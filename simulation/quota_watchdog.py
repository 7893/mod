"""Quota Watchdog for Cloudflare Workers AI free tier governance.

Key Rules:
1. Project-side daily neuron budget: 3,000 Neurons/day.
2. Reserve conservatively before each external request and reconcile afterwards.
3. Persistent audit ledger in `sim_ai_quota_ledger`.
4. If the project budget is reached or quota check fails, trip the FUSED state, forcing
   graceful degradation to LocalNarrativeLibrary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
import os
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

import pymysql
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Daily ceiling for simulation governance AI calls.
DAILY_NEURON_LIMIT: float = 3000.0
HK_TZ = ZoneInfo("Asia/Hong_Kong")


@dataclass
class QuotaStatus:
    stat_date: str
    call_count: int
    neurons_used: float
    daily_limit: float
    remaining_neurons: float
    usage_pct: float
    status: str  # "ACTIVE" | "FUSED" | "DISABLED"


class QuotaWatchdog:
    """Manages daily neuron quotas and ledger persistence."""

    def __init__(
        self,
        conn: Optional[pymysql.Connection] = None,
        daily_limit: float = DAILY_NEURON_LIMIT,
    ):
        self._conn = conn
        self.daily_limit = daily_limit

    def _get_connection(self) -> pymysql.Connection:
        """Return the injected connection or create a transaction-owning connection."""
        if self._conn is not None:
            return self._conn

        if not os.environ.get("MOD_DB_HOST"):
            for env_file in [".env.systemd", ".env.local", ".env"]:
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    break

        user = os.getenv("MOD_DB_USER", "")
        password = os.getenv("MOD_DB_PASSWORD", "")
        host = os.getenv("MOD_DB_HOST", "127.0.0.1")
        port = int(os.getenv("MOD_DB_PORT", 3306))
        db = os.getenv("MOD_DB_NAME", "mod")

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # secret-scan: allow
            database=db,
            # Reservation correctness depends on SELECT ... FOR UPDATE holding the
            # row lock until the explicit commit below.
            autocommit=False,
        )

    def can_consume(
        self,
        estimated_neurons: float = 50.0,
        target_date: Optional[date] = None,
    ) -> Tuple[bool, str]:
        """Check if today's consumption allows consuming estimated_neurons."""
        check_date = target_date or datetime.now(HK_TZ).date()
        conn = self._get_connection()
        close_needed = conn != self._conn

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT neurons_used, status FROM sim_ai_quota_ledger WHERE stat_date = %s",
                    (check_date,),
                )
                row = cur.fetchone()
                if not row:
                    return True, "Quota available (no usage yet today)"

                neurons_used, status = float(row[0]), str(row[1])
                if status == "FUSED" or (neurons_used + estimated_neurons) > self.daily_limit:
                    return (
                        False,
                        f"Quota exhausted: used {neurons_used:.1f}/{self.daily_limit:.1f} neurons "
                        f"(requested +{estimated_neurons:.1f})",
                    )
                return True, f"Quota available ({self.daily_limit - neurons_used:.1f} remaining)"
        finally:
            if close_needed:
                conn.close()

    def record_consumption(
        self,
        neurons_used: float,
        call_count: int = 1,
        target_date: Optional[date] = None,
    ) -> QuotaStatus:
        """Record consumption into sim_ai_quota_ledger with atomic update."""
        check_date = target_date or datetime.now(HK_TZ).date()
        now = datetime.now(HK_TZ)
        conn = self._get_connection()
        close_needed = conn != self._conn

        try:
            with conn.cursor() as cur:
                # Upsert daily ledger
                cur.execute(
                    """
                    INSERT INTO sim_ai_quota_ledger (stat_date, call_count, neurons_used, status, updated_at)
                    VALUES (%s, %s, %s, CASE WHEN %s >= %s THEN 'FUSED' ELSE 'ACTIVE' END, %s)
                    ON DUPLICATE KEY UPDATE
                        call_count = call_count + VALUES(call_count),
                        neurons_used = neurons_used + VALUES(neurons_used),
                        status = CASE WHEN neurons_used + VALUES(neurons_used) >= %s THEN 'FUSED' ELSE 'ACTIVE' END,
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        check_date,
                        call_count,
                        neurons_used,
                        neurons_used,
                        self.daily_limit,
                        now,
                        self.daily_limit,
                    ),
                )
                if not getattr(conn, "autocommit", False):
                    conn.commit()

                cur.execute(
                    "SELECT call_count, neurons_used, status FROM sim_ai_quota_ledger WHERE stat_date = %s",
                    (check_date,),
                )
                r = cur.fetchone()
                calls, used, status = int(r[0]), float(r[1]), str(r[2])

                return QuotaStatus(
                    stat_date=check_date.isoformat(),
                    call_count=calls,
                    neurons_used=round(used, 2),
                    daily_limit=self.daily_limit,
                    remaining_neurons=max(0.0, round(self.daily_limit - used, 2)),
                    usage_pct=min(100.0, round((used / self.daily_limit) * 100, 2)),
                    status=status,
                )
        finally:
            if close_needed:
                conn.close()

    def try_reserve(
        self,
        estimated_neurons: float,
        target_date: Optional[date] = None,
    ) -> Tuple[bool, str]:
        """Atomically reserve a conservative per-call budget before external I/O.

        The ledger row is locked until the reservation commits. A process crash leaves
        a conservative reservation behind, which fails safe instead of overspending.
        """
        if estimated_neurons <= 0:
            return False, "Estimated neurons must be positive"
        check_date = target_date or datetime.now(HK_TZ).date()
        now = datetime.now(HK_TZ)
        conn = self._get_connection()
        close_needed = conn != self._conn
        try:
            with conn.cursor() as cur:
                # Materialize the daily row first. INSERT IGNORE plus the unique
                # stat_date key closes the absent-row race between two processes.
                cur.execute(
                    "INSERT IGNORE INTO sim_ai_quota_ledger "
                    "(stat_date, call_count, neurons_used, status, updated_at) "
                    "VALUES (%s, 0, 0, 'ACTIVE', %s)",
                    (check_date, now),
                )
                cur.execute(
                    "SELECT call_count, neurons_used, status FROM sim_ai_quota_ledger "
                    "WHERE stat_date = %s FOR UPDATE",
                    (check_date,),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Quota ledger row unavailable after initialization")
                used = float(row[1])
                status = str(row[2])
                if status == "FUSED" or used + estimated_neurons > self.daily_limit:
                    if not getattr(conn, "autocommit", False):
                        conn.rollback()
                    return False, (
                        f"Quota exhausted: used {used:.1f}/{self.daily_limit:.1f} neurons "
                        f"(reservation +{estimated_neurons:.1f})"
                    )
                cur.execute(
                    "UPDATE sim_ai_quota_ledger SET neurons_used = %s, status = 'ACTIVE', "
                    "updated_at = %s WHERE stat_date = %s",
                    (used + estimated_neurons, now, check_date),
                )
                if not getattr(conn, "autocommit", False):
                    conn.commit()
            return True, f"Reserved {estimated_neurons:.1f} neurons"
        except Exception:
            if not getattr(conn, "autocommit", False):
                conn.rollback()
            raise
        finally:
            if close_needed:
                conn.close()

    def reconcile_reservation(
        self,
        reserved_neurons: float,
        actual_neurons: float,
        call_count: int,
        target_date: Optional[date] = None,
    ) -> None:
        """Replace a reservation with actual usage, or release it after failure."""
        check_date = target_date or datetime.now(HK_TZ).date()
        now = datetime.now(HK_TZ)
        conn = self._get_connection()
        close_needed = conn != self._conn
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT call_count, neurons_used, status FROM sim_ai_quota_ledger "
                    "WHERE stat_date = %s FOR UPDATE",
                    (check_date,),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Quota reservation ledger row disappeared before reconciliation")
                calls = int(row[0]) + call_count
                used = max(0.0, float(row[1]) - reserved_neurons + max(0.0, actual_neurons))
                status = "FUSED" if used >= self.daily_limit else "ACTIVE"
                cur.execute(
                    "UPDATE sim_ai_quota_ledger SET call_count = %s, neurons_used = %s, "
                    "status = %s, updated_at = %s WHERE stat_date = %s",
                    (calls, used, status, now, check_date),
                )
                if not getattr(conn, "autocommit", False):
                    conn.commit()
        except Exception:
            if not getattr(conn, "autocommit", False):
                conn.rollback()
            raise
        finally:
            if close_needed:
                conn.close()

    def get_status(self, target_date: Optional[date] = None) -> QuotaStatus:
        """Retrieve current daily status."""
        check_date = target_date or datetime.now(HK_TZ).date()
        conn = self._get_connection()
        close_needed = conn != self._conn

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT call_count, neurons_used, status FROM sim_ai_quota_ledger WHERE stat_date = %s",
                    (check_date,),
                )
                row = cur.fetchone()
                if not row:
                    return QuotaStatus(
                        stat_date=check_date.isoformat(),
                        call_count=0,
                        neurons_used=0.0,
                        daily_limit=self.daily_limit,
                        remaining_neurons=self.daily_limit,
                        usage_pct=0.0,
                        status="ACTIVE",
                    )

                calls, used, status = int(row[0]), float(row[1]), str(row[2])
                return QuotaStatus(
                    stat_date=check_date.isoformat(),
                    call_count=calls,
                    neurons_used=round(used, 2),
                    daily_limit=self.daily_limit,
                    remaining_neurons=max(0.0, round(self.daily_limit - used, 2)),
                    usage_pct=min(100.0, round((used / self.daily_limit) * 100, 2)),
                    status=status,
                )
        finally:
            if close_needed:
                conn.close()
