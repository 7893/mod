"""Transactional writer for construction lifecycle events with safety gates and audit trail.

Enforces:
1. MOD_SIMULATION_ENGINE_ENABLED gate (fails closed if not explicitly enabled).
2. Zero schema changes (INSERT / controlled UPDATE on existing tables only).
3. Transaction atomicity: multi-table rows for an event commit together or roll back.
4. Pre-write backup mechanism.
5. Batch commit with progress logging.
6. Structured audit trail logging to output/construction_audit.log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

import pymysql

from .construction_models import (
    BatchRolloutEventFootprint,
    DataReadinessEventFootprint,
    DualRunCheckEventFootprint,
    InterfaceDebuggingEventFootprint,
    PoolOnboardingEventFootprint,
    TrainingCertificationEventFootprint,
    TransitionReviewEventFootprint,
    validate_construction_event,
)

logger = logging.getLogger(__name__)
_TRUE_VALUES = frozenset({"true", "1", "yes"})


def is_construction_writer_enabled() -> bool:
    """Strictly verify if simulation engine writes are allowed by environment."""
    val = os.environ.get("MOD_SIMULATION_ENGINE_ENABLED", "").strip().lower()
    return val in _TRUE_VALUES


@dataclass
class ConstructionWriteResult:
    """Outcome of a construction write operation."""

    success: bool
    event_count: int
    rows_written: Dict[str, int]
    backup_file: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class ConstructionWriter:
    """Append-only / controlled-update transactional writer for construction events."""

    def __init__(
        self,
        conn: Optional[Any] = None,
        audit_log_path: Optional[str] = "output/construction_audit.log",
        backup_dir: Optional[str] = "scripts/agy/output/backups",
    ):
        self._external_conn = conn
        self._audit_log_path = Path(audit_log_path) if audit_log_path else None
        self._backup_dir = Path(backup_dir) if backup_dir else None

    def _get_connection(self) -> Any:
        if self._external_conn:
            return self._external_conn

        if not os.environ.get("MOD_DB_HOST"):
            try:
                from dotenv import load_dotenv

                for env_file in [".env.systemd", ".env.local", ".env"]:
                    if os.path.exists(env_file):
                        load_dotenv(env_file)
                        break
            except Exception:
                pass

        host = os.environ.get("MOD_DB_HOST", "127.0.0.1")
        port = int(os.environ.get("MOD_DB_PORT", "3306"))
        user = os.environ.get("MOD_DB_USER", "")
        password = os.environ.get("MOD_DB_PASSWORD", "")
        database = os.environ.get("MOD_DB_NAME", "mod_s_v2")

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # secret-scan: allow
            database=database,
            autocommit=False,
            charset="utf8mb4",
        )

    def backup_affected_tables(self, tables: List[str]) -> str:
        """Create a safety snapshot backup of target tables before writing."""
        if not self._backup_dir:
            self._backup_dir = Path("scripts/agy/output/backups")
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"construction_backup_{timestamp}.json"

        conn = self._get_connection()
        backup_data: Dict[str, List[Dict[str, Any]]] = {}
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                for table in tables:
                    # Sanitize table names against allowed list
                    if table not in (
                        "org_unit",
                        "construction_task",
                        "rollout_batch",
                        "rollout_status_snapshot",
                        "data_readiness",
                        "training",
                        "dual_run_result",
                    ):
                        raise ValueError(f"Unauthorized table backup request: {table}")
                    cursor.execute(f"SELECT * FROM {table};")  # noqa: S608
                    rows = cursor.fetchall()
                    # Convert dates and Decimals for serialization
                    serialized_rows = []
                    for r in rows:
                        sr = {}
                        for k, v in r.items():
                            sr[k] = str(v) if v is not None else None
                        serialized_rows.append(sr)
                    backup_data[table] = serialized_rows

            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Backup created successfully: {backup_path}")
            return str(backup_path)
        finally:
            if not self._external_conn:
                conn.close()

    def _record_audit(self, audit: Dict[str, Any]) -> None:
        """Write structured audit record to local JSONL log file."""
        if not self._audit_log_path:
            return
        try:
            self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit, ensure_ascii=False) + "\n")
        except Exception as ex:  # noqa: BLE001
            logger.warning(f"Failed to write construction audit log: {ex}")

    def write_construction_events(
        self,
        events: List[object],
        batch_size: int = 500,
        execute: bool = False,
    ) -> ConstructionWriteResult:
        """
        Atomically write a collection of construction event footprints in batches.

        Requires:
        1. execute=True AND MOD_SIMULATION_ENGINE_ENABLED=true.
        2. Strict validation of every event before any write.
        3. Automatic pre-write backup.
        """
        run_id = f"c_sim_{uuid.uuid4().hex[:12]}"
        t0 = time.perf_counter()

        if not execute or not is_construction_writer_enabled():
            return ConstructionWriteResult(
                success=False,
                event_count=len(events),
                rows_written={},
                error="BLOCKED: Construction writing disabled (requires MOD_SIMULATION_ENGINE_ENABLED=true and execute=True).",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # 1. Deterministic validation of all events in memory
        for ev in events:
            validate_construction_event(ev)

        # 2. Pre-write backup
        backup_file = self.backup_affected_tables(
            [
                "org_unit",
                "rollout_status_snapshot",
                "data_readiness",
                "training",
                "dual_run_result",
                "construction_task",
                "rollout_batch",
            ]
        )

        conn = self._get_connection()
        rows_written = {
            "org_unit": 0,
            "rollout_status_snapshot": 0,
            "data_readiness": 0,
            "training": 0,
            "dual_run_result": 0,
            "construction_task": 0,
            "rollout_batch": 0,
        }

        try:
            with conn.cursor() as cursor:
                # Write in batches
                total_batches = (len(events) + batch_size - 1) // batch_size if events else 1
                for b_idx in range(total_batches):
                    chunk = events[b_idx * batch_size : (b_idx + 1) * batch_size]
                    batch_rows_start = sum(rows_written.values())
                    for ev in chunk:
                        self._write_single_event(cursor, ev, rows_written)
                    conn.commit()
                    batch_rows_end = sum(rows_written.values())
                    batch_rows = batch_rows_end - batch_rows_start
                    pct = (b_idx + 1) / total_batches * 100
                    logger.info(
                        f"[{run_id}] Committed batch {b_idx + 1}/{total_batches} ({pct:.1f}%): "
                        f"{len(chunk)} events, {batch_rows} rows. Total written: {batch_rows_end}."
                    )

            duration = (time.perf_counter() - t0) * 1000
            audit_entry = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "event_count": len(events),
                "rows_written": rows_written,
                "backup_file": backup_file,
                "status": "SUCCESS",
                "duration_ms": duration,
            }
            self._record_audit(audit_entry)
            return ConstructionWriteResult(
                success=True,
                event_count=len(events),
                rows_written=rows_written,
                backup_file=backup_file,
                duration_ms=duration,
            )

        except Exception as ex:
            conn.rollback()
            duration = (time.perf_counter() - t0) * 1000
            err_msg = f"Rolled back batch: {ex}"
            logger.error(f"[{run_id}] Write failed: {err_msg}")
            audit_entry = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "event_count": len(events),
                "rows_written": rows_written,
                "backup_file": backup_file,
                "status": "FAILED",
                "error": err_msg,
                "duration_ms": duration,
            }
            self._record_audit(audit_entry)
            return ConstructionWriteResult(
                success=False,
                event_count=len(events),
                rows_written=rows_written,
                backup_file=backup_file,
                error=err_msg,
                duration_ms=duration,
            )
        finally:
            if not self._external_conn:
                conn.close()

    def _upsert_task(
        self,
        cursor: Any,
        t: Any,
        rows_written: Dict[str, int],
    ) -> None:
        """Insert or update a construction task safely."""
        cursor.execute(
            """
            INSERT INTO construction_task
            (id, org_id, name, type, owner, plan_time, actual_time, status, progress, update_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status = VALUES(status), progress = VALUES(progress),
                                   actual_time = VALUES(actual_time), update_time = VALUES(update_time);
            """,
            (
                t.id,
                t.org_id,
                t.name,
                t.type,
                t.owner,
                t.plan_time,
                t.actual_time,
                t.status,
                t.progress,
                t.update_time,
            ),
        )
        rows_written["construction_task"] += 1

    def _write_single_event(
        self,
        cursor: Any,
        ev: object,
        rows_written: Dict[str, int],
    ) -> None:
        """Dispatch and insert/update rows for an individual validated event."""
        if isinstance(ev, PoolOnboardingEventFootprint):
            # Update org_unit
            cursor.execute(
                "UPDATE org_unit SET status = %s WHERE id = %s;",
                (ev.status_update.to_status, ev.status_update.id),
            )
            rows_written["org_unit"] += cursor.rowcount

            # Insert / update snapshot
            cursor.execute(
                """
                INSERT INTO rollout_status_snapshot (org_id, snapshot_date, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status);
                """,
                (ev.snapshot.org_id, ev.snapshot.snapshot_date, ev.snapshot.status),
            )
            rows_written["rollout_status_snapshot"] += 1

            # Insert tasks
            for t in ev.initial_tasks:
                self._upsert_task(cursor, t, rows_written)

        elif isinstance(ev, DataReadinessEventFootprint):
            r = ev.readiness
            cursor.execute(
                """
                UPDATE data_readiness SET
                    static_total = %s, static_completed = %s, static_rate = %s,
                    opening_total = %s, opening_completed = %s, opening_rate = %s, opening_diff_amount = %s,
                    dynamic_total = %s, dynamic_completed = %s, dynamic_sync_success = %s,
                    dynamic_sync_fail = %s, dynamic_sync_pending = %s, dynamic_rate = %s,
                    overall_status = %s, last_sync_time = %s
                WHERE org_id = %s;
                """,
                (
                    r.static_total,
                    r.static_completed,
                    r.static_rate,
                    r.opening_total,
                    r.opening_completed,
                    r.opening_rate,
                    r.opening_diff_amount,
                    r.dynamic_total,
                    r.dynamic_completed,
                    r.dynamic_sync_success,
                    r.dynamic_sync_fail,
                    r.dynamic_sync_pending,
                    r.dynamic_rate,
                    r.overall_status,
                    r.last_sync_time,
                    r.org_id,
                ),
            )
            rows_written["data_readiness"] += cursor.rowcount
            if getattr(ev, "associated_task", None):
                self._upsert_task(cursor, ev.associated_task, rows_written)

        elif isinstance(ev, TrainingCertificationEventFootprint):
            t = ev.training
            cursor.execute(
                """
                INSERT INTO training
                (id, org_id, batch_id, type, date, mode, expected, actual, absent, passed, makeup, cert_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    t.id,
                    t.org_id,
                    t.batch_id,
                    t.type,
                    t.date,
                    t.mode,
                    t.expected,
                    t.actual,
                    t.absent,
                    t.passed,
                    t.makeup,
                    t.cert_count,
                ),
            )
            rows_written["training"] += 1
            if getattr(ev, "associated_task", None):
                self._upsert_task(cursor, ev.associated_task, rows_written)

        elif isinstance(ev, InterfaceDebuggingEventFootprint):
            self._upsert_task(cursor, ev.task, rows_written)

        elif isinstance(ev, DualRunCheckEventFootprint):
            dr = ev.dual_run
            cursor.execute(
                """
                INSERT INTO dual_run_result
                (id, org_id, check_type, v1_amount, v2_amount, diff_amount, result, check_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    dr.id,
                    dr.org_id,
                    dr.check_type,
                    dr.v1_amount,
                    dr.v2_amount,
                    dr.diff_amount,
                    dr.result,
                    dr.check_date,
                ),
            )
            rows_written["dual_run_result"] += 1
            if getattr(ev, "associated_task", None):
                self._upsert_task(cursor, ev.associated_task, rows_written)

        elif isinstance(ev, TransitionReviewEventFootprint):
            # Update org_unit status
            cursor.execute(
                "UPDATE org_unit SET status = %s WHERE id = %s;",
                (ev.to_status, ev.org_id),
            )
            rows_written["org_unit"] += cursor.rowcount

            # Insert snapshot
            cursor.execute(
                """
                INSERT INTO rollout_status_snapshot (org_id, snapshot_date, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status);
                """,
                (ev.snapshot.org_id, ev.snapshot.snapshot_date, ev.snapshot.status),
            )
            rows_written["rollout_status_snapshot"] += 1

        elif isinstance(ev, BatchRolloutEventFootprint):
            b = ev.batch_update
            cursor.execute(
                "UPDATE rollout_batch SET status = %s WHERE id = %s;",
                (b.status, b.id),
            )
            rows_written["rollout_batch"] += cursor.rowcount
