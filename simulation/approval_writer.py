"""Transactional writer for the staged approval and voucher lifecycle."""

from __future__ import annotations

from contextlib import suppress
import time
from typing import Any

from app.business_rules import SIMULATED_FLOW_NATURE

from .approval_models import ApprovalFlowBatch, validate_approval_flow
from .daily_stats import add_daily_delta, apply_daily_deltas
from .simulation_writer import SimulationWriter, WriteResult, is_simulation_engine_enabled


class ApprovalFlowWriter(SimulationWriter):
    """Persist one isolated new-flow batch as a single transaction."""

    def write_batch(self, batch: ApprovalFlowBatch, *, auto_commit: bool = True) -> WriteResult:
        if not is_simulation_engine_enabled():
            self.record_failure_audit("MOD_SIMULATION_ENGINE_ENABLED is not enabled (fail-closed)")
            raise RuntimeError("Simulation write rejected: MOD_SIMULATION_ENGINE_ENABLED is not enabled.")

        validate_approval_flow(batch)
        event_count = len(batch.submissions)
        if not any((batch.submissions, batch.transitions, batch.vouchers)):
            return WriteResult(success=True, event_count=0, rows_written={})

        started = time.perf_counter()
        conn = self._get_connection()
        rows_written = {
            "business_document": 0,
            "business_document_line": 0,
            "business_document_status": 0,
            "accounting_voucher": 0,
            "accounting_voucher_line": 0,
            "document_voucher_link": 0,
            "integration_result": 0,
            "daily_stats": 0,
        }
        try:
            cursor = conn.cursor()
            date_deltas: dict[Any, dict[str, int]] = {}

            doc_rows = [(
                doc.id, doc.org_id, doc.type, doc.doc_no, doc.applicant,
                doc.nature, doc.amount, doc.submit_time, doc.approve_time, doc.status,
            ) for doc in batch.submissions]
            doc_line_rows = [
                (line.id, line.doc_id, line.item_name, line.amount, line.quantity)
                for doc in batch.submissions for line in doc.lines
            ]
            if doc_rows:
                cursor.executemany(
                    "INSERT INTO business_document "
                    "(id, org_id, type, doc_no, applicant, nature, amount, submit_time, approve_time, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                    doc_rows,
                )
                cursor.executemany(
                    "INSERT INTO business_document_line "
                    "(id, doc_id, item_name, amount, quantity) VALUES (%s, %s, %s, %s, %s);",
                    doc_line_rows,
                )
                rows_written["business_document"] = len(doc_rows)
                rows_written["business_document_line"] = len(doc_line_rows)
                for doc in batch.submissions:
                    add_daily_delta(
                        date_deltas, doc.submit_time.date(),
                        docs=1, doc_lines=len(doc.lines),
                    )

            for transition in batch.transitions:
                cursor.execute(
                    "UPDATE business_document SET status = %s, "
                    "approve_time = COALESCE(%s, approve_time) "
                    "WHERE id = %s AND nature = %s AND status = %s;",
                    (
                        transition.to_status, transition.approve_time, transition.doc_id,
                        SIMULATED_FLOW_NATURE, transition.from_status,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"Document {transition.doc_id} changed before its staged transition"
                    )
                rows_written["business_document_status"] += 1

            voucher_rows = [(
                voucher.id, voucher.org_id, voucher.voucher_no, voucher.type,
                voucher.gen_time, voucher.int_time, voucher.status,
                voucher.debit, voucher.credit,
            ) for voucher in batch.vouchers]
            voucher_line_rows = [
                (line.id, line.voucher_id, line.subject_code, line.subject_name, line.debit, line.credit)
                for voucher in batch.vouchers for line in voucher.lines
            ]
            link_rows = [(link.doc_id, link.voucher_id) for link in batch.links]
            integration_rows = [(
                item.id, item.voucher_id, item.status, item.retry_count,
                item.error_code, item.error_message, item.integration_time,
            ) for item in batch.integrations]
            if voucher_rows:
                cursor.executemany(
                    "INSERT INTO accounting_voucher "
                    "(id, org_id, voucher_no, type, gen_time, int_time, status, debit, credit) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
                    voucher_rows,
                )
                cursor.executemany(
                    "INSERT INTO accounting_voucher_line "
                    "(id, voucher_id, subject_code, subject_name, debit, credit) "
                    "VALUES (%s, %s, %s, %s, %s, %s);",
                    voucher_line_rows,
                )
                cursor.executemany(
                    "INSERT INTO document_voucher_link (doc_id, voucher_id) VALUES (%s, %s);",
                    link_rows,
                )
                cursor.executemany(
                    "INSERT INTO integration_result "
                    "(id, voucher_id, status, retry_count, error_code, error_message, integration_time) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s);",
                    integration_rows,
                )
                rows_written["accounting_voucher"] = len(voucher_rows)
                rows_written["accounting_voucher_line"] = len(voucher_line_rows)
                rows_written["document_voucher_link"] = len(link_rows)
                rows_written["integration_result"] = len(integration_rows)

                voucher_dates = {item.id: item.gen_time.date() for item in batch.vouchers}
                for voucher in batch.vouchers:
                    add_daily_delta(
                        date_deltas, voucher.gen_time.date(),
                        vouchers=1, voucher_lines=len(voucher.lines),
                    )
                for link in batch.links:
                    add_daily_delta(date_deltas, voucher_dates[link.voucher_id], links=1)
                for item in batch.integrations:
                    add_daily_delta(
                        date_deltas, item.integration_time.date(),
                        integrations=1, success=int(item.status == "SUCCESS"),
                    )

            rows_written["daily_stats"] = apply_daily_deltas(cursor, date_deltas)
            result = WriteResult(
                success=True,
                event_count=event_count,
                rows_written=rows_written,
                duration_ms=round((time.perf_counter() - started) * 1000.0, 2),
            )
            if auto_commit:
                conn.commit()
                self.record_success_audit(result)
            return result
        except Exception as exc:
            with suppress(Exception):
                conn.rollback()
            self.record_failure_audit(str(exc), event_count=event_count)
            raise
        finally:
            if auto_commit and not self._external_conn:
                conn.close()
