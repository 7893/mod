"""Transactional writer for realistic business simulation engine with strict safety gates."""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymysql

from .footprint_models import EventFootprint, SimulationAuditRecord, validate_footprint
from .daily_stats import add_daily_delta, apply_daily_deltas

logger = logging.getLogger(__name__)

_TRUE_VALUES = frozenset({"true", "1", "yes"})


def is_simulation_engine_enabled() -> bool:
    """Strictly verify if simulation engine writes are allowed by environment."""
    val = os.environ.get("MOD_SIMULATION_ENGINE_ENABLED", "").strip().lower()
    return val in _TRUE_VALUES


@dataclass
class WriteResult:
    """Outcome of a batch simulation write operation."""
    success: bool
    event_count: int
    rows_written: Dict[str, int]
    error: Optional[str] = None
    duration_ms: float = 0.0


class SimulationWriter:
    """
    Append-only transactional writer for simulation footprints.

    Enforces:
    1. MOD_SIMULATION_ENGINE_ENABLED gate (fails closed if not true).
    2. Zero schema changes (INSERT only on detail tables, locked UPDATE/INSERT on daily_stats).
    3. Transaction atomicity: all multi-table rows for the batch commit or all rollback.
    4. Audit trail logging to structured JSONL file.
    5. Cascade consistency with daily_stats.
    """

    def __init__(
        self,
        conn: Optional[Any] = None,
        audit_log_path: Optional[str] = "output/simulation_audit.log",
    ):
        self._external_conn = conn
        self._audit_log_path = Path(audit_log_path) if audit_log_path else None

    def _get_connection(self) -> Any:
        if self._external_conn:
            return self._external_conn

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

    def _record_audit(self, audit: SimulationAuditRecord) -> None:
        """Write audit record to local JSONL log file without raising exceptions."""
        if not self._audit_log_path:
            return
        try:
            self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(audit), ensure_ascii=False) + "\n")
        except Exception as ex:  # noqa: BLE001
            logger.warning(f"Failed to record simulation audit trail: {ex}")

    def record_success_audit(self, result: Any, run_id: Optional[str] = None) -> None:
        """Explicitly record SUCCESS audit entry when caller commits transaction."""
        audit = SimulationAuditRecord(
            run_id=run_id or f"sim_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now().isoformat(),
            business_type="费用报销",
            event_count=getattr(result, "event_count", 0),
            rows_written=getattr(result, "rows_written", {}),
            status="SUCCESS",
            duration_ms=getattr(result, "duration_ms", 0.0),
        )
        self._record_audit(audit)

    def record_failure_audit(self, error: str, event_count: int = 0, run_id: Optional[str] = None) -> None:
        """Explicitly record ROLLED_BACK audit entry when transaction is rolled back."""
        audit = SimulationAuditRecord(
            run_id=run_id or f"sim_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now().isoformat(),
            business_type="费用报销",
            event_count=event_count,
            rows_written={},
            status="ROLLED_BACK",
            error=error,
            duration_ms=0.0,
        )
        self._record_audit(audit)

    def write_events(self, events: List[EventFootprint], auto_commit: bool = True) -> WriteResult:
        """
        Atomically write a list of business event footprints.

        All events are validated and inserted inside a single transaction.
        If any failure occurs, entire batch is rolled back.
        """
        run_id = f"sim_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        if not is_simulation_engine_enabled():
            audit = SimulationAuditRecord(
                run_id=run_id,
                timestamp=datetime.now().isoformat(),
                business_type="费用报销",
                event_count=len(events),
                rows_written={},
                status="BLOCKED",
                error="MOD_SIMULATION_ENGINE_ENABLED is not enabled (fail-closed)",
                duration_ms=0.0,
            )
            self._record_audit(audit)
            raise RuntimeError(
                "Simulation write rejected: MOD_SIMULATION_ENGINE_ENABLED is not enabled."
            )

        if not events:
            return WriteResult(success=True, event_count=0, rows_written={})

        # Pre-validate all footprints before any DB action
        for idx, event in enumerate(events):
            try:
                validate_footprint(event)
            except Exception as e:
                raise ValueError(f"Event at index {idx} failed footprint validation: {e}") from e

        conn = self._get_connection()
        rows_written = {
            "business_document": 0,
            "business_document_line": 0,
            "accounting_voucher": 0,
            "accounting_voucher_line": 0,
            "document_voucher_link": 0,
            "integration_result": 0,
            "daily_stats": 0,
        }

        try:
            cursor = conn.cursor()

            # 1. Prepare batch parameters
            doc_rows = []
            doc_line_rows = []
            vch_rows = []
            vch_line_rows = []
            link_rows = []
            integ_rows = []

            # Aggregations for daily_stats by date
            date_deltas: Dict[Any, Dict[str, int]] = {}

            for event in events:
                doc = event.document
                vch = event.voucher
                link = event.link
                integ = event.integration

                doc_rows.append((
                    doc.id, doc.org_id, doc.type, doc.doc_no, doc.applicant,
                    doc.nature, doc.amount, doc.submit_time, doc.approve_time, doc.status
                ))
                for line in doc.lines:
                    doc_line_rows.append((
                        line.id, line.doc_id, line.item_name, line.amount, line.quantity
                    ))

                vch_rows.append((
                    vch.id, vch.org_id, vch.voucher_no, vch.type, vch.gen_time,
                    vch.int_time, vch.status, vch.debit, vch.credit
                ))
                for vl in vch.lines:
                    vch_line_rows.append((
                        vl.id, vl.voucher_id, vl.subject_code, vl.subject_name,
                        vl.debit, vl.credit
                    ))

                link_rows.append((link.doc_id, link.voucher_id))
                integ_rows.append((
                    integ.id, integ.voucher_id, integ.status, integ.retry_count,
                    integ.error_code, integ.error_message, integ.integration_time
                ))

                add_daily_delta(
                    date_deltas,
                    doc.submit_time.date(),
                    docs=1,
                    doc_lines=len(doc.lines),
                )
                add_daily_delta(
                    date_deltas,
                    vch.gen_time.date(),
                    vouchers=1,
                    voucher_lines=len(vch.lines),
                    links=1,
                )
                add_daily_delta(
                    date_deltas,
                    integ.integration_time.date(),
                    integrations=1,
                    success=int(integ.status == "SUCCESS"),
                )

            # 2. Execute multi-row INSERTs
            cursor.executemany(
                "INSERT INTO business_document "
                "(id, org_id, type, doc_no, applicant, nature, amount, submit_time, approve_time, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                doc_rows,
            )
            rows_written["business_document"] = len(doc_rows)

            cursor.executemany(
                "INSERT INTO business_document_line "
                "(id, doc_id, item_name, amount, quantity) "
                "VALUES (%s, %s, %s, %s, %s);",
                doc_line_rows,
            )
            rows_written["business_document_line"] = len(doc_line_rows)

            cursor.executemany(
                "INSERT INTO accounting_voucher "
                "(id, org_id, voucher_no, type, gen_time, int_time, status, debit, credit) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
                vch_rows,
            )
            rows_written["accounting_voucher"] = len(vch_rows)

            cursor.executemany(
                "INSERT INTO accounting_voucher_line "
                "(id, voucher_id, subject_code, subject_name, debit, credit) "
                "VALUES (%s, %s, %s, %s, %s, %s);",
                vch_line_rows,
            )
            rows_written["accounting_voucher_line"] = len(vch_line_rows)

            cursor.executemany(
                "INSERT INTO document_voucher_link (doc_id, voucher_id) VALUES (%s, %s);",
                link_rows,
            )
            rows_written["document_voucher_link"] = len(link_rows)

            cursor.executemany(
                "INSERT INTO integration_result "
                "(id, voucher_id, status, retry_count, error_code, error_message, integration_time) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s);",
                integ_rows,
            )
            rows_written["integration_result"] = len(integ_rows)

            # 3. Synchronously cascade by each record's actual business timestamp.
            rows_written["daily_stats"] = apply_daily_deltas(cursor, date_deltas)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            if auto_commit:
                conn.commit()
                audit = SimulationAuditRecord(
                    run_id=run_id,
                    timestamp=datetime.now().isoformat(),
                    business_type="费用报销",
                    event_count=len(events),
                    rows_written=rows_written,
                    status="SUCCESS",
                    duration_ms=round(duration_ms, 2),
                )
                self._record_audit(audit)

            return WriteResult(
                success=True,
                event_count=len(events),
                rows_written=rows_written,
                duration_ms=round(duration_ms, 2),
            )

        except Exception as ex:
            with suppress(Exception):
                conn.rollback()
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            audit = SimulationAuditRecord(
                run_id=run_id,
                timestamp=datetime.now().isoformat(),
                business_type="费用报销",
                event_count=len(events),
                rows_written={},
                status="ROLLED_BACK",
                error=str(ex),
                duration_ms=round(duration_ms, 2),
            )
            self._record_audit(audit)
            raise
        finally:
            if auto_commit and not self._external_conn:
                conn.close()
