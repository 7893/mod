"""Unit tests for safe transactional construction writer (Phase E)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.simulation.construction_models import (
    DualRunCheckEventFootprint,
    DualRunResultRecordFootprint,
    ConstructionTaskFootprint,
)
from app.simulation.construction_writer import ConstructionWriter, is_construction_writer_enabled


def test_construction_writer_safety_switch_blocked(monkeypatch):
    monkeypatch.delenv("MOD_SIMULATION_ENGINE_ENABLED", raising=False)
    assert not is_construction_writer_enabled()

    writer = ConstructionWriter()
    res = writer.write_construction_events([], execute=True)
    assert not res.success
    assert "BLOCKED" in (res.error or "")


def test_construction_writer_execute_false_blocked(monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    assert is_construction_writer_enabled()

    writer = ConstructionWriter()
    res = writer.write_construction_events([], execute=False)
    assert not res.success
    assert "BLOCKED" in (res.error or "")


def test_construction_writer_atomic_rollback_on_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate error on execute
    mock_cursor.execute.side_effect = RuntimeError("Simulated DB connection error")

    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(tmp_path / "backups"),
    )
    # Mock backup to avoid real DB queries
    writer.backup_affected_tables = MagicMock(return_value="mock_backup.json")

    event = DualRunCheckEventFootprint(
        org_id=10,
        batch_id=1,
        event_date=date(2026, 9, 5),
        dual_run=DualRunResultRecordFootprint(
            id=101,
            org_id=10,
            check_type="业务单据金额核对",
            v1_amount=Decimal("1000.00"),
            v2_amount=Decimal("1000.00"),
            diff_amount=Decimal("0.00"),
            result="一致",
            check_date=date(2026, 9, 5),
        ),
        associated_task=ConstructionTaskFootprint(
            id=201,
            org_id=10,
            name="双轨核对任务",
            type="双轨验证",
            owner="张三",
            plan_time=date(2026, 9, 5),
            actual_time=date(2026, 9, 5),
            status="已完成",
            progress=100,
            update_time=date(2026, 9, 5),
        ),
    )

    res = writer.write_construction_events([event], execute=True)
    assert not res.success
    assert "Rolled back" in (res.error or "")
    mock_conn.rollback.assert_called_once()
