"""Unit tests for realistic business simulation engine footprint, playbook, and writer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from simulation.engine_context import IdAllocator, SimulationBaseline
from simulation.expense_playbook import ExpensePlaybook
from simulation.footprint_models import (
    DocumentFootprint,
    DocumentLineFootprint,
    EventFootprint,
    IntegrationFootprint,
    LinkFootprint,
    VoucherFootprint,
    VoucherLineFootprint,
    validate_footprint,
)
from simulation.simulation_writer import SimulationWriter, is_simulation_engine_enabled


def _create_sample_event(
    amount: Decimal = Decimal("1500.50"),
    submit_time: datetime = datetime(2026, 9, 4, 9, 30, 0),
    approve_time: datetime = datetime(2026, 9, 4, 10, 15, 0),
    gen_time: datetime = datetime(2026, 9, 4, 10, 20, 0),
    int_time: datetime = datetime(2026, 9, 4, 10, 22, 0),
) -> EventFootprint:
    doc_lines = [
        DocumentLineFootprint(id=101, doc_id=1, item_name="差旅交通费", amount=Decimal("1000.00"), quantity=1),
        DocumentLineFootprint(id=102, doc_id=1, item_name="住宿费", amount=Decimal("500.50"), quantity=1),
    ]
    doc = DocumentFootprint(
        id=1,
        org_id=10,
        type="费用报销单",
        doc_no="DOC-TEST001",
        applicant="张三",
        nature="正式业务",
        amount=amount,
        submit_time=submit_time,
        approve_time=approve_time,
        status="处理完成",
        lines=doc_lines,
    )
    vch_lines = [
        VoucherLineFootprint(
            id=201, voucher_id=1, subject_code="1002", subject_name="银行存款",
            debit=amount, credit=Decimal("0.00")
        ),
        VoucherLineFootprint(
            id=202, voucher_id=1, subject_code="2202", subject_name="应付账款",
            debit=Decimal("0.00"), credit=amount
        ),
    ]
    vch = VoucherFootprint(
        id=1,
        org_id=10,
        voucher_no="V-TEST001",
        type="记账凭证",
        gen_time=gen_time,
        int_time=int_time,
        status="已集成",
        debit=amount,
        credit=amount,
        lines=vch_lines,
    )
    link = LinkFootprint(doc_id=1, voucher_id=1)
    integ = IntegrationFootprint(
        id=301,
        voucher_id=1,
        status="SUCCESS",
        retry_count=0,
        error_code="",
        error_message="成功",
        integration_time=int_time,
    )
    return EventFootprint(document=doc, voucher=vch, link=link, integration=integ)


def test_footprint_validation_success():
    event = _create_sample_event()
    validate_footprint(event)


def test_footprint_validation_line_sum_mismatch():
    event = _create_sample_event()
    event.document.lines[0].amount = Decimal("999.00")
    with pytest.raises(ValueError, match="Document lines sum .* does not equal"):
        validate_footprint(event)


def test_footprint_validation_voucher_debit_credit_mismatch():
    event = _create_sample_event()
    event.voucher.lines[0].debit = Decimal("1400.00")
    with pytest.raises(ValueError, match="Voucher line debit/credit mismatch"):
        validate_footprint(event)


def test_footprint_validation_timeline_inversion():
    event = _create_sample_event(
        submit_time=datetime(2026, 9, 4, 10, 0, 0),
        approve_time=datetime(2026, 9, 4, 9, 0, 0),  # approve earlier than submit
    )
    with pytest.raises(ValueError, match="Timeline inversion detected"):
        validate_footprint(event)


def test_expense_playbook_generation():
    baseline = SimulationBaseline(
        latest_business_date=datetime(2026, 9, 3, 18, 0, 0),
        online_org_ids=[1, 2],
        org_users={
            1: [{"name": "经办甲", "role": "经办人"}, {"name": "总监甲", "role": "财务总监"}],
            2: [{"name": "用户乙", "role": "普通用户"}],
        },
        next_ids={
            "business_document": 5000,
            "business_document_line": 10000,
            "accounting_voucher": 3000,
            "accounting_voucher_line": 6000,
            "integration_result": 4000,
        },
    )
    allocator = IdAllocator(baseline.next_ids)
    playbook = ExpensePlaybook(baseline=baseline, id_allocator=allocator, seed=42)

    events = playbook.generate_batch(count=10, target_date=datetime(2026, 9, 4, 8, 30))
    assert len(events) == 10

    for evt in events:
        validate_footprint(evt)
        assert evt.document.type == "费用报销单"
        assert evt.document.nature == "正式业务"
        assert evt.document.status == "处理完成"
        assert evt.document.org_id in [1, 2]
        allowed_names = [u["name"] for u in baseline.org_users[evt.document.org_id]]
        assert evt.document.applicant in allowed_names
        assert evt.document.submit_time > baseline.latest_business_date
        assert evt.voucher.debit == evt.document.amount
        assert evt.voucher.credit == evt.document.amount
        assert evt.link.doc_id == evt.document.id
        assert evt.link.voucher_id == evt.voucher.id
        assert evt.integration.voucher_id == evt.voucher.id


def test_simulation_writer_disabled_gate(monkeypatch, tmp_path):
    monkeypatch.delenv("MOD_SIMULATION_ENGINE_ENABLED", raising=False)
    assert not is_simulation_engine_enabled()

    audit_path = tmp_path / "audit.log"
    writer = SimulationWriter(audit_log_path=str(audit_path))
    event = _create_sample_event()

    with pytest.raises(RuntimeError, match="MOD_SIMULATION_ENGINE_ENABLED is not enabled"):
        writer.write_events([event])

    assert audit_path.exists()
    content = audit_path.read_text()
    assert "BLOCKED" in content


def test_simulation_writer_transactional_commit(monkeypatch, tmp_path):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    assert is_simulation_engine_enabled()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        ("2026-09-04",),  # daily_stats row exists check
    ]

    audit_path = tmp_path / "audit.log"
    writer = SimulationWriter(conn=mock_conn, audit_log_path=str(audit_path))
    event = _create_sample_event()

    result = writer.write_events([event])
    assert result.success
    assert result.event_count == 1
    assert result.rows_written["business_document"] == 1
    assert result.rows_written["accounting_voucher"] == 1
    assert result.rows_written["daily_stats"] == 1

    assert mock_conn.commit.called
    assert not mock_conn.rollback.called
    assert audit_path.exists()
    assert "SUCCESS" in audit_path.read_text()


def test_simulation_writer_transactional_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.executemany.side_effect = RuntimeError("DB connection dropped")

    audit_path = tmp_path / "audit.log"
    writer = SimulationWriter(conn=mock_conn, audit_log_path=str(audit_path))
    event = _create_sample_event()

    with pytest.raises(RuntimeError, match="DB connection dropped"):
        writer.write_events([event])

    assert mock_conn.rollback.called
    assert not mock_conn.commit.called
    assert audit_path.exists()
    assert "ROLLED_BACK" in audit_path.read_text()
