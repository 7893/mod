"""Unit tests for evolution coordinator and contradiction meshing (Phase D)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.simulation.engine_context import ConstructionBaseline
from app.simulation.evolution_coordinator import EvolutionCoordinator
from app.simulation.lifecycle_advancer import LifecycleThresholds


@pytest.fixture
def baseline() -> ConstructionBaseline:
    # 20 orgs across statuses
    orgs = {}
    orgs_by_status = {"准备中": [], "已具备双轨条件": [], "双轨运行中": []}
    org_users = {}
    for i in range(1, 21):
        if i <= 8:
            st = "准备中"
        elif i <= 14:
            st = "已具备双轨条件"
        else:
            st = "双轨运行中"

        orgs[i] = {
            "id": i,
            "name": f"测试单位_{i}",
            "batch_id": 1,
            "status": st,
            "region": "华北",
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 12, 1),
        }
        orgs_by_status[st].append(i)
        org_users[i] = [{"name": f"员工_{i}", "role": "会计"}]

    batches = {
        1: {
            "id": 1,
            "name": "第一批",
            "start_date": date(2026, 7, 1),
            "end_date": date(2026, 12, 31),
            "status": "双轨运行中",
        }
    }
    next_ids = {"construction_task": 1000, "training": 1000, "dual_run_result": 1000}
    return ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs=orgs,
        orgs_by_status=orgs_by_status,
        org_users=org_users,
        next_ids=next_ids,
        batches=batches,
    )


def test_difficult_unit_distribution_and_determinism(baseline: ConstructionBaseline):
    coordinator = EvolutionCoordinator(baseline, seed=42)

    # Deterministic output for same org_id
    res1, reason1 = coordinator.is_difficult_unit(10)
    res2, reason2 = coordinator.is_difficult_unit(10)
    assert res1 == res2
    assert reason1 == reason2

    # Check distribution over 500 virtual IDs
    difficult_count = sum(coordinator.is_difficult_unit(i)[0] for i in range(1, 501))
    rate = difficult_count / 500
    # Expected around 4% (2% to 6%)
    assert 0.02 <= rate <= 0.06


def test_normal_unit_evolves_towards_graduation(baseline: ConstructionBaseline):
    coordinator = EvolutionCoordinator(baseline, seed=42)
    cur_date = date(2026, 9, 5)

    # Unit 1 is in 准备中
    metrics_before = coordinator.unit_metrics[1].static_rate
    events = coordinator.evolve_unit_step(1, cur_date)
    assert len(events) > 0
    metrics_after = coordinator.unit_metrics[1].static_rate
    assert metrics_after >= metrics_before


def test_contradiction_meshing_perfect_alignment(baseline: ConstructionBaseline):
    """
    Core Phase D acceptance test:
    Verify that units held back by the Lifecycle Advancer (spear) match EXACTLY
    with units flagged by the Risk & Governance View (shield).
    """
    thresholds = LifecycleThresholds(
        prep_consecutive_days_min=1,
        dual_ready_consecutive_days_min=1,
        dual_run_consecutive_days_min=1,
    )
    coordinator = EvolutionCoordinator(baseline, thresholds=thresholds, seed=42)
    cur_date = date(2026, 9, 5)

    # Evolve all units over several steps
    candidate_ids = list(baseline.orgs.keys())
    for _ in range(3):
        for oid in candidate_ids:
            coordinator.evolve_unit_step(oid, cur_date)

    # Force specific friction on unit 3 and unit 16 for testing edge conditions
    coordinator.unit_metrics[3].opening_diff_amount = Decimal("5000.00")
    coordinator.unit_metrics[3].has_blocking_risk = True

    coordinator.unit_metrics[16].dual_run_consistency_rate = 94.0
    coordinator.unit_metrics[16].dual_run_recent_matches = 0
    coordinator.unit_metrics[16].has_blocking_risk = True

    report = coordinator.inspect_contradiction_meshing(candidate_ids, cur_date)

    assert report.is_perfectly_meshed is True
    assert len(report.unmeshed_advancer_only) == 0
    assert len(report.unmeshed_risk_only) == 0
    assert 3 in report.meshed_units
    assert 16 in report.meshed_units
    assert report.held_back_units_count == report.risk_flagged_units_count
