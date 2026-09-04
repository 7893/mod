"""Unit tests for B-Mode lifecycle state machine advancer.

Phase C: Tests for 6-stage lifecycle transitions, metrics evaluation, and the Three Iron Rules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.simulation.engine_context import ConstructionBaseline
from app.simulation.lifecycle_advancer import (
    LifecycleAdvancer,
    LifecycleThresholds,
    OrgMetricsSnapshot,
)


@pytest.fixture
def baseline() -> ConstructionBaseline:
    orgs = {
        10: {
            "id": 10,
            "name": "测试单位A",
            "batch_id": 1,
            "status": "准备中",
            "region": "华东",
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 12, 1),
        },
        20: {
            "id": 20,
            "name": "测试单位B",
            "batch_id": 1,
            "status": "双轨运行中",
            "region": "华南",
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 12, 1),
        },
    }
    orgs_by_status = {"准备中": [10], "双轨运行中": [20]}
    org_users = {
        10: [{"name": "张三", "role": "会计"}],
        20: [{"name": "李四", "role": "财务主管"}],
    }
    batches = {
        1: {
            "id": 1,
            "name": "第一批",
            "start_date": date(2026, 7, 1),
            "end_date": date(2026, 12, 31),
            "status": "准备中",
        }
    }
    next_ids = {"construction_task": 100, "training": 100, "dual_run_result": 100}
    return ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs=orgs,
        orgs_by_status=orgs_by_status,
        org_users=org_users,
        next_ids=next_ids,
        batches=batches,
    )


def test_rule1_forward_only_progression(baseline: ConstructionBaseline):
    advancer = LifecycleAdvancer(baseline)
    assert advancer.get_next_stage("未启动") == "准备中"
    assert advancer.get_next_stage("准备中") == "已具备双轨条件"
    assert advancer.get_next_stage("已具备双轨条件") == "双轨运行中"
    assert advancer.get_next_stage("双轨运行中") == "已上线"
    assert advancer.get_next_stage("已上线") == "稳定运行"
    assert advancer.get_next_stage("稳定运行") is None


def test_rule2_sustained_qualification_days(baseline: ConstructionBaseline):
    """Test that transition requires N consecutive qualified days; dips reset counter."""
    thresholds = LifecycleThresholds(prep_consecutive_days_min=3)
    advancer = LifecycleAdvancer(baseline, thresholds=thresholds, seed=42)

    cur_date = date(2026, 9, 1)
    # Qualified snapshot
    metrics = OrgMetricsSnapshot(
        org_id=10,
        current_status="准备中",
        batch_id=1,
        stage_entered_date=date(2026, 8, 1),
        static_rate=100.0,
        opening_rate=100.0,
        opening_diff_amount=Decimal("0.00"),
        dynamic_rate=95.0,
        tasks_completed={"基础环境": True, "基础数据": True, "期初数据": True},
    )

    # Day 1: Qualified, but consecutive days = 1 < 3 -> No transition
    event1 = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event1 is None
    assert advancer.consecutive_qualified_days[10] == 1
    assert advancer.org_status[10] == "准备中"

    # Day 2: Metric dips (e.g. dynamic sync rate dropped below 90%) -> Reset!
    metrics.dynamic_rate = 85.0
    cur_date += timedelta(days=1)
    event2 = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event2 is None
    assert advancer.consecutive_qualified_days[10] == 0

    # Day 3: Re-qualified -> consecutive days = 1
    metrics.dynamic_rate = 95.0
    cur_date += timedelta(days=1)
    event3 = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event3 is None
    assert advancer.consecutive_qualified_days[10] == 1

    # Day 4: Qualified -> consecutive days = 2
    cur_date += timedelta(days=1)
    event4 = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event4 is None
    assert advancer.consecutive_qualified_days[10] == 2

    # Day 5: Qualified -> consecutive days = 3 -> TRANSITION!
    cur_date += timedelta(days=1)
    event5 = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event5 is not None
    assert event5.status_update.from_status == "准备中"
    assert event5.status_update.to_status == "已具备双轨条件"
    assert advancer.org_status[10] == "已具备双轨条件"


def test_rule3_transition_has_process_and_snapshot(baseline: ConstructionBaseline):
    """Test transition generates formal review notes and status snapshot."""
    thresholds = LifecycleThresholds(prep_consecutive_days_min=1)
    advancer = LifecycleAdvancer(baseline, thresholds=thresholds, seed=42)

    cur_date = date(2026, 9, 5)
    metrics = OrgMetricsSnapshot(
        org_id=10,
        current_status="准备中",
        batch_id=1,
        stage_entered_date=date(2026, 8, 1),
        static_rate=100.0,
        opening_rate=100.0,
        opening_diff_amount=Decimal("0.00"),
        dynamic_rate=95.0,
        tasks_completed={"基础环境": True, "基础数据": True, "期初数据": True},
    )

    event = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event is not None
    assert "阶段跃迁评审决议" in event.review_notes
    assert event.snapshot.org_id == 10
    assert event.snapshot.snapshot_date == cur_date
    assert event.snapshot.status == "已具备双轨条件"


def test_dual_run_to_go_live_evaluation(baseline: ConstructionBaseline):
    """Test dual-run to go-live transition criteria."""
    thresholds = LifecycleThresholds(
        dual_run_days_min=14,
        dual_run_min_checks=5,
        dual_run_consistency_rate_min=98.0,
        dual_run_consecutive_days_min=1,
    )
    advancer = LifecycleAdvancer(baseline, thresholds=thresholds, seed=42)

    cur_date = date(2026, 9, 5)
    # 20 days since dual run start (> 14)
    metrics = OrgMetricsSnapshot(
        org_id=20,
        current_status="双轨运行中",
        batch_id=1,
        stage_entered_date=date(2026, 8, 15),
        dual_run_checks_total=10,
        dual_run_consistency_rate=99.5,
        dual_run_recent_matches=5,
        has_blocking_risk=False,
    )

    # 1. Qualified case
    event = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event is not None
    assert event.to_status == "已上线"

    # 2. Case where blocking risk is present
    advancer.org_status[20] = "双轨运行中"
    metrics.has_blocking_risk = True
    event_blocked = advancer.advance_unit_if_eligible(metrics, cur_date)
    assert event_blocked is None
