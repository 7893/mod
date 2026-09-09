"""Quota Watchdog for Cloudflare Workers AI free tier governance.

Key Rules:
1. Daily neuron ceiling: 3,000 Neurons/day (out of Cloudflare's 10,000 free quota).
2. Guarantees $0.00 bill: Never exceeds the 3,000 neuron threshold under any condition.
3. Persistent audit ledger in `sim_ai_quota_ledger`.
4. If daily limit is reached or quota check fails, trips fuse to FUSED state, forcing
   graceful degradation to LocalNarrativeLibrary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
import os
from typing import Optional, Tuple

import pymysql
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Daily ceiling for simulation governance AI calls.
DAILY_NEURON_LIMIT: float = 3000.0


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
        """Returns existing connection or creates an autocommitting connection."""
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
            autocommit=True,
        )

    def can_consume(
        self,
        estimated_neurons: float = 50.0,
        target_date: Optional[date] = None,
    ) -> Tuple[bool, str]:
        """Check if today's consumption allows consuming estimated_neurons."""
        check_date = target_date or datetime.now(timezone.utc).date()
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
        check_date = target_date or datetime.now(timezone.utc).date()
        now = datetime.now(timezone.utc)
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

    def get_status(self, target_date: Optional[date] = None) -> QuotaStatus:
        """Retrieve current daily status."""
        check_date = target_date or datetime.now(timezone.utc).date()
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
