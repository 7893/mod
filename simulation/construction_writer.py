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
import gzip
from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional
import uuid

import pymysql

from .construction_models import (
    BatchRolloutEventFootprint,
    DataReadinessEventFootprint,
    DualRunCheckEventFootprint,
    InterfaceDebuggingEventFootprint,
    NewOrgAdmissionFootprint,
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
            # 本地开发可选加载 .env；缺少 python-dotenv 或文件不可读都不应阻断。
            with suppress(Exception):
                from dotenv import load_dotenv

                for env_file in [".env.systemd", ".env.local", ".env"]:
                    if os.path.exists(env_file):
                        load_dotenv(env_file)
                        break

        host = os.environ.get("MOD_DB_HOST", "127.0.0.1")
        port = int(os.environ.get("MOD_DB_PORT", "3306"))
        user = os.environ.get("MOD_DB_USER", "")
        password = os.environ.get("MOD_DB_PASSWORD", "")
        database = os.environ.get("MOD_DB_NAME", "mod")

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # secret-scan: allow
            database=database,
            autocommit=False,
            charset="utf8mb4",
        )

    def backup_affected_tables(
        self,
        tables: List[str],
        compress: bool = True,
        max_backups: Optional[int] = None,
        retention_days: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
        min_free_bytes: Optional[int] = None,
    ) -> str:
        """Create a safety snapshot backup of target tables before writing.

        Guarantees:
        1. Checks available disk space; raises RuntimeError if below min_free_bytes (fail closed).
        2. Compresses with gzip by default to prevent disk ballooning.
        3. Writes to temp file and atomically renames.
        4. Rotates backups enforcing 3-fold bounds: max_backups, retention_days, and max_total_bytes.
        5. Fails closed (raises RuntimeError) if rotation or limits cannot be satisfied.
        """
        if not self._backup_dir:
            self._backup_dir = Path("scripts/agy/output/backups")
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        if max_backups is None:
            max_backups = int(os.getenv("MOD_BACKUP_MAX_COPIES", "3"))
        if retention_days is None:
            retention_days = int(os.getenv("MOD_BACKUP_RETENTION_DAYS", "7"))
        if max_total_bytes is None:
            max_total_bytes = int(os.getenv("MOD_BACKUP_MAX_TOTAL_BYTES", str(200 * 1024 * 1024)))
        if min_free_bytes is None:
            min_free_bytes = int(os.getenv("MOD_BACKUP_MIN_FREE_BYTES", str(5 * 1024 * 1024 * 1024)))

        # 1. Disk space check (fail closed if free space < threshold)
        usage = shutil.disk_usage(self._backup_dir)
        if usage.free < min_free_bytes:
            raise RuntimeError(
                f"BLOCKED: Insufficient disk space for backup ({usage.free / (1024**3):.2f} GiB free, "
                f"{min_free_bytes / (1024**3):.2f} GiB required)."
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".json.gz" if compress else ".json"
        filename = f"construction_backup_{timestamp}{ext}"
        backup_path = self._backup_dir / filename
        temp_path = self._backup_dir / f".tmp_{filename}"

        conn = self._get_connection()
        backup_data: Dict[str, List[Dict[str, Any]]] = {}
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                for table in tables:
                    # Sanitize table names against allowed list
                    if table not in (
                        "org_unit",
                        "sys_user",
                        "construction_task",
                        "rollout_batch",
                        "rollout_status_snapshot",
                        "data_readiness",
                        "training",
                        "dual_run_result",
                        "daily_stats",
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

            if compress:
                with gzip.open(temp_path, "wt", encoding="utf-8") as f:
                    json.dump(backup_data, f, ensure_ascii=False)
            else:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)

            # Atomic swap
            temp_path.replace(backup_path)
            logger.info(f"Backup created successfully: {backup_path}")

            # Enforce 3-fold bounds (fail-closed if pruning fails)
            try:
                self._rotate_backups(
                    max_backups=max_backups,
                    retention_days=retention_days,
                    max_total_bytes=max_total_bytes,
                )
            except Exception as rot_ex:
                if backup_path.exists():
                    with suppress(OSError):
                        backup_path.unlink()
                raise RuntimeError(f"Backup rotation enforcement failed (fail-closed): {rot_ex}") from rot_ex

            return str(backup_path)
        finally:
            if temp_path.exists():
                with suppress(OSError):
                    temp_path.unlink()
            if not self._external_conn:
                conn.close()

    def _rotate_backups(
        self,
        max_backups: int = 3,
        retention_days: int = 7,
        max_total_bytes: int = 200 * 1024 * 1024,
    ) -> None:
        """Enforce 3-fold bounds on backups: copies, retention days, and total directory bytes.

        Guarantees:
        1. Never deletes the sole remaining backup file.
        2. Raises RuntimeError (fail closed) if an unlinked file cannot be deleted or bounds exceeded.
        """
        if not self._backup_dir or not self._backup_dir.exists():
            return

        existing = [
            p
            for p in self._backup_dir.iterdir()
            if p.is_file()
            and p.name.startswith("construction_backup_")
            and (p.name.endswith(".json") or p.name.endswith(".json.gz"))
        ]
        if not existing:
            return

        # Sort newest first
        existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # 1. Retention Days check (never delete sole remaining backup)
        now_ts = time.time()
        cutoff_ts = now_ts - (retention_days * 86400.0)
        for old_path in list(existing[1:]):
            try:
                if old_path.stat().st_mtime < cutoff_ts:
                    old_path.unlink()
                    existing.remove(old_path)
                    logger.info(f"Rotated expired backup beyond {retention_days} days: {old_path.name}")
            except Exception as ex:
                raise RuntimeError(f"Failed to delete expired backup {old_path}: {ex}") from ex

        # 2. Max Backups Count check (never delete sole remaining backup)
        if max_backups > 0 and len(existing) > max_backups:
            to_delete = existing[max_backups:]
            for old_path in to_delete:
                if len(existing) <= 1:
                    break
                try:
                    old_path.unlink()
                    existing.remove(old_path)
                    logger.info(f"Rotated excess backup beyond {max_backups} copies: {old_path.name}")
                except Exception as ex:
                    raise RuntimeError(f"Failed to delete excess backup {old_path}: {ex}") from ex

        # 3. Max Total Bytes check (never delete sole remaining backup)
        if max_total_bytes > 0:
            total_bytes = sum(p.stat().st_size for p in existing)
            while total_bytes > max_total_bytes and len(existing) > 1:
                oldest = existing[-1]
                try:
                    oldest.unlink()
                    existing.pop()
                    logger.info(
                        f"Rotated backup {oldest.name} to enforce max_total_bytes ({max_total_bytes} bytes)"
                    )
                except Exception as ex:
                    raise RuntimeError(
                        f"Failed to delete backup to enforce capacity limit {oldest}: {ex}"
                    ) from ex
                total_bytes = sum(p.stat().st_size for p in existing)

        # 4. Final verification
        final_count = len(existing)
        final_bytes = sum(p.stat().st_size for p in existing)
        if max_backups > 0 and final_count > max_backups:
            raise RuntimeError(f"Backup capacity breach: {final_count} copies exceed max_backups {max_backups}")
        if max_total_bytes > 0 and final_bytes > max_total_bytes:
            raise RuntimeError(
                f"Backup capacity breach: {final_bytes} bytes exceed max_total_bytes {max_total_bytes}"
            )

    def record_success_audit(
        self,
        result: Any,
        run_id: Optional[str] = None,
    ) -> None:
        """Explicitly record SUCCESS audit entry when transaction is committed."""
        audit_entry = {
            "run_id": run_id or f"c_sim_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().isoformat(),
            "event_count": getattr(result, "event_count", 0),
            "rows_written": getattr(result, "rows_written", {}),
            "backup_file": getattr(result, "backup_file", None),
            "status": "SUCCESS",
            "duration_ms": getattr(result, "duration_ms", 0.0),
        }
        self._record_audit(audit_entry)

    def record_failure_audit(
        self,
        error: str,
        event_count: int = 0,
        run_id: Optional[str] = None,
        backup_file: Optional[str] = None,
    ) -> None:
        """Explicitly record FAILED audit entry when transaction is rolled back."""
        audit_entry = {
            "run_id": run_id or f"c_sim_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().isoformat(),
            "event_count": event_count,
            "rows_written": {
                "org_unit": 0,
                "sys_user": 0,
                "rollout_status_snapshot": 0,
                "data_readiness": 0,
                "training": 0,
                "dual_run_result": 0,
                "construction_task": 0,
                "rollout_batch": 0,
                "daily_stats": 0,
            },
            "backup_file": backup_file,
            "status": "FAILED",
            "error": error,
            "duration_ms": 0.0,
        }
        self._record_audit(audit_entry)

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
        create_backup: bool = False,
        auto_commit: bool = True,
    ) -> ConstructionWriteResult:
        """Atomically write a collection of construction event footprints in batches.

        Guarantees:
        1. Single-transaction atomicity: All events across all batches commit together at the end.
           Zero intermediate commits occur inside the batch loop.
        2. If any SQL or batch fails, the entire transaction is rolled back with zero committed rows.
        3. Audit log reports SUCCESS only after successful final commit; on failure reports zero committed rows.
        4. auto_commit=False allows the caller (e.g. resident runtime service) to own the transaction
           and execute post-write assertions before final commit.
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

        # 0. Short-circuit if no events: zero DB connection, zero backup, zero audit
        if not events:
            return ConstructionWriteResult(
                success=True,
                event_count=0,
                rows_written={},
                error=None,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # 1. Deterministic validation of all events in memory
        for ev in events:
            validate_construction_event(ev)

        # 2. Pre-write backup (only if explicitly requested)
        backup_file: Optional[str] = None
        if create_backup:
            backup_file = self.backup_affected_tables(
                [
                    "org_unit",
                    "sys_user",
                    "rollout_status_snapshot",
                    "data_readiness",
                    "training",
                    "dual_run_result",
                    "construction_task",
                    "rollout_batch",
                    "daily_stats",
                ]
            )

        conn = self._get_connection()
        rows_written = {
            "org_unit": 0,
            "sys_user": 0,
            "rollout_status_snapshot": 0,
            "data_readiness": 0,
            "training": 0,
            "dual_run_result": 0,
            "construction_task": 0,
            "rollout_batch": 0,
            "daily_stats": 0,
        }

        try:
            with conn.cursor() as cursor:
                # Stage in batches without intermediate commit
                total_batches = (len(events) + batch_size - 1) // batch_size if events else 1
                for b_idx in range(total_batches):
                    chunk = events[b_idx * batch_size : (b_idx + 1) * batch_size]
                    batch_rows_start = sum(rows_written.values())
                    for ev in chunk:
                        self._write_single_event(cursor, ev, rows_written)
                    batch_rows_end = sum(rows_written.values())
                    batch_rows = batch_rows_end - batch_rows_start
                    pct = (b_idx + 1) / total_batches * 100
                    logger.info(
                        f"[{run_id}] Staged batch {b_idx + 1}/{total_batches} ({pct:.1f}%): "
                        f"{len(chunk)} events, {batch_rows} rows. Total staged: {batch_rows_end}."
                    )

            duration = (time.perf_counter() - t0) * 1000
            if auto_commit:
                conn.commit()
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
            with suppress(Exception):
                conn.rollback()
            duration = (time.perf_counter() - t0) * 1000
            err_msg = f"Rolled back batch: {ex}"
            logger.error(f"[{run_id}] Write failed: {err_msg}")
            zero_rows = {k: 0 for k in rows_written}
            audit_entry = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "event_count": len(events),
                "rows_written": zero_rows,
                "backup_file": backup_file,
                "status": "FAILED",
                "error": err_msg,
                "duration_ms": duration,
            }
            self._record_audit(audit_entry)
            return ConstructionWriteResult(
                success=False,
                event_count=len(events),
                rows_written=zero_rows,
                backup_file=backup_file,
                error=err_msg,
                duration_ms=duration,
            )
        finally:
            if auto_commit and not self._external_conn:
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
        if isinstance(ev, NewOrgAdmissionFootprint):
            # 1. Insert into org_unit
            cursor.execute(
                """
                INSERT INTO org_unit (id, name, batch_id, status, region, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (ev.org_id, ev.name, ev.batch_id, ev.status, ev.region, ev.start_date, ev.end_date),
            )
            rows_written["org_unit"] += 1

            # 2. Insert users into sys_user
            for u in ev.users:
                cursor.execute(
                    """
                    INSERT INTO sys_user (id, name, org_id, role, job)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (u.id, u.name, u.org_id, u.role, u.job),
                )
                rows_written["sys_user"] += 1

            # 3. Insert tasks into construction_task
            for t in ev.tasks:
                self._upsert_task(cursor, t, rows_written)

            # 4. Insert data_readiness
            if ev.readiness:
                r = ev.readiness
                cursor.execute(
                    """
                    INSERT INTO data_readiness (
                        org_id, batch_id, static_total, static_completed, static_rate,
                        opening_total, opening_completed, opening_rate, opening_diff_amount,
                        dynamic_total, dynamic_completed, dynamic_sync_success, dynamic_sync_fail,
                        dynamic_sync_pending, dynamic_rate, last_sync_time, overall_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        r.org_id, r.batch_id, r.static_total, r.static_completed, r.static_rate,
                        r.opening_total, r.opening_completed, r.opening_rate, r.opening_diff_amount,
                        r.dynamic_total, r.dynamic_completed, r.dynamic_sync_success, r.dynamic_sync_fail,
                        r.dynamic_sync_pending, r.dynamic_rate, r.last_sync_time, r.overall_status,
                    ),
                )
                rows_written["data_readiness"] += 1

            # 5. Insert rollout_status_snapshot
            if ev.snapshot:
                cursor.execute(
                    """
                    INSERT INTO rollout_status_snapshot (org_id, snapshot_date, status)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status);
                    """,
                    (ev.snapshot.org_id, ev.snapshot.snapshot_date, ev.snapshot.status),
                )
                rows_written["rollout_status_snapshot"] += 1

            # 6. Synchronously cascade update daily_stats
            cursor.execute(
                """
                UPDATE daily_stats
                SET org_count = org_count + 1,
                    user_count = user_count + %s
                WHERE stat_date >= %s;
                """,
                (len(ev.users), ev.start_date),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    UPDATE daily_stats
                    SET org_count = org_count + 1,
                        user_count = user_count + %s
                    ORDER BY stat_date DESC LIMIT 1;
                    """,
                    (len(ev.users),),
                )
            rows_written["daily_stats"] += 1

        elif isinstance(ev, PoolOnboardingEventFootprint):
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
