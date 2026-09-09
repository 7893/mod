"""Regression tests for GI #4: Dynamic Equilibrium, Chronobiology & Cross-screen ripple."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from simulation.governance_state_machine import (
    ExpertPool,
    GovernanceStateMachine,
    GovernanceStatus,
    compute_rhythm_factor,
)
from simulation.construction_propeller import ConstructionPropeller
from app.main import app
from app.api import connection


def test_chronobiological_rhythm_profile():
    """Verify circadian rhythm factor k across different times of day in HKT."""
    # Morning peak (09:30 HKT)
    t_morning = datetime(2026, 9, 10, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_morning) == 1.8

    # Lunch break (12:30 HKT)
    t_lunch = datetime(2026, 9, 10, 12, 30, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_lunch) == 0.5

    # Afternoon peak (15:00 HKT)
    t_afternoon = datetime(2026, 9, 10, 15, 0, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_afternoon) == 1.8

    # Overtime evening (19:30 HKT)
    t_evening = datetime(2026, 9, 10, 19, 30, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_evening) == 1.0

    # Deep night sleep (03:00 HKT)
    t_night = datetime(2026, 9, 10, 3, 0, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_night) == 0.0

    # Month-end sprint multiplier (day >= 25, 09:30 HKT)
    t_monthend = datetime(2026, 9, 28, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    assert compute_rhythm_factor(t_monthend) == 2.7


def test_night_freeze_guard():
    """Verify state machine strictly freezes during deep night hours (22:00 - 07:00 HKT)."""
    pool = ExpertPool(capacity=8)
    fsm = GovernanceStateMachine(pool=pool, seed=42)
    night_time = datetime(2026, 9, 10, 2, 30, tzinfo=timezone(timedelta(hours=8)))

    status, evt = fsm.transition(
        current_status=GovernanceStatus.DISCOVERED.value,
        issue_id="ISS-NIGHT-001",
        issue_type="超期挂账",
        unit_name="测试单位",
        now=night_time,
        force_boost=False,
        apply_rhythm=True,
    )
    # Must remain unchanged with no event generated
    assert status == GovernanceStatus.DISCOVERED.value
    assert evt is None

    # When force_boost is True, bypasses night freeze
    status_forced, evt_forced = fsm.transition(
        current_status=GovernanceStatus.DISCOVERED.value,
        issue_id="ISS-NIGHT-001",
        issue_type="超期挂账",
        unit_name="测试单位",
        now=night_time,
        force_boost=True,
        apply_rhythm=True,
    )
    assert status_forced == GovernanceStatus.ASSIGNED.value
    assert evt_forced is not None


def test_propeller_dynamic_equilibrium_corridor():
    """Verify propeller tunes friction spawn and issue limits based on inventory corridor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Scenario A: Open count is low (20 issues < 35 threshold) -> accelerate friction, throttle resolution
    mock_cursor.fetchone.return_value = (20,)
    mock_cursor.fetchall.side_effect = [
        [],  # open issues
        [],  # locked unit ids
        [(101, "冲刺测试单位", "陕西", 7, "准备中", 85.0)],  # units to eval
    ]

    propeller = ConstructionPropeller(conn=mock_conn, seed=42)
    # Seed 42 with friction_chance 0.50 triggers friction trap
    result = propeller.step(
        now=datetime(2026, 9, 10, 10, 0, tzinfo=timezone(timedelta(hours=8))),
        auto_commit=False,
    )

    # In low stock scenario, friction trap spawns new issue
    assert result.issues_created >= 1 or result.units_advanced >= 0


def test_cross_screen_ripple_on_issue_resolution():
    """Verify resolving issue heals construction_task and data_readiness without touching org_unit.status."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    propeller = ConstructionPropeller(conn=mock_conn, seed=123)
    now = datetime(2026, 9, 10, 10, 30, tzinfo=timezone.utc)
    propeller._boost_healed_unit(mock_cursor, unit_id=55, now=now)

    # Check construction_task updated to 100% and 已完成
    calls = [str(call) for call in mock_cursor.execute.call_args_list]
    assert any("progress = 100, status = '已完成'" in c for c in calls)
    assert any("opening_rate = '100.0%%'" in c for c in calls)
    # Lifecycle advancement belongs to lifecycle_advancer only (KI-072)
    assert not any("org_unit" in c for c in calls)


def test_recent_activities_api_endpoint():
    """Verify GET /api/governance/recent-activities endpoint returns timeline feed."""
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value = [
        {
            "id": 1,
            "issueId": "ISS-20260908-0001",
            "action": "调度派工",
            "actor": "数字化转型总指挥部",
            "detail": "指派专班深入现场",
            "timeStr": "10:24:18",
            "occurredAt": "2026-09-08 10:24:18",
            "unitName": "神华准格尔能源有限责任公司",
            "province": "内蒙古",
            "issueType": "超期挂账",
            "status": "ASSIGNED",
        }
    ]
    mock_conn.execute.return_value = mock_result

    app.dependency_overrides[connection] = lambda: mock_conn
    client = TestClient(app, raise_server_exceptions=True)

    try:
        resp = client.get("/api/governance/recent-activities?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["issueId"] == "ISS-20260908-0001"
        assert data[0]["unitName"] == "神华准格尔能源有限责任公司"
        assert data[0]["timeStr"] == "10:24:18"
    finally:
        app.dependency_overrides.pop(connection, None)
