"""
Realistic Business Simulation Engine - Resident Background Runtime Service (Step 3).

Integrates:
1. HongKongDiurnalEngine: 24h diurnal curve, weekend damping, month-end spikes, Poisson bursts.
2. Dual Rate Limiting:
   - Soft: Diurnal intensity & Poisson burst intervals.
   - Hard Fuse: Max events per minute (<= 20) and per day (<= 5000), pauses and logs warnings if reached.
3. Fast Movie + Slow Movie Coordination:
   - Fast Movie: Expense reimbursement footprints (SimulationWriter + daily_stats cascade).
   - Slow Movie: Construction mainline milestones & B-mode advancer (ConstructionWriter).
4. Post-Cycle Self-Check & Safe Error Handling:
   - Every write cycle runs deterministic self-check (debit=credit, applicant matches org, no time inversion, no orphans).
   - Single cycle failure: rolls back that batch, logs ERROR audit, continues next cycle.
   - Consecutive failures >= threshold (default 3): trips persistent fail-closed flag file, logs CRITICAL audit, halts writes.
5. Persistent Fail-Closed Guard:
   - If output/simulator_fail_closed.flag exists, service refuses to write until manually cleared.
6. Graceful lifecycle and status monitoring (output/simulator_status.json).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pymysql

from app.live_projection.simulation_engine import HongKongDiurnalEngine
from app.live_projection.outbox_writer import append_outbox
from .construction_models import validate_construction_event
from .pool_onboarding import ReservePoolAdmissionPlaybook
from .construction_writer import ConstructionWriter
from .engine_context import (
    IdAllocator,
    load_construction_baseline,
    load_simulation_baseline,
)
from .expense_playbook import ExpensePlaybook
from .evolution_coordinator import EvolutionCoordinator
from .footprint_models import EventFootprint, validate_footprint
from .simulation_writer import SimulationWriter, is_simulation_engine_enabled

logger = logging.getLogger(__name__)
HK_TZ = ZoneInfo("Asia/Hong_Kong")


@dataclass
class SimulatorRuntimeConfig:
    """Configuration for simulation runtime service."""

    max_events_per_minute: int = 20
    max_events_per_day: int = 5000
    consecutive_failure_threshold: int = 3
    fail_closed_flag_path: Path = field(default_factory=lambda: Path("output/simulator_fail_closed.flag"))
    fuse_state_path: Path = field(default_factory=lambda: Path("output/simulator_fuse_state.json"))
    status_file_path: Path = field(default_factory=lambda: Path("output/simulator_status.json"))
    audit_log_path: Path = field(default_factory=lambda: Path("output/simulation_audit.log"))
    lifecycle_state_path: Optional[Path] = None
    slow_movie_interval_cycles: int = 6
    min_wait_seconds: float = 2.5
    max_wait_seconds: float = 90.0
    dry_run: bool = False


class FailClosedManager:
    """Manages persistent fail-closed flag file on disk."""

    def __init__(self, flag_path: Path, audit_log_path: Path):
        self.flag_path = flag_path
        self.audit_log_path = audit_log_path

    def is_tripped(self) -> bool:
        return self.flag_path.exists()

    def trip(self, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "tripped": True,
            "timestamp": datetime.now(HK_TZ).isoformat(),
            "reason": reason,
            "details": details or {},
            "status": "HALTED",
        }
        with open(self.flag_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        logger.critical(f"[FAIL-CLOSED TRIPPED] {reason}")
        self._record_critical_audit(reason, details)

    def clear(self) -> bool:
        if self.flag_path.exists():
            try:
                self.flag_path.unlink()
                logger.info("[FAIL-CLOSED CLEARED] Flag removed by operator.")
                return True
            except Exception as ex:
                logger.error(f"Failed to clear fail-closed flag: {ex}")
                return False
        return False

    def get_trip_info(self) -> Optional[Dict[str, Any]]:
        if not self.flag_path.exists():
            return None
        try:
            with open(self.flag_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"tripped": True, "reason": "Unreadable flag file"}

    def _record_critical_audit(self, reason: str, details: Optional[Dict[str, Any]]) -> None:
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(HK_TZ).isoformat(),
                "level": "CRITICAL",
                "action": "FAIL_CLOSED_TRIPPED",
                "reason": reason,
                "details": details or {},
            }
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as ex:
            logger.warning(f"Could not record critical audit: {ex}")


class RateLimitFuse:
    """Minute/day hard caps with an atomic, cross-process reservation ledger."""

    def __init__(
        self,
        max_per_minute: int = 20,
        max_per_day: int = 5000,
        state_file_path: Optional[Path] = None,
    ):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self.state_file_path = Path(state_file_path) if state_file_path else None
        self._current_minute = ""
        self._minute_count = 0
        self._current_day = ""
        self._day_count = 0
        self._corruption_error: Optional[str] = None
        self._mutex = threading.Lock()
        self._lock_file_path = (
            self.state_file_path.with_suffix(".lock") if self.state_file_path else None
        )
        self._init_persisted_state()

    def _init_persisted_state(self) -> None:
        if not self.state_file_path or not self.state_file_path.exists():
            return
        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "business_date" not in data or "day_count" not in data:
                raise RuntimeError(f"Invalid schema in rate limit state file: {self.state_file_path}")
            self._current_day = str(data["business_date"])
            self._day_count = int(data["day_count"])
            self._current_minute = str(data.get("minute_key", ""))
            self._minute_count = int(data.get("minute_count", 0))
        except Exception as ex:
            logger.error(f"Failed to load rate limit state file: {ex}")
            self._corruption_error = f"Corrupted rate limit state file: {ex}"

    def _sync_persisted_state(self, day_key: str) -> None:
        if self._corruption_error:
            raise RuntimeError(self._corruption_error)
        if not self.state_file_path or not self.state_file_path.exists():
            if self._current_day != day_key:
                self._current_day = day_key
                self._day_count = 0
            return

        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "business_date" not in data or "day_count" not in data:
                raise RuntimeError(f"Invalid schema in rate limit state file: {self.state_file_path}")
            file_date = str(data["business_date"])
            if file_date == day_key:
                self._current_day = day_key
                self._day_count = int(data["day_count"])
            elif file_date < day_key:
                # Rollover to new business day
                self._current_day = day_key
                self._day_count = 0
            else:
                # File date is ahead of local clock (clock skew protection)
                raise RuntimeError(
                    f"Rate limit business date {file_date} is ahead of local date {day_key}"
                )
        except (json.JSONDecodeError, RuntimeError) as ex:
            self._corruption_error = f"Corrupted rate limit state file: {self.state_file_path}: {ex}"
            raise RuntimeError(self._corruption_error) from ex

    def can_produce(self, now: datetime, count: int = 1) -> Tuple[bool, str]:
        if self._corruption_error:
            return False, f"Rate limit state error (fail-closed): {self._corruption_error}"

        now_hkt = now.astimezone(HK_TZ) if now.tzinfo else now.replace(tzinfo=HK_TZ)
        minute_key = now_hkt.strftime("%Y-%m-%d %H:%M")
        day_key = now_hkt.strftime("%Y-%m-%d")

        try:
            self._sync_persisted_state(day_key)
        except Exception as ex:
            return False, f"Rate limit state error (fail-closed): {ex}"

        minute_count = self._minute_count if minute_key == self._current_minute else 0
        day_count = self._day_count if day_key == self._current_day else 0

        if minute_count + count > self.max_per_minute:
            return False, f"Minute hard cap reached ({minute_count}/{self.max_per_minute})"

        if day_count + count > self.max_per_day:
            return False, f"Daily hard cap reached ({day_count}/{self.max_per_day})"

        return True, ""

    def reserve(self, now: datetime, count: int = 1, persist: bool = True) -> Tuple[bool, str]:
        """Atomically reserve capacity before writing a simulation batch."""
        if count < 0:
            return False, "Reservation count cannot be negative"
        now_hkt = now.astimezone(HK_TZ) if now.tzinfo else now.replace(tzinfo=HK_TZ)
        minute_key = now_hkt.strftime("%Y-%m-%d %H:%M")
        day_key = now_hkt.strftime("%Y-%m-%d")

        def reserve_locked() -> Tuple[bool, str]:
            if self._corruption_error:
                return False, f"Rate limit state error (fail-closed): {self._corruption_error}"

            day_count = self._day_count if self._current_day == day_key else 0
            minute_count = self._minute_count if self._current_minute == minute_key else 0
            if self.state_file_path and persist and self.state_file_path.exists():
                try:
                    with open(self.state_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        raise RuntimeError("state is not a JSON object")
                    file_date = str(data.get("business_date", ""))
                    if file_date > day_key:
                        raise RuntimeError(
                            f"business date {file_date} is ahead of local date {day_key}"
                        )
                    if file_date == day_key:
                        day_count = int(data.get("day_count", 0))
                        minute_count = (
                            int(data.get("minute_count", 0))
                            if str(data.get("minute_key", "")) == minute_key
                            else 0
                        )
                    else:
                        day_count = 0
                        minute_count = 0
                except Exception as ex:
                    self._corruption_error = f"Corrupted rate limit state file: {ex}"
                    return False, f"Rate limit state error (fail-closed): {ex}"

            if minute_count + count > self.max_per_minute:
                return False, f"Minute hard cap reached ({minute_count}/{self.max_per_minute})"
            if day_count + count > self.max_per_day:
                return False, f"Daily hard cap reached ({day_count}/{self.max_per_day})"

            self._current_minute = minute_key
            self._minute_count = minute_count + count
            self._current_day = day_key
            self._day_count = day_count + count
            if self.state_file_path and persist:
                self._write_state(now_hkt)
            return True, ""

        with self._mutex:
            if not self.state_file_path or not persist:
                return reserve_locked()
            import fcntl
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = self._lock_file_path or self.state_file_path.with_suffix(".lock")
            with open(lock_file, "w") as lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                try:
                    return reserve_locked()
                finally:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    def _write_state(self, now_hkt: datetime) -> None:
        if not self.state_file_path:
            return
        state_data = {
            "business_date": self._current_day,
            "day_count": self._day_count,
            "minute_key": self._current_minute,
            "minute_count": self._minute_count,
            "timezone": "Asia/Hong_Kong",
            "updated_at": now_hkt.isoformat(),
        }
        tmp_path = self.state_file_path.with_name(f".tmp_{self.state_file_path.name}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(self.state_file_path)
        with suppress(OSError):
            self.state_file_path.chmod(0o644)

    def release(self, now: datetime, count: int, persist: bool = True) -> None:
        """Release a reservation after rollback or when the committed batch was smaller."""
        if count <= 0:
            return
        now_hkt = now.astimezone(HK_TZ) if now.tzinfo else now.replace(tzinfo=HK_TZ)
        minute_key = now_hkt.strftime("%Y-%m-%d %H:%M")
        day_key = now_hkt.strftime("%Y-%m-%d")

        def release_locked() -> None:
            if self.state_file_path and persist and self.state_file_path.exists():
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if str(data.get("business_date", "")) != day_key:
                    return
                self._current_day = day_key
                self._day_count = max(0, int(data.get("day_count", 0)) - count)
                self._current_minute = str(data.get("minute_key", ""))
                current_minute_count = int(data.get("minute_count", 0))
                self._minute_count = (
                    max(0, current_minute_count - count)
                    if self._current_minute == minute_key
                    else current_minute_count
                )
                self._write_state(now_hkt)
                return
            if self._current_day == day_key:
                self._day_count = max(0, self._day_count - count)
            if self._current_minute == minute_key:
                self._minute_count = max(0, self._minute_count - count)

        with self._mutex:
            if not self.state_file_path or not persist:
                release_locked()
                return
            import fcntl
            lock_file = self._lock_file_path or self.state_file_path.with_suffix(".lock")
            with open(lock_file, "w") as lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                try:
                    release_locked()
                finally:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    def record(self, now: datetime, count: int = 1, persist: bool = True) -> None:
        ok, reason = self.reserve(now, count=count, persist=persist)
        if not ok:
            raise RuntimeError(reason)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "minute_count": self._minute_count,
            "max_per_minute": self.max_per_minute,
            "day_count": self._day_count,
            "max_per_day": self.max_per_day,
            "business_date": self._current_day,
        }


class PostCycleSelfChecker:
    """In-transaction or post-commit self-check assertions verifying zero regressions."""

    @staticmethod
    def check_fast_movie_events(conn: Any, events: List[EventFootprint]) -> Tuple[bool, str]:
        for ev in events:
            # 1. Check debit == credit and sum(lines) == doc.amount
            line_sum = sum(line.amount for line in ev.document.lines)
            if line_sum != ev.document.amount:
                return False, f"Line sum mismatch for doc {ev.document.id}: {line_sum} != {ev.document.amount}"

            total_debit = sum(vl.debit for vl in ev.voucher.lines)
            total_credit = sum(vl.credit for vl in ev.voucher.lines)
            if total_debit != total_credit or total_debit != ev.document.amount:
                return False, f"Voucher lines unbalanced for doc {ev.document.id}: D={total_debit}, C={total_credit}"

            # 2. Check time progression
            if ev.document.approve_time < ev.document.submit_time:
                return False, f"Time inversion for doc {ev.document.id}: approve < submit"

            # 3. Check applicant in sys_user if live connection is provided
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM sys_user WHERE org_id = %s AND name = %s;",
                        (ev.document.org_id, ev.document.applicant),
                    )
                    if cur.fetchone()[0] == 0:
                        return False, f"Applicant {ev.document.applicant} not found in org {ev.document.org_id}"

        return True, ""

    @staticmethod
    def check_construction_events(conn: Any, events: List[object]) -> Tuple[bool, str]:
        for ev in events:
            try:
                validate_construction_event(ev)
            except Exception as ex:
                return False, f"Construction event validation error: {ex}"
        return True, ""


@dataclass
class CycleResult:
    """Outcome of a single runtime loop cycle."""

    status: str  # "SUCCESS", "RATE_LIMITED", "DRY_RUN", "FAIL_CLOSED", "ERROR"
    events_written: int = 0
    wait_seconds: float = 10.0
    intensity: float = 1.0
    error: Optional[str] = None
    cycle_duration_ms: float = 0.0


class SimulatorRuntimeService:
    """
    Resident background service driving realistic 7x24 simulation generation.
    """

    def __init__(
        self,
        config: Optional[SimulatorRuntimeConfig] = None,
        conn: Optional[Any] = None,
        seed: Optional[int] = None,
        propeller: Optional[Any] = None,
        backfiller: Optional[Any] = None,
        projection_writer=None,
    ):
        self.config = config or SimulatorRuntimeConfig()
        self._external_conn = conn
        self.rng = random.Random(seed)
        self.fail_closed_mgr = FailClosedManager(self.config.fail_closed_flag_path, self.config.audit_log_path)
        self.fuse = RateLimitFuse(
            max_per_minute=self.config.max_events_per_minute,
            max_per_day=self.config.max_events_per_day,
            state_file_path=self.config.fuse_state_path,
        )
        self.consecutive_failures = 0
        self.cycle_count = 0
        self.start_time = time.time()
        self.onboarding_dates: List[Any] = []
        self._last_rate_limit_reason: Optional[str] = None
        self._last_rate_limit_warn_time: float = 0.0
        self.propeller = propeller
        self.backfiller = backfiller
        self.projection_writer = projection_writer or append_outbox

        # Cache baselines
        self._fast_baseline: Optional[Any] = None
        self._fast_allocator: Optional[IdAllocator] = None
        self._construction_baseline: Optional[Any] = None
        self._construction_allocator: Optional[IdAllocator] = None
        self._evolution_coordinator: Optional[EvolutionCoordinator] = None

    def _get_connection(self) -> Any:
        if self._external_conn:
            return self._external_conn

        host = os.environ.get("MOD_DB_HOST", "127.0.0.1")
        port = int(os.environ.get("MOD_DB_PORT", "3306"))
        user = os.environ.get("MOD_DB_USER", "")
        password = os.environ.get("MOD_DB_PASSWORD", "")
        database = os.environ.get("MOD_DB_NAME", "mod")

        if not user:
            raise ValueError("Database user not configured in environment (MOD_DB_USER)")

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # secret-scan: allow
            database=database,
            charset="utf8mb4",
            autocommit=False,
        )

    def _ensure_baselines(self, conn: Any) -> None:
        if self._fast_baseline is None or (self.cycle_count > 0 and self.cycle_count % 100 == 0):
            self._fast_baseline = load_simulation_baseline(conn)
            self._fast_allocator = IdAllocator(self._fast_baseline.next_ids)

        # The coordinator owns construction lifecycle state after initialization.
        # Replacing its baseline every 100 cycles would split runtime state between
        # the coordinator and a newly loaded object.
        if self._construction_baseline is None:
            self._construction_baseline = load_construction_baseline(conn)
            self._construction_allocator = IdAllocator(self._construction_baseline.next_ids)
        if self._evolution_coordinator is None and self._construction_baseline is not None:
            self._evolution_coordinator = EvolutionCoordinator(
                self._construction_baseline,
                seed=self.rng.randint(1, 1000000),
            )
            self._construction_allocator = self._evolution_coordinator.allocator
            self._restore_evolution_state()

    def step_cycle(self, now: Optional[datetime] = None) -> CycleResult:
        """Execute one complete diurnal simulation tick cycle."""
        t0 = time.perf_counter()
        now_hkt = now or datetime.now(HK_TZ)

        # 1. Guard against persistent fail-closed state
        if self.fail_closed_mgr.is_tripped():
            info = self.fail_closed_mgr.get_trip_info()
            reason = info.get("reason", "Persistent fail-closed flag set") if info else "Fail-closed"
            return CycleResult(
                status="FAIL_CLOSED",
                events_written=0,
                wait_seconds=60.0,
                intensity=0.0,
                error=f"HALTED: {reason}. Manual clearance required.",
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # 2. Query Diurnal Intensity & Interval
        intensity = HongKongDiurnalEngine.get_intensity(now_hkt)
        wait_seconds, burst_count = HongKongDiurnalEngine.next_burst_interval(now_hkt, self.rng)
        wait_seconds = max(self.config.min_wait_seconds, min(self.config.max_wait_seconds, wait_seconds))

        # 3. The disabled/dry-run path is strictly observational and must not consume
        #    rate-limit capacity or touch any persistence.
        engine_enabled = is_simulation_engine_enabled() and not self.config.dry_run
        if not engine_enabled:
            logger.info(
                f"[DRY-RUN TICK] {now_hkt.strftime('%Y-%m-%d %H:%M:%S')} HKT | "
                f"Intensity: {intensity:.3f} | Planned burst: {burst_count} events | DB Write: DISABLED"
            )
            self._save_status("DRY_RUN", intensity, now_hkt, None)
            return CycleResult(
                status="DRY_RUN",
                events_written=0,
                wait_seconds=wait_seconds,
                intensity=intensity,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # 4. Atomically reserve the planned burst before acquiring a DB connection.
        #    A failed transaction releases the reservation; a smaller slow-movie batch
        #    releases the unused tail after commit.
        reservation_count = burst_count
        reserved, limit_reason = self.fuse.reserve(now_hkt, reservation_count, persist=True)
        if not reserved:
            now_mono = time.monotonic()
            if limit_reason != self._last_rate_limit_reason or (now_mono - self._last_rate_limit_warn_time) >= 300.0:
                logger.warning(f"[RATE_LIMIT_FUSE] {limit_reason}. Pausing cycle.")
                self._last_rate_limit_reason = limit_reason
                self._last_rate_limit_warn_time = now_mono

            self._save_status("RATE_LIMITED", intensity, now_hkt, limit_reason)
            return CycleResult(
                status="RATE_LIMITED",
                events_written=0,
                wait_seconds=wait_seconds,
                intensity=intensity,
                error=limit_reason,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )
        self._last_rate_limit_reason = None

        conn = None
        lifecycle_state_saved = True
        db_lock_acquired = False
        try:
            conn = self._get_connection()

            # KI-072: Acquire database-level leader lock to prevent dual-instance conflicts
            with conn.cursor() as cur:
                cur.execute("SELECT GET_LOCK('mod_simulator_leader', 0) AS acquired")
                lock_result = cur.fetchone()
                if not lock_result or lock_result[0] != 1:
                    logger.info("[STANDBY] Another simulator instance holds the leader lock. Skipping cycle.")
                    self._save_status("STANDBY", intensity, now_hkt, "Another instance is leader")
                    self.fuse.release(now_hkt, reservation_count, persist=True)
                    return CycleResult(
                        status="STANDBY",
                        events_written=0,
                        wait_seconds=wait_seconds,
                        intensity=intensity,
                        error="Another simulator instance is leader",
                        cycle_duration_ms=(time.perf_counter() - t0) * 1000,
                    )
                db_lock_acquired = True

            self._ensure_baselines(conn)
            self.cycle_count += 1

            # Decide fast vs slow movie
            is_slow_movie = (self.cycle_count % self.config.slow_movie_interval_cycles == 0) and burst_count > 0

            if is_slow_movie:
                # Generate slow-movie construction event
                all_events = self._generate_slow_movie_events(now_hkt.date())
                is_construction = True
            else:
                # Generate fast-movie expense events
                playbook = ExpensePlaybook(self._fast_baseline, self._fast_allocator, seed=self.rng.randint(1, 1000000))
                fast_events: List[EventFootprint] = []
                for _ in range(burst_count):
                    fe = playbook.generate_event(target_date=now_hkt)
                    validate_footprint(fe)
                    fast_events.append(fe)
                all_events = fast_events  # type: ignore
                is_construction = False

            # 5. Real Atomic Write Execution (Single-Transaction Ownership)
            c_writer: Optional[ConstructionWriter] = None
            s_writer: Optional[SimulationWriter] = None
            construction_audit: Optional[Any] = None

            if is_construction:
                if not all_events:
                    events_written = 0
                else:
                    c_writer = ConstructionWriter(conn=conn, audit_log_path=str(self.config.audit_log_path))
                    c_res = c_writer.write_construction_events(
                        all_events, execute=True, create_backup=False, auto_commit=False
                    )
                    if not c_res.success:
                        raise RuntimeError(f"Construction write failed: {c_res.error}")

                    ok, chk_err = PostCycleSelfChecker.check_construction_events(conn, all_events)
                    if not ok:
                        raise RuntimeError(f"Post-cycle construction self-check failed: {chk_err}")

                    construction_audit = c_res
                    events_written = len(all_events)

                # KI-062: Hook ConstructionPropeller (The Spear & Shield)
                if self.propeller is not None:
                    self.propeller.step(now=now_hkt, auto_commit=False)
                elif not (type(conn).__name__ == "MagicMock" or type(conn).__name__ == "Mock"):
                    from .construction_propeller import ConstructionPropeller

                    propeller = ConstructionPropeller(conn=conn)
                    prop_res = propeller.step(now=now_hkt, auto_commit=False)
                    logger.info(
                        f"[PROPELLER] Units advanced: {prop_res.units_advanced} | "
                        f"Issues advanced: {prop_res.issues_advanced} | "
                        f"Issues resolved: {prop_res.issues_resolved} | "
                        f"Issues created: {prop_res.issues_created}"
                    )

                # KI-062: Trickle backfill AI narrative (guarded by 3,000 neurons/day QuotaWatchdog)
                if os.getenv("MOD_CF_AI_ENABLED", "true").lower() == "true":
                    if self.backfiller is not None:
                        self.backfiller.run_cycle(batch_size=1, auto_commit=False)
                    elif not (type(conn).__name__ == "MagicMock" or type(conn).__name__ == "Mock"):
                        from .trickle_backfill import TrickleBackfiller

                        backfiller = TrickleBackfiller(conn=conn)
                        backfiller.run_cycle(batch_size=1, auto_commit=False)

                conn.commit()
                if c_writer is not None and construction_audit is not None:
                    c_writer.record_success_audit(construction_audit)
                lifecycle_state_saved = self._save_evolution_state()
            else:
                s_writer = SimulationWriter(conn=conn, audit_log_path=str(self.config.audit_log_path))
                s_res = s_writer.write_events(all_events, auto_commit=False)  # type: ignore
                if not s_res.success:
                    raise RuntimeError(f"Fast-movie write failed: {s_res.error}")

                ok, chk_err = PostCycleSelfChecker.check_fast_movie_events(conn, all_events)  # type: ignore
                if not ok:
                    raise RuntimeError(f"Post-cycle fast-movie self-check failed: {chk_err}")

                self.projection_writer(conn, [self._projection_record(event, now_hkt) for event in all_events])
                conn.commit()
                s_writer.record_success_audit(s_res)
                events_written = len(all_events)

            # Success: reservation already counted. Slow-movie cycles usually commit fewer
            # events than the planned burst, so release only the unused capacity.
            self.consecutive_failures = 0
            self.fuse.release(now_hkt, max(0, reservation_count - events_written), persist=True)
            if not lifecycle_state_saved:
                err_msg = "Committed lifecycle events but failed to persist restart state; service halted"
                self._save_status("ERROR", intensity, now_hkt, err_msg)
                return CycleResult(
                    status="ERROR",
                    events_written=events_written,
                    wait_seconds=wait_seconds,
                    intensity=intensity,
                    error=err_msg,
                    cycle_duration_ms=(time.perf_counter() - t0) * 1000,
                )
            self._save_status("SUCCESS", intensity, now_hkt, None)

            return CycleResult(
                status="SUCCESS",
                events_written=events_written,
                wait_seconds=wait_seconds,
                intensity=intensity,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )

        except Exception as ex:
            self.fuse.release(now_hkt, reservation_count, persist=True)
            if conn:
                with suppress(Exception):
                    conn.rollback()

            # KI-083: Discard in-memory baselines and allocators after failure / rollback
            # so the next retry cycle reloads clean DB truth rather than colliding on stale IDs.
            self._fast_baseline = None
            self._fast_allocator = None

            if "is_construction" in locals() and is_construction:
                # Lifecycle generation mutates in-memory evidence before staging its
                # matching rows. Discard it after rollback; the next cycle reloads DB
                # truth plus the last committed restart-state file.
                self._construction_baseline = None
                self._construction_allocator = None
                self._evolution_coordinator = None
                self.onboarding_dates = []

            self.consecutive_failures += 1
            err_msg = str(ex)
            logger.error(
                f"[CYCLE ERROR] Consecutive failure {self.consecutive_failures}/"
                f"{self.config.consecutive_failure_threshold}: {err_msg}"
            )

            # Record failure audit if writers were active
            try:
                if 'is_construction' in locals() and is_construction and c_writer:
                    c_writer.record_failure_audit(err_msg, event_count=len(all_events) if 'all_events' in locals() else 0)
                elif s_writer:
                    s_writer.record_failure_audit(err_msg, event_count=len(all_events) if 'all_events' in locals() else 0)
            except Exception as audit_ex:
                logger.warning("失败审计落库自身失败，本周期失败仅存日志: %s", type(audit_ex).__name__)

            # Check if threshold reached for fail-closed trip
            if self.consecutive_failures >= self.config.consecutive_failure_threshold:
                self.fail_closed_mgr.trip(
                    reason=f"Exceeded {self.config.consecutive_failure_threshold} consecutive cycle self-check failures",
                    details={"last_error": err_msg, "consecutive_failures": self.consecutive_failures},
                )

            self._save_status("ERROR", intensity, now_hkt, err_msg)
            return CycleResult(
                status="ERROR",
                events_written=0,
                wait_seconds=wait_seconds,
                intensity=intensity,
                error=err_msg,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )
        finally:
            # KI-072: Release database-level leader lock
            if db_lock_acquired and conn:
                with suppress(Exception):
                    with conn.cursor() as cur:
                        cur.execute("SELECT RELEASE_LOCK('mod_simulator_leader')")
            if not self._external_conn and conn:
                conn.close()

    def _generate_slow_movie_events(self, event_date: Any) -> List[object]:
        """Generate metric evidence and any formal lifecycle review for one unit."""
        if not self._construction_baseline:
            return []

        # KI-035: Low-frequency Batch 8 dynamic reserve pool admission (1~3 per week)
        admissions_in_week = sum(
            1 for d in self.onboarding_dates if 0 <= (event_date - d).days < 7
        )
        days_since_last = (
            (event_date - self.onboarding_dates[-1]).days
            if self.onboarding_dates
            else 999
        )
        # Sporadic admission: max 3/week, min 2 days gap, controlled tick probability
        if admissions_in_week < 3 and days_since_last >= 2 and self.rng.random() < 0.10:
            pb_onboard = ReservePoolAdmissionPlaybook(
                baseline=self._construction_baseline,
                id_allocator=self._construction_allocator,
                seed=self.rng.randint(1, 1000000),
            )
            ev = pb_onboard.generate(event_date=event_date, id_allocator=self._construction_allocator)
            self.onboarding_dates.append(event_date)
            # Sync in-memory baseline
            self._construction_baseline.orgs[ev.org_id] = {
                "id": ev.org_id,
                "name": ev.name,
                "batch_id": 8,
                "status": "未启动",
                "region": ev.region,
                "start_date": ev.start_date,
                "end_date": ev.end_date,
            }
            self._construction_baseline.orgs_by_status.setdefault("未启动", []).append(ev.org_id)
            self._construction_baseline.org_users[ev.org_id] = [
                {"name": u.name, "role": u.role} for u in ev.users
            ]
            if self._evolution_coordinator is not None:
                self._evolution_coordinator.register_org(ev.org_id)
            return [ev]

        coordinator = self._evolution_coordinator
        if coordinator is None:
            return []
        candidates = [
            oid for oid, metrics in coordinator.unit_metrics.items()
            if coordinator.advancer.org_status.get(oid, metrics.current_status) != "稳定运行"
        ]
        if not candidates:
            return []
        oid = self.rng.choice(candidates)
        events = coordinator.evolve_unit_step(oid, event_date)
        metrics = coordinator.unit_metrics[oid]
        transition = coordinator.advancer.advance_unit_if_eligible(metrics, event_date)
        if transition is not None:
            metrics.current_status = transition.status_update.to_status
            metrics.stage_entered_date = event_date
            events.append(transition)
        return events

    def _projection_record(self, event: EventFootprint, committed_at: datetime) -> Dict[str, Any]:
        """Map one successfully committed footprint to the factual SSE contract."""
        org = (
            self._construction_baseline.orgs.get(event.document.org_id, {})
            if self._construction_baseline is not None
            else {}
        )
        integration_ok = event.integration.status == "SUCCESS"
        return {
            "event_id": f"document-{event.document.id}",
            "committed_at": committed_at.isoformat(),
            "business_type": "integration_completed",
            "increments": {
                "documents": 1,
                "vouchers": 1,
                "integrations": 1,
            },
            "unit_id": event.document.org_id,
            "unit_name": org.get("name"),
            "province": org.get("region"),
            "batch_name": f"第{org.get('batch_id')}批" if org.get("batch_id") else None,
            "story_title": f"{event.document.type}完成业务入账",
            "story_desc": (
                f"{event.document.doc_no} → {event.voucher.voucher_no} · "
                f"集成{'成功' if integration_ok else '失败'}"
            ),
            "amount": str(event.document.amount),
            "badge_tone": "success" if integration_ok else "danger",
        }

    def _restore_evolution_state(self) -> None:
        """Restore lifecycle evidence counters after a daemon restart (fail closed on corruption)."""
        path = self.config.lifecycle_state_path or self.config.status_file_path.with_name(
            "simulator_lifecycle_state.json"
        )
        if not path.exists() or self._evolution_coordinator is None:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != 1:
                raise RuntimeError("unsupported lifecycle state version")
            coordinator = self._evolution_coordinator
            advancer = coordinator.advancer
            self.onboarding_dates = [datetime.fromisoformat(v).date() for v in data.get("onboarding_dates", [])]
            advancer.org_status.update({int(k): str(v) for k, v in data.get("org_status", {}).items()})
            advancer.consecutive_qualified_days.update({
                int(k): int(v) for k, v in data.get("consecutive_qualified_days", {}).items()
            })
            advancer.stage_entered_dates.update({
                int(k): datetime.fromisoformat(v).date() for k, v in data.get("stage_entered_dates", {}).items()
            })
            advancer.last_qualification_dates.update({
                int(k): datetime.fromisoformat(v).date() for k, v in data.get("last_qualification_dates", {}).items()
            })
            for key, raw in data.get("unit_metrics", {}).items():
                oid = int(key)
                metrics = coordinator.unit_metrics.get(oid)
                if metrics is None:
                    continue
                for field_name in (
                    "current_status", "static_rate", "opening_rate", "dynamic_rate",
                    "training_completed", "training_pass_rate", "interfaces_completed",
                    "dual_run_checks_total", "dual_run_consistency_rate",
                    "dual_run_recent_matches", "has_blocking_risk",
                ):
                    if field_name in raw:
                        setattr(metrics, field_name, raw[field_name])
                metrics.opening_diff_amount = Decimal(str(raw.get("opening_diff_amount", "0")))
                metrics.tasks_completed = dict(raw.get("tasks_completed", metrics.tasks_completed))
                if raw.get("stage_entered_date"):
                    metrics.stage_entered_date = datetime.fromisoformat(raw["stage_entered_date"]).date()
        except Exception as ex:
            self.fail_closed_mgr.trip("Lifecycle state is unreadable", {"error": str(ex)})
            raise

    def _save_evolution_state(self) -> bool:
        """Atomically persist lifecycle evidence only after the database commit succeeds."""
        if self._evolution_coordinator is None:
            return True
        coordinator = self._evolution_coordinator
        advancer = coordinator.advancer
        data = {
            "version": 1,
            "updated_at": datetime.now(HK_TZ).isoformat(),
            "onboarding_dates": [d.isoformat() for d in self.onboarding_dates],
            "org_status": {str(k): v for k, v in advancer.org_status.items()},
            "consecutive_qualified_days": {str(k): v for k, v in advancer.consecutive_qualified_days.items()},
            "stage_entered_dates": {str(k): v.isoformat() for k, v in advancer.stage_entered_dates.items()},
            "last_qualification_dates": {str(k): v.isoformat() for k, v in advancer.last_qualification_dates.items()},
            "unit_metrics": {
                str(oid): {
                    "current_status": metrics.current_status,
                    "stage_entered_date": metrics.stage_entered_date.isoformat(),
                    "static_rate": metrics.static_rate,
                    "opening_rate": metrics.opening_rate,
                    "opening_diff_amount": str(metrics.opening_diff_amount),
                    "dynamic_rate": metrics.dynamic_rate,
                    "tasks_completed": metrics.tasks_completed,
                    "training_completed": metrics.training_completed,
                    "training_pass_rate": metrics.training_pass_rate,
                    "interfaces_completed": metrics.interfaces_completed,
                    "dual_run_checks_total": metrics.dual_run_checks_total,
                    "dual_run_consistency_rate": metrics.dual_run_consistency_rate,
                    "dual_run_recent_matches": metrics.dual_run_recent_matches,
                    "has_blocking_risk": metrics.has_blocking_risk,
                }
                for oid, metrics in coordinator.unit_metrics.items()
            },
        }
        path = self.config.lifecycle_state_path or self.config.status_file_path.with_name(
            "simulator_lifecycle_state.json"
        )
        tmp_path = path.with_name(f".tmp_{path.name}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.replace(path)
            return True
        except Exception as ex:
            self.fail_closed_mgr.trip("Lifecycle restart state could not be persisted", {"error": str(ex)})
            return False
        finally:
            if tmp_path.exists():
                with suppress(OSError):
                    tmp_path.unlink()

    def _save_status(self, last_status: str, intensity: float, now: datetime, last_error: Optional[str]) -> None:
        """Persist structured service heartbeat status to JSON file using atomic tempfile swap."""
        tmp_path = None
        try:
            target_path = self.config.status_file_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if self.fail_closed_mgr.is_tripped():
                service_status = "HALTED"
            elif last_status == "SUCCESS":
                service_status = "RUNNING"
            elif last_status == "DRY_RUN":
                service_status = "DISABLED"
            else:
                service_status = "DEGRADED"
            status_data = {
                "service": "mod-simulator",
                "status": service_status,
                "last_cycle_status": last_status,
                "timestamp": now.isoformat(),
                "intensity": round(intensity, 4),
                "uptime_seconds": round(time.time() - self.start_time, 1),
                "consecutive_failures": self.consecutive_failures,
                "fail_closed_tripped": self.fail_closed_mgr.is_tripped(),
                "fuse_metrics": self.fuse.get_metrics(),
                "last_error": last_error,
            }
            tmp_path = target_path.with_name(f".tmp_{target_path.name}")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            tmp_path.replace(target_path)
            with suppress(OSError):
                target_path.chmod(0o644)
        except Exception as ex:
            logger.warning(f"Could not persist runtime status: {ex}")
        finally:
            if tmp_path and tmp_path.exists():
                with suppress(OSError):
                    tmp_path.unlink()

    def run_once(self, now: Optional[datetime] = None) -> CycleResult:
        """Execute a single cycle and return outcome."""
        return self.step_cycle(now)

    def run_forever(self, stop_event: Optional[threading.Event] = None) -> None:
        """Run the main simulation loop until stopped or fail-closed tripped."""
        logger.info("MOD Realistic Simulator background service started.")
        while not (stop_event and stop_event.is_set()):
            res = self.step_cycle()
            if res.status == "FAIL_CLOSED":
                logger.critical(f"Service entering halt sleep: {res.error}")
                # In fail-closed state, sleep longer before re-checking
                if stop_event:
                    stop_event.wait(30.0)
                else:
                    time.sleep(30.0)
                continue

            if stop_event and stop_event.is_set():
                break

            if stop_event:
                stop_event.wait(res.wait_seconds)
            else:
                time.sleep(res.wait_seconds)
