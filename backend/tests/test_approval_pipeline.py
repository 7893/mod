"""Contracts for the new-data-only approval and voucher simulation flow."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.business_rules import (
    DOC_STATUS_PENDING_APPROVAL,
    DOC_STATUS_PENDING_VOUCHER,
    SIMULATED_FLOW_NATURE,
)
from simulation.approval_models import ApprovalFlowBatch, DocumentTransition, SourceDocument, validate_approval_flow
from simulation.approval_pipeline import ApprovalPipeline
from simulation.approval_writer import ApprovalFlowWriter
from simulation.engine_context import IdAllocator, SimulationBaseline
from simulation.footprint_models import DocumentFootprint, DocumentLineFootprint


def _baseline() -> SimulationBaseline:
    return SimulationBaseline(
        latest_business_date=datetime(2026, 9, 20, 18, 0),
        online_org_ids=[1],
        org_users={1: [{"name": "经办甲", "role": "经办人"}]},
        next_ids={
            "business_document": 100,
            "business_document_line": 200,
            "accounting_voucher": 300,
            "accounting_voucher_line": 400,
            "integration_result": 500,
        },
    )


class _QueryCursor:
    def __init__(self, result_sets=None):
        self.result_sets = list(result_sets or [])
        self.current = []
        self.calls = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.lstrip().startswith("SELECT") and self.result_sets:
            self.current = self.result_sets.pop(0)
        return self.rowcount

    def executemany(self, sql, params):
        rows = list(params)
        self.calls.append((sql, rows))
        self.rowcount = len(rows)
        return self.rowcount

    def fetchall(self):
        return self.current

    def fetchone(self):
        return self.current[0] if self.current else None


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_new_submissions_enter_approval_without_same_cycle_vouchers():
    cursor = _QueryCursor([[], []])
    pipeline = ApprovalPipeline(_baseline(), IdAllocator(_baseline().next_ids), seed=7)
    now = datetime(2026, 9, 21, 10, 0)

    batch = pipeline.build_batch(_Connection(cursor), 8, now)

    assert len(batch.submissions) == 8
    assert not batch.vouchers
    assert all(item.nature == SIMULATED_FLOW_NATURE for item in batch.submissions)
    assert all(item.status == DOC_STATUS_PENDING_APPROVAL for item in batch.submissions)
    assert all(item.approve_time is None for item in batch.submissions)
    assert all(0 <= (now - item.submit_time).total_seconds() <= 90 for item in batch.submissions)
    assert all(SIMULATED_FLOW_NATURE in call[1] for call in cursor.calls)


def test_voucher_components_support_merge_and_split_without_losing_amounts():
    allocator = IdAllocator(_baseline().next_ids)
    pipeline = ApprovalPipeline(_baseline(), allocator, seed=11)
    approved = datetime(2026, 9, 21, 9, 0)
    first = SourceDocument(1, 1, "费用报销单", Decimal("100.00"), approved, approved, ("交通费",))
    second = SourceDocument(2, 1, "费用报销单", Decimal("50.00"), approved, approved, ("住宿费",))

    merged = ApprovalFlowBatch(source_documents={1: first, 2: second})
    pipeline._append_voucher_component(merged, [first, second], [Decimal("150.00")], approved)
    validate_approval_flow(merged)
    assert len(merged.vouchers) == 1
    assert len(merged.links) == 2

    split = ApprovalFlowBatch(source_documents={1: first})
    pipeline._append_voucher_component(
        split, [first], [Decimal("62.00"), Decimal("38.00")], approved,
    )
    validate_approval_flow(split)
    assert len(split.vouchers) == 2
    assert len(split.links) == 2


def test_approval_gate_respects_work_hours_and_holiday_capacity():
    work = ApprovalPipeline(_baseline(), IdAllocator(_baseline().next_ids), seed=19)
    holiday = ApprovalPipeline(_baseline(), IdAllocator(_baseline().next_ids), seed=19)
    night = ApprovalPipeline(_baseline(), IdAllocator(_baseline().next_ids), seed=19)

    work_capacity = work._approval_capacity(100, datetime(2026, 9, 21, 10, 0))
    holiday_capacity = holiday._approval_capacity(100, datetime(2026, 9, 26, 10, 0))
    night_capacity = night._approval_capacity(100, datetime(2026, 9, 21, 2, 0))

    assert work_capacity > holiday_capacity > 0
    assert night_capacity == 0


def test_writer_transitions_only_the_isolated_new_flow(monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    cursor = _QueryCursor()
    connection = _Connection(cursor)
    batch = ApprovalFlowBatch(transitions=[DocumentTransition(
        doc_id=42,
        from_status=DOC_STATUS_PENDING_APPROVAL,
        to_status=DOC_STATUS_PENDING_VOUCHER,
        approve_time=datetime(2026, 9, 21, 11, 0),
    )])

    result = ApprovalFlowWriter(conn=connection, audit_log_path=None).write_batch(batch)

    assert result.rows_written["business_document_status"] == 1
    update_sql, update_params = next(call for call in cursor.calls if call[0].startswith("UPDATE business_document"))
    assert "nature = %s AND status = %s" in update_sql
    assert SIMULATED_FLOW_NATURE in update_params
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_writer_persists_submission_without_inventing_a_voucher(monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    submitted = datetime(2026, 9, 21, 13, 10)
    document = DocumentFootprint(
        id=100,
        org_id=1,
        type="费用报销单",
        doc_no="DOC-STAGED",
        applicant="经办甲",
        nature=SIMULATED_FLOW_NATURE,
        amount=Decimal("88.80"),
        submit_time=submitted,
        approve_time=None,
        status=DOC_STATUS_PENDING_APPROVAL,
        lines=[DocumentLineFootprint(200, 100, "交通费", Decimal("88.80"), 1)],
    )
    cursor = _QueryCursor([[(submitted.date(),)]])
    connection = _Connection(cursor)

    result = ApprovalFlowWriter(conn=connection, audit_log_path=None).write_batch(
        ApprovalFlowBatch(submissions=[document]),
    )

    assert result.rows_written["business_document"] == 1
    assert result.rows_written["accounting_voucher"] == 0
    assert result.rows_written["daily_stats"] == 1
    statements = "\n".join(call[0] for call in cursor.calls)
    assert "INSERT INTO business_document " in statements
    assert "INSERT INTO accounting_voucher " not in statements
