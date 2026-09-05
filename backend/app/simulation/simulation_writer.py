"""Transactional writer for realistic business simulation engine with strict safety gates."""

from __future__ import annotations

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

    def write_events(self, events: List[EventFootprint]) -> WriteResult:
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

                stat_date = doc.submit_time.date()
                if stat_date not in date_deltas:
                    date_deltas[stat_date] = {
                        "docs": 0, "doc_lines": 0, "vouchers": 0,
                        "voucher_lines": 0, "links": 0, "integrations": 0,
                        "success": 0,
                    }
                date_deltas[stat_date]["docs"] += 1
                date_deltas[stat_date]["doc_lines"] += len(doc.lines)
                date_deltas[stat_date]["vouchers"] += 1
                date_deltas[stat_date]["voucher_lines"] += len(vch.lines)
                date_deltas[stat_date]["links"] += 1
                date_deltas[stat_date]["integrations"] += 1
                if integ.status == "SUCCESS":
                    date_deltas[stat_date]["success"] += 1

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

            # 3. Synchronously cascade update daily_stats
            for stat_date, delta in date_deltas.items():
                cursor.execute(
                    "SELECT stat_date FROM daily_stats WHERE stat_date = %s FOR UPDATE;",
                    (stat_date,),
                )
                exists = cursor.fetchone()
                if exists:
                    cursor.execute(
                        "UPDATE daily_stats SET "
                        "doc_count = doc_count + %s, doc_today = doc_today + %s, "
                        "voucher_count = voucher_count + %s, voucher_today = voucher_today + %s, "
                        "integration_count = integration_count + %s, integration_success = integration_success + %s, "
                        "doc_line_count = doc_line_count + %s, voucher_line_count = voucher_line_count + %s, "
                        "link_count = link_count + %s "
                        "WHERE stat_date = %s;",
                        (
                            delta["docs"], delta["docs"],
                            delta["vouchers"], delta["vouchers"],
                            delta["integrations"], delta["success"],
                            delta["doc_lines"], delta["voucher_lines"],
                            delta["links"],
                            stat_date,
                        ),
                    )
                else:
                    # Inherit base numbers from latest preceding stat_date
                    cursor.execute(
                        "SELECT org_count, user_count, doc_count, voucher_count, "
                        "integration_count, integration_success, doc_line_count, "
                        "voucher_line_count, link_count, dual_run_count, snapshot_count "
                        "FROM daily_stats ORDER BY stat_date DESC LIMIT 1;"
                    )
                    prev = cursor.fetchone()
                    if prev:
                        (org_cnt, usr_cnt, p_doc, p_vch, p_int, p_succ,
                         p_dline, p_vline, p_link, p_dual, p_snap) = prev
                    else:
                        org_cnt, usr_cnt, p_doc, p_vch, p_int, p_succ = 2000, 26713, 0, 0, 0, 0
                        p_dline, p_vline, p_link, p_dual, p_snap = 0, 0, 0, 0, 0

                    cursor.execute(
                        "INSERT INTO daily_stats ("
                        "stat_date, org_count, user_count, doc_count, doc_today, "
                        "voucher_count, voucher_today, integration_count, integration_success, "
                        "doc_line_count, voucher_line_count, link_count, dual_run_count, snapshot_count"
                        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                        (
                            stat_date, org_cnt, usr_cnt,
                            p_doc + delta["docs"], delta["docs"],
                            p_vch + delta["vouchers"], delta["vouchers"],
                            p_int + delta["integrations"], p_succ + delta["success"],
                            p_dline + delta["doc_lines"], p_vline + delta["voucher_lines"],
                            p_link + delta["links"], p_dual, p_snap
                        ),
                    )
                rows_written["daily_stats"] += 1

            conn.commit()
            duration_ms = (time.perf_counter() - start_time) * 1000.0

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
            if not self._external_conn:
                conn.close()
