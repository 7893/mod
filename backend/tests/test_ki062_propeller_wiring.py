"""Regression test suite for KI-062: ConstructionPropeller & TrickleBackfiller wiring into simulation loop.

Verifies:
1. In enabled mode, slow-movie cycles invoke ConstructionPropeller.step() and TrickleBackfiller.run_cycle().
2. In disabled/dry-run mode, engine strictly fails closed without invoking propeller or backfiller.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from simulation.engine_context import (
    ConstructionBaseline,
    IdAllocator,
    SimulationBaseline,
)
from simulation.runtime_service import (
    PostCycleSelfChecker,
    SimulatorRuntimeConfig,
    SimulatorRuntimeService,
)

HK_TZ = ZoneInfo("Asia/Hong_Kong")


def _mock_fast_baseline() -> SimulationBaseline:
    return SimulationBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        online_org_ids=[1],
        org_users={1: [{"name": "张三", "role": "经办人"}]},
        next_ids={
            "business_document": 100,
            "business_document_line": 200,
            "accounting_voucher": 300,
            "accounting_voucher_line": 400,
            "integration_result": 500,
        },
    )


def _mock_construction_baseline() -> ConstructionBaseline:
    return ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs={1: {"id": 1, "name": "测试单位", "batch_id": 1, "status": "双轨运行中"}},
        orgs_by_status={"双轨运行中": [1]},
        org_users={1: [{"name": "李四", "role": "项目经理"}]},
        next_ids={
            "org_unit": 1000,
            "sys_user": 1000,
            "construction_task": 100,
            "training_record": 200,
            "dual_run_result": 300,
            "data_readiness_record": 400,
            "interface_debug_record": 500,
            "transition_review_record": 600,
            "rollout_batch": 700,
        },
        batches={1: {"id": 1, "name": "第一批次", "status": "双轨运行中"}},
    )


def test_ki062_propeller_invoked_when_engine_enabled(tmp_path, monkeypatch):
    """Assertion: When simulation engine is enabled, slow-movie cycles invoke propeller and backfiller."""
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    monkeypatch.setenv("MOD_CF_AI_ENABLED", "true")

    config = SimulatorRuntimeConfig(
        max_events_per_minute=100,
        max_events_per_day=10000,
        fail_closed_flag_path=tmp_path / "fail_closed.flag",
        fuse_state_path=tmp_path / "fuse_state.json",
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
        slow_movie_interval_cycles=1,  # every cycle is a slow-movie cycle
        dry_run=False,
    )

    mock_conn = MagicMock()
    mock_propeller = MagicMock()
    mock_propeller.step.return_value = MagicMock(
        units_advanced=2, issues_advanced=1, issues_created=0, issues_resolved=1
    )
    mock_backfiller = MagicMock()
    mock_backfiller.run_cycle.return_value = MagicMock(issues_processed=1, neurons_consumed=1.5)

    service = SimulatorRuntimeService(
        config=config,
        conn=mock_conn,
        propeller=mock_propeller,
        backfiller=mock_backfiller,
    )

    service._fast_baseline = _mock_fast_baseline()
    service._fast_allocator = IdAllocator(service._fast_baseline.next_ids)
    service._construction_baseline = _mock_construction_baseline()
    service._construction_allocator = IdAllocator(service._construction_baseline.next_ids)

    # Mock B-mode slow movie event writer
    c_mock_res = MagicMock(success=True)
    monkeypatch.setattr(
        "simulation.runtime_service.ConstructionWriter.write_construction_events",
        lambda self, evts, **kwargs: c_mock_res,
    )
    monkeypatch.setattr(PostCycleSelfChecker, "check_construction_events", lambda conn, evts: (True, ""))

    now_hkt = datetime(2026, 9, 8, 11, 0, 0, tzinfo=HK_TZ)
    result = service.step_cycle(now=now_hkt)

    assert result.status == "SUCCESS"
    assert mock_propeller.step.called, "ConstructionPropeller.step() MUST be called in enabled slow-movie cycle"
    mock_backfiller.run_cycle.assert_called_once_with(batch_size=1, auto_commit=False)
    assert mock_conn.commit.called, "Database transaction MUST commit propeller & backfiller changes"


def test_ki062_propeller_not_invoked_when_engine_disabled(tmp_path, monkeypatch):
    """Assertion: When simulation engine is disabled (fail-closed), propeller and backfiller are NEVER called."""
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "false")

    config = SimulatorRuntimeConfig(
        max_events_per_minute=100,
        max_events_per_day=10000,
        fail_closed_flag_path=tmp_path / "fail_closed.flag",
        fuse_state_path=tmp_path / "fuse_state.json",
        status_file_path=tmp_path / "status.json",
        audit_log_path=tmp_path / "audit.log",
        slow_movie_interval_cycles=1,
        dry_run=False,
    )

    mock_conn = MagicMock()
    mock_propeller = MagicMock()
    mock_backfiller = MagicMock()

    service = SimulatorRuntimeService(
        config=config,
        conn=mock_conn,
        propeller=mock_propeller,
        backfiller=mock_backfiller,
    )

    service._fast_baseline = _mock_fast_baseline()
    service._fast_allocator = IdAllocator(service._fast_baseline.next_ids)
    service._construction_baseline = _mock_construction_baseline()
    service._construction_allocator = IdAllocator(service._construction_baseline.next_ids)

    now_hkt = datetime(2026, 9, 8, 11, 0, 0, tzinfo=HK_TZ)
    result = service.step_cycle(now=now_hkt)

    assert result.status == "DRY_RUN"
    assert not mock_propeller.step.called, "ConstructionPropeller MUST NOT be called in disabled mode (fail-closed)"
    assert not mock_backfiller.run_cycle.called, "TrickleBackfiller MUST NOT be called in disabled mode"
    assert not mock_conn.commit.called, "No commit allowed in disabled mode"
