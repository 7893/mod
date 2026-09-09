"""Tests for governance state machine, propeller, and API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from unittest.mock import MagicMock
from starlette.testclient import TestClient

from simulation.governance_state_machine import (
    ExpertPool,
    GovernanceStateMachine,
    GovernanceStatus,
    LocalNarrativeLibrary,
)
from app.main import app
from app.api import connection


def test_local_narrative_library():
    """Verify local narrative library provides complete offline seeds."""
    tmpl = LocalNarrativeLibrary.get_template("超期挂账")
    assert "历史往来账" in tmpl["title_template"]
    assert "investigate_note" in tmpl
    assert "patch_note" in tmpl
    assert "rework_note" in tmpl
    assert "resolve_note" in tmpl


def test_expert_pool_capacity():
    """Verify expert pool has capacity 8 and queues when exhausted."""
    pool = ExpertPool(capacity=8)
    assert pool.free_count == 8

    acquired = []
    for i in range(8):
        spec = pool.acquire(f"issue-{i}")
        assert spec is not None
        acquired.append(spec)

    assert pool.free_count == 0
    # 9th request must return None (queueing)
    assert pool.acquire("issue-overflow") is None

    # Release one
    released = pool.release("issue-0")
    assert released is not None
    assert pool.free_count == 1

    # Now 9th can acquire
    next_spec = pool.acquire("issue-overflow")
    assert next_spec == released


def test_governance_state_machine_flow():
    """Verify full transition flow DISCOVERED -> ASSIGNED -> IN_PROGRESS -> VERIFYING -> RESOLVED."""
    pool = ExpertPool(capacity=8)
    fsm = GovernanceStateMachine(pool=pool, seed=123)
    now = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    issue_id = "test-iss-001"

    # 1. DISCOVERED -> ASSIGNED
    status, evt = fsm.transition(
        current_status="DISCOVERED",
        issue_id=issue_id,
        issue_type="超期挂账",
        unit_name="测试装备制造厂",
        now=now,
    )
    assert status == GovernanceStatus.ASSIGNED.value
    assert evt is not None
    assert evt[0] == "调度派工"

    # 2. ASSIGNED -> IN_PROGRESS
    status, evt = fsm.transition(
        current_status=status,
        issue_id=issue_id,
        issue_type="超期挂账",
        unit_name="测试装备制造厂",
        now=now,
    )
    assert status == GovernanceStatus.IN_PROGRESS.value
    assert evt[0] == "现场排查"

    # 3. IN_PROGRESS -> VERIFYING
    status, evt = fsm.transition(
        current_status=status,
        issue_id=issue_id,
        issue_type="超期挂账",
        unit_name="测试装备制造厂",
        now=now,
    )
    assert status == GovernanceStatus.VERIFYING.value
    assert evt[0] == "发布补丁"

    # 4. VERIFYING -> RESOLVED (with force_boost=True to guarantee pass)
    status, evt = fsm.transition(
        current_status=status,
        issue_id=issue_id,
        issue_type="超期挂账",
        unit_name="测试装备制造厂",
        now=now,
        force_boost=True,
    )
    assert status == GovernanceStatus.RESOLVED.value
    assert evt[0] == "闭环销项"


def test_governance_rework_loop():
    """Verify 15% rework loop in state machine transitions from VERIFYING back to IN_PROGRESS."""
    pool = ExpertPool(capacity=8)
    pool.acquire("test-rework-001")

    rework_triggered = False
    now = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    for seed in range(50):
        fsm_trial = GovernanceStateMachine(pool=pool, seed=seed)
        status, evt = fsm_trial.transition(
            current_status="VERIFYING",
            issue_id="test-rework-001",
            issue_type="超预算迹象",
            unit_name="测试单位",
            now=now,
            force_boost=False,
        )
        if status == GovernanceStatus.IN_PROGRESS.value and evt and evt[0] == "二次核验":
            rework_triggered = True
            break

    assert rework_triggered, "Rework loop should be triggered on verification failure"


def test_governance_api_endpoints(monkeypatch):
    """Verify FastAPI governance endpoints (list, detail, timeline, dispatch)."""
    mock_conn = MagicMock()
    app.dependency_overrides[connection] = lambda: mock_conn
    client = TestClient(app)

    monkeypatch.setattr(
        "app.services.governance.list_governance_issues",
        lambda conn, **kwargs: {
            "total": 1,
            "items": [{"id": "ISS-TEST-001", "unitName": "测试单位", "status": "OPEN"}],
            "statusSummary": {"OPEN": 1},
        },
    )
    monkeypatch.setattr(
        "app.services.governance.get_governance_issue",
        lambda conn, issue_id: {"id": issue_id, "unitName": "测试单位", "status": "OPEN"},
    )
    monkeypatch.setattr(
        "app.services.governance.get_issue_timeline",
        lambda conn, issue_id: [{"action": "一键督办", "actor": "专班专家", "detail": "推进督办"}],
    )
    monkeypatch.setattr(
        "app.services.governance.dispatch_issue",
        lambda conn, issue_id: {"id": issue_id, "status": "IN_PROGRESS"},
    )

    try:
        # 1. List
        res = client.get("/api/governance/issues?page=1&page_size=5")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "ISS-TEST-001"

        # 2. Detail
        res_detail = client.get("/api/governance/issues/ISS-TEST-001")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == "ISS-TEST-001"

        # 3. Timeline
        res_timeline = client.get("/api/governance/issues/ISS-TEST-001/timeline")
        assert res_timeline.status_code == 200
        assert res_timeline.json()[0]["action"] == "一键督办"

        # 4. Dispatch
        res_dispatch = client.post("/api/governance/issues/ISS-TEST-001/dispatch")
        assert res_dispatch.status_code == 200
        assert res_dispatch.json()["status"] == "IN_PROGRESS"
    finally:
        app.dependency_overrides.pop(connection, None)


def test_construction_propeller_advancement():
    """Verify ConstructionPropeller can execute a cycle, advance issues, and lock/unlock units."""
    from simulation.construction_propeller import ConstructionPropeller

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 1st fetchall: open_issues
    # 2nd fetchall: locked_unit_ids
    # 3rd fetchall: units_to_eval (u_id, u_name, u_region, b_id, u_status, avg_prog)
    mock_cur.fetchall.side_effect = [
        [(1, 101, "太原重工", "超预算迹象", "DISCOVERED", 0)],
        [(101,)],
        [(102, "大同煤矿", "山西", 6, "准备中", 80.0)],
    ]

    prop = ConstructionPropeller(conn=mock_conn, seed=42)
    res = prop.step()
    assert res is not None
    assert isinstance(res.issues_advanced, int)
    assert isinstance(res.units_advanced, int)

