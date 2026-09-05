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
from .construction_models import validate_construction_event
from .construction_playbooks import (
    DualRunCheckPlaybook,
    TrainingCertificationPlaybook,
)
from .construction_writer import ConstructionWriter
from .engine_context import (
    IdAllocator,
    load_construction_baseline,
    load_simulation_baseline,
)
from .expense_playbook import ExpensePlaybook
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
    status_file_path: Path = field(default_factory=lambda: Path("output/simulator_status.json"))
    audit_log_path: Path = field(default_factory=lambda: Path("output/simulation_audit.log"))
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
    """Sliding rate limiter with minute and daily hard caps."""

    def __init__(self, max_per_minute: int = 20, max_per_day: int = 5000):
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day
        self._current_minute = ""
        self._minute_count = 0
        self._current_day = ""
        self._day_count = 0

    def can_produce(self, now: datetime, count: int = 1) -> Tuple[bool, str]:
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        day_key = now.strftime("%Y-%m-%d")

        minute_count = self._minute_count if minute_key == self._current_minute else 0
        day_count = self._day_count if day_key == self._current_day else 0

        if minute_count + count > self.max_per_minute:
            return False, f"Minute hard cap reached ({minute_count}/{self.max_per_minute})"

        if day_count + count > self.max_per_day:
            return False, f"Daily hard cap reached ({day_count}/{self.max_per_day})"

        return True, ""

    def record(self, now: datetime, count: int = 1) -> None:
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        day_key = now.strftime("%Y-%m-%d")

        if minute_key != self._current_minute:
            self._current_minute = minute_key
            self._minute_count = 0
        self._minute_count += count

        if day_key != self._current_day:
            self._current_day = day_key
            self._day_count = 0
        self._day_count += count

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "minute_count": self._minute_count,
            "max_per_minute": self.max_per_minute,
            "day_count": self._day_count,
            "max_per_day": self.max_per_day,
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
    ):
        self.config = config or SimulatorRuntimeConfig()
        self._external_conn = conn
        self.rng = random.Random(seed)
        self.fail_closed_mgr = FailClosedManager(self.config.fail_closed_flag_path, self.config.audit_log_path)
        self.fuse = RateLimitFuse(self.config.max_events_per_minute, self.config.max_events_per_day)
        self.consecutive_failures = 0
        self.cycle_count = 0
        self.start_time = time.time()

        # Cache baselines
        self._fast_baseline: Optional[Any] = None
        self._fast_allocator: Optional[IdAllocator] = None
        self._construction_baseline: Optional[Any] = None
        self._construction_allocator: Optional[IdAllocator] = None

    def _get_connection(self) -> Any:
        if self._external_conn:
            return self._external_conn

        host = os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST", "127.0.0.1")
        port = int(os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT", "3306"))
        user = os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER", "mod_v2_writer")
        password = os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD", "")
        database = os.getenv("MOD_DB_NAME") or os.getenv("MOD_V2_DB_NAME", "mod_s_v2")

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

        if self._construction_baseline is None or (self.cycle_count > 0 and self.cycle_count % 100 == 0):
            self._construction_baseline = load_construction_baseline(conn)
            self._construction_allocator = IdAllocator(self._construction_baseline.next_ids)

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

        # 3. Check Fuse Rate Limits
        can_produce, limit_reason = self.fuse.can_produce(now_hkt, burst_count)
        if not can_produce:
            logger.warning(f"[RATE_LIMIT_FUSE] {limit_reason}. Pausing cycle.")
            self._save_status("RATE_LIMITED", intensity, now_hkt, limit_reason)
            return CycleResult(
                status="RATE_LIMITED",
                events_written=0,
                wait_seconds=wait_seconds,
                intensity=intensity,
                error=limit_reason,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # 4. Check whether database writes are enabled
        engine_enabled = is_simulation_engine_enabled() and not self.config.dry_run

        conn = self._get_connection()
        try:
            self._ensure_baselines(conn)
            self.cycle_count += 1

            # Decide fast vs slow movie
            is_slow_movie = (self.cycle_count % self.config.slow_movie_interval_cycles == 0) and burst_count > 0

            if is_slow_movie:
                # Generate slow-movie construction event
                c_event = self._generate_slow_movie_event(now_hkt.date())
                all_events: List[object] = [c_event] if c_event else []
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

            if not engine_enabled:
                # Dry-run / Idle mode: zero database modifications
                logger.info(
                    f"[DRY-RUN TICK] {now_hkt.strftime('%Y-%m-%d %H:%M:%S')} HKT | "
                    f"Intensity: {intensity:.3f} | Burst: {len(all_events)} events | DB Write: DISABLED"
                )
                self.fuse.record(now_hkt, len(all_events))
                self._save_status("DRY_RUN", intensity, now_hkt, None)
                return CycleResult(
                    status="DRY_RUN",
                    events_written=0,
                    wait_seconds=wait_seconds,
                    intensity=intensity,
                    cycle_duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # 5. Real Atomic Write Execution
            if is_construction:
                c_writer = ConstructionWriter(conn=conn, audit_log_path=str(self.config.audit_log_path))
                c_res = c_writer.write_construction_events(all_events, execute=True)
                if not c_res.success:
                    raise RuntimeError(f"Construction write failed: {c_res.error}")

                ok, chk_err = PostCycleSelfChecker.check_construction_events(conn, all_events)
                if not ok:
                    raise RuntimeError(f"Post-cycle construction self-check failed: {chk_err}")
                events_written = len(all_events)
            else:
                s_writer = SimulationWriter(conn=conn, audit_log_path=str(self.config.audit_log_path))
                s_res = s_writer.write_events(all_events)  # type: ignore
                if not s_res.success:
                    raise RuntimeError(f"Fast-movie write failed: {s_res.error}")

                ok, chk_err = PostCycleSelfChecker.check_fast_movie_events(conn, all_events)  # type: ignore
                if not ok:
                    conn.rollback()
                    raise RuntimeError(f"Post-cycle fast-movie self-check failed: {chk_err}")
                events_written = len(all_events)

            # Success: reset consecutive failures & record fuse
            self.consecutive_failures = 0
            self.fuse.record(now_hkt, events_written)
            self._save_status("SUCCESS", intensity, now_hkt, None)

            return CycleResult(
                status="SUCCESS",
                events_written=events_written,
                wait_seconds=wait_seconds,
                intensity=intensity,
                cycle_duration_ms=(time.perf_counter() - t0) * 1000,
            )

        except Exception as ex:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

            self.consecutive_failures += 1
            err_msg = str(ex)
            logger.error(
                f"[CYCLE ERROR] Consecutive failure {self.consecutive_failures}/"
                f"{self.config.consecutive_failure_threshold}: {err_msg}"
            )

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
            if not self._external_conn and conn:
                conn.close()

    def _generate_slow_movie_event(self, event_date: Any) -> Optional[object]:
        """Generate an eligible slow-movie construction event based on current baseline."""
        if not self._construction_baseline:
            return None

        # Try DualRunCheck for active dual-run org
        dual_orgs = self._construction_baseline.orgs_by_status.get("双轨运行中", [])
        if dual_orgs:
            oid = self.rng.choice(dual_orgs)
            pb = DualRunCheckPlaybook(self._construction_baseline, seed=self.rng.randint(1, 100000))
            return pb.generate(org_id=oid, event_date=event_date, id_allocator=self._construction_allocator)

        # Fallback to Training
        prep_orgs = self._construction_baseline.orgs_by_status.get("准备中", [])
        if prep_orgs:
            oid = self.rng.choice(prep_orgs)
            pb_train = TrainingCertificationPlaybook(self._construction_baseline, seed=self.rng.randint(1, 100000))
            return pb_train.generate(org_id=oid, event_date=event_date, id_allocator=self._construction_allocator)

        return None

    def _save_status(self, last_status: str, intensity: float, now: datetime, last_error: Optional[str]) -> None:
        """Persist structured service heartbeat status to JSON file."""
        try:
            self.config.status_file_path.parent.mkdir(parents=True, exist_ok=True)
            status_data = {
                "service": "mod-simulator",
                "status": "HALTED" if self.fail_closed_mgr.is_tripped() else ("RUNNING" if last_status != "ERROR" else "DEGRADED"),
                "last_cycle_status": last_status,
                "timestamp": now.isoformat(),
                "intensity": round(intensity, 4),
                "uptime_seconds": round(time.time() - self.start_time, 1),
                "consecutive_failures": self.consecutive_failures,
                "fail_closed_tripped": self.fail_closed_mgr.is_tripped(),
                "fuse_metrics": self.fuse.get_metrics(),
                "last_error": last_error,
            }
            with open(self.config.status_file_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            logger.warning(f"Could not persist runtime status: {ex}")

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
                time.sleep(30.0)
                continue

            if stop_event and stop_event.is_set():
                break

            time.sleep(res.wait_seconds)
