"""Regression tests for business corpus static asset loading, deterministic retrieval,
and integration into the simulation engine (KI-034 Phase 3).
"""

from __future__ import annotations

import socket

from simulation.business_corpus import (
    ASSET_PATH,
    get_corpus_stats,
    get_friction_reason,
    get_transition_review_notes,
    load_corpus,
)
from simulation.construction_playbooks import TransitionReviewPlaybook
from simulation.engine_context import ConstructionBaseline
from simulation.evolution_coordinator import EvolutionCoordinator


def test_corpus_asset_exists_and_meets_volume_criteria():
    """Verify that the static business corpus asset exists and satisfies quantity requirements."""
    assert ASSET_PATH.exists(), f"Corpus asset file {ASSET_PATH} must exist"
    stats = get_corpus_stats()

    # Criteria: >= 300 friction items, >= 200 transition review items, >= 500 total
    assert stats["totalFrictions"] >= 300, f"Expected >= 300 frictions, got {stats['totalFrictions']}"
    assert stats["totalReviews"] >= 200, f"Expected >= 200 reviews, got {stats['totalReviews']}"
    assert stats["totalCount"] >= 500, f"Expected >= 500 total, got {stats['totalCount']}"

    # Category checks for frictions (5 categories)
    expected_fric_cats = {
        "legacy_data",
        "interface_network",
        "voucher_dual_run",
        "org_permission",
        "business_process",
    }
    assert set(stats["frictionCategories"].keys()) == expected_fric_cats
    for cat, count in stats["frictionCategories"].items():
        assert count >= 40, f"Category {cat} should have sufficient items, got {count}"

    # Stage checks for milestone transition reviews (5 standard transitions)
    expected_review_keys = {
        "未启动->准备中",
        "准备中->已具备双轨条件",
        "已具备双轨条件->双轨运行中",
        "双轨运行中->已上线",
        "已上线->稳定运行",
    }
    assert set(stats["reviewTransitions"].keys()) == expected_review_keys
    for stage, count in stats["reviewTransitions"].items():
        assert count >= 40, f"Transition {stage} should have sufficient items, got {count}"


def test_corpus_quality_and_safety():
    """Verify corpus items are professional, realistic SOE financial content without placeholder leak."""
    corpus = load_corpus()
    forbidden_tokens = ["TODO", "FIXME", "XXX", "李四", "张三", "王五", "阿里巴巴", "腾讯", "华为"]

    for cat, items in corpus.get("frictions", {}).items():
        for item in items:
            assert len(item) >= 15, f"Friction item too short in {cat}: {item}"
            for token in forbidden_tokens:
                assert token not in item, f"Forbidden token '{token}' found in item: {item}"

    for transition, items in corpus.get("transition_reviews", {}).items():
        for item in items:
            assert item.startswith("【阶段跃迁评审决议】"), f"Review item missing prefix: {item}"
            assert len(item) >= 25, f"Review item too short in {transition}: {item}"
            for token in forbidden_tokens:
                assert token not in item, f"Forbidden token '{token}' found in item: {item}"


def test_friction_determinism_and_reproducibility():
    """Verify that same org_id always yields identical friction reason (deterministic contract)."""
    test_org_ids = [1, 2, 7, 18, 42, 100, 199, 305, 512, 1024]
    for org_id in test_org_ids:
        first_result = get_friction_reason(org_id)
        for _ in range(20):
            assert get_friction_reason(org_id) == first_result


def test_friction_distribution_across_categories():
    """Verify that varying org_ids distribute broadly across all 5 categories and items."""
    corpus = load_corpus()
    all_frictions = set()
    for cat_items in corpus.get("frictions", {}).values():
        all_frictions.update(cat_items)

    collected_reasons = set()
    for org_id in range(1, 201):
        reason = get_friction_reason(org_id)
        assert reason in all_frictions
        collected_reasons.add(reason)

    # Across 200 different org_ids, we should see high diversity (>= 50 distinct reasons)
    assert len(collected_reasons) >= 50, f"Diversity too low: got {len(collected_reasons)}"


def test_transition_review_determinism_and_stages():
    """Verify that get_transition_review_notes is deterministic per stage and org_id."""
    stages = [
        ("未启动", "准备中"),
        ("准备中", "已具备双轨条件"),
        ("已具备双轨条件", "双轨运行中"),
        ("双轨运行中", "已上线"),
        ("已上线", "稳定运行"),
    ]

    for from_st, to_st in stages:
        res1 = get_transition_review_notes(from_st, to_st, org_id=42)
        res2 = get_transition_review_notes(from_st, to_st, org_id=42)
        assert res1 == res2
        assert res1.startswith("【阶段跃迁评审决议】")

        # Different org gets deterministic note
        res_other = get_transition_review_notes(from_st, to_st, org_id=99)
        assert res_other.startswith("【阶段跃迁评审决议】")


def test_zero_runtime_network_llm_contract(monkeypatch):
    """Verify that business corpus operations operate completely offline with strictly zero network calls."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("Illegal network call during business corpus runtime retrieval!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # Perform repeated retrievals
    for org_id in range(1, 50):
        _ = get_friction_reason(org_id)
        _ = get_transition_review_notes("准备中", "已具备双轨条件", org_id)


def test_evolution_coordinator_integration_with_corpus():
    """Verify EvolutionCoordinator uses the authentic corpus for difficult units deterministically."""
    from datetime import date, datetime

    # Minimal baseline
    orgs = {i: {"id": i, "name": f"Org_{i}", "batch_id": 1, "status": "准备中", "region": "华北", "start_date": date(2026, 8, 1), "end_date": date(2026, 12, 1)} for i in range(1, 101)}
    orgs_by_status = {"准备中": list(orgs.keys())}
    baseline = ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs=orgs,
        orgs_by_status=orgs_by_status,
        org_users={i: [{"name": f"User_{i}", "role": "会计"}] for i in range(1, 101)},
        next_ids={"construction_task": 1, "training": 1, "dual_run_result": 1},
        batches={1: {"id": 1, "name": "B1", "start_date": date(2026, 8, 1), "end_date": date(2026, 12, 1), "status": "进行中"}},
    )

    coordinator = EvolutionCoordinator(baseline, seed=42)
    difficult_reasons = []
    for oid in range(1, 101):
        is_diff, reason = coordinator.is_difficult_unit(oid)
        if is_diff:
            assert reason is not None
            assert len(reason) >= 15
            difficult_reasons.append(reason)
            # Check determinism on subsequent call
            assert coordinator.is_difficult_unit(oid) == (True, reason)

    # Check that we found some difficult units (~4%)
    assert len(difficult_reasons) >= 1


def test_transition_playbook_integration_with_corpus():
    """Verify TransitionReviewPlaybook uses authentic corpus notes when review_notes is not provided."""
    from datetime import date, datetime

    orgs = {
        10: {"id": 10, "name": "Org_10", "batch_id": 1, "status": "准备中", "region": "华北", "start_date": date(2026, 8, 1), "end_date": date(2026, 12, 1)}
    }
    baseline = ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs=orgs,
        orgs_by_status={"准备中": [10]},
        org_users={10: [{"name": "User_10", "role": "会计"}]},
        next_ids={"construction_task": 1, "training": 1, "dual_run_result": 1},
        batches={1: {"id": 1, "name": "B1", "start_date": date(2026, 8, 1), "end_date": date(2026, 12, 1), "status": "进行中"}},
    )

    playbook = TransitionReviewPlaybook(baseline, seed=42)
    ev = playbook.generate(org_id=10, event_date=date(2026, 9, 5), from_status="准备中", to_status="已具备双轨条件")
    assert ev.review_notes.startswith("【阶段跃迁评审决议】")
    assert any(term in ev.review_notes for term in ["准入", "评审", "验收", "评估", "核实", "标准", "推进"])
