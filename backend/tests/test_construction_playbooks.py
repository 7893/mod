"""Unit tests for the 7 construction playbooks and causal gates.

Phase B: In-memory tests for playbooks, gates, user assignment, and footprint validation.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from simulation.construction_playbooks import (
    BatchRolloutPlaybook,
    DataReadinessPlaybook,
    DualRunCheckPlaybook,
    InterfaceDebuggingPlaybook,
    PoolOnboardingPlaybook,
    TrainingCertificationPlaybook,
    TransitionReviewPlaybook,
)
from simulation.engine_context import ConstructionBaseline, IdAllocator


@pytest.fixture
def baseline() -> ConstructionBaseline:
    orgs = {
        1: {"id": 1, "name": "单位1_未启动", "batch_id": 1, "status": "未启动", "region": "华北", "start_date": date(2026, 9, 1), "end_date": date(2026, 12, 1)},
        2: {"id": 2, "name": "单位2_准备中", "batch_id": 1, "status": "准备中", "region": "华东", "start_date": date(2026, 8, 1), "end_date": date(2026, 11, 1)},
        3: {"id": 3, "name": "单位3_已具备双轨条件", "batch_id": 1, "status": "已具备双轨条件", "region": "华南", "start_date": date(2026, 7, 1), "end_date": date(2026, 10, 1)},
        4: {"id": 4, "name": "单位4_双轨运行中", "batch_id": 1, "status": "双轨运行中", "region": "华中", "start_date": date(2026, 6, 1), "end_date": date(2026, 9, 1)},
        5: {"id": 5, "name": "单位5_已上线", "batch_id": 1, "status": "已上线", "region": "西南", "start_date": date(2026, 5, 1), "end_date": date(2026, 8, 1)},
    }
    orgs_by_status = {
        "未启动": [1],
        "准备中": [2],
        "已具备双轨条件": [3],
        "双轨运行中": [4],
        "已上线": [5],
    }
    org_users = {
        1: [{"name": "张伟", "role": "会计"}],
        2: [{"name": "李强", "role": "出纳"}],
        3: [{"name": "王芳", "role": "财务主管"}],
        4: [{"name": "赵敏", "role": "总账会计"}],
        5: [{"name": "刘洋", "role": "项目经理"}],
    }
    batches = {
        1: {"id": 1, "name": "第一批", "start_date": date(2026, 1, 1), "end_date": date(2026, 10, 31), "status": "准备中"},
    }
    next_ids = {
        "construction_task": 1000,
        "training": 2000,
        "dual_run_result": 3000,
    }
    return ConstructionBaseline(
        latest_business_date=datetime(2026, 9, 4, 18, 0, 0),
        orgs=orgs,
        orgs_by_status=orgs_by_status,
        org_users=org_users,
        next_ids=next_ids,
        batches=batches,
    )


def test_pool_onboarding_playbook_success(baseline: ConstructionBaseline):
    playbook = PoolOnboardingPlaybook(baseline, seed=42)
    allocator = IdAllocator(baseline.next_ids)
    event = playbook.generate(org_id=1, event_date=date(2026, 9, 5), id_allocator=allocator)

    assert event.org_id == 1
    assert event.status_update.from_status == "未启动"
    assert event.status_update.to_status == "准备中"
    assert len(event.initial_tasks) == 2
    assert all(t.owner == "张伟" for t in event.initial_tasks)


def test_pool_onboarding_playbook_gate_violation(baseline: ConstructionBaseline):
    playbook = PoolOnboardingPlaybook(baseline)
    with pytest.raises(ValueError, match="Gate violated: org 2 status is '准备中'"):
        playbook.generate(org_id=2, event_date=date(2026, 9, 5))


def test_data_readiness_playbook_success(baseline: ConstructionBaseline):
    playbook = DataReadinessPlaybook(baseline, seed=42)
    event = playbook.generate(
        org_id=2,
        event_date=date(2026, 9, 5),
        static_completed=60,
        static_total=60,
        opening_completed=80,
        opening_total=80,
        dynamic_total=100,
        dynamic_fail=0,
        dynamic_pending=0,
    )
    assert event.readiness.static_rate == "100.0%"
    assert event.readiness.opening_rate == "100.0%"
    assert event.readiness.dynamic_rate == "100.0%"
    assert event.readiness.overall_status == "已导入"
    assert event.associated_task.status == "已完成"
    assert event.associated_task.owner == "李强"


def test_data_readiness_playbook_gate_violation(baseline: ConstructionBaseline):
    playbook = DataReadinessPlaybook(baseline)
    with pytest.raises(ValueError, match="Gate violated: org 1 status is '未启动'"):
        playbook.generate(org_id=1, event_date=date(2026, 9, 5))


def test_training_certification_playbook_success(baseline: ConstructionBaseline):
    playbook = TrainingCertificationPlaybook(baseline, seed=42)
    allocator = IdAllocator(baseline.next_ids)
    event = playbook.generate(
        org_id=2,
        event_date=date(2026, 9, 5),
        id_allocator=allocator,
        expected=20,
        absent=1,
        unpassed=2,
    )
    assert event.training.actual == 19
    assert event.training.passed == 17
    assert event.training.makeup == 2
    assert event.training.cert_count == 19
    assert event.associated_task.owner == "李强"


def test_interface_debugging_playbook_success(baseline: ConstructionBaseline):
    playbook = InterfaceDebuggingPlaybook(baseline, seed=42)
    allocator = IdAllocator(baseline.next_ids)
    event = playbook.generate(
        org_id=3,
        event_date=date(2026, 9, 5),
        id_allocator=allocator,
        completed=True,
    )
    assert event.task.type == "接口联调"
    assert event.task.status == "已完成"
    assert event.test_passed_count == event.test_case_count
    assert event.task.owner == "王芳"


def test_dual_run_check_playbook_matched(baseline: ConstructionBaseline):
    playbook = DualRunCheckPlaybook(baseline, seed=42)
    allocator = IdAllocator(baseline.next_ids)
    event = playbook.generate(
        org_id=4,
        event_date=date(2026, 9, 5),
        id_allocator=allocator,
        force_diff=False,
    )
    assert event.dual_run.result == "一致"
    assert event.dual_run.diff_amount == Decimal("0.00")
    assert event.associated_task.owner == "赵敏"


def test_dual_run_check_playbook_forced_diff(baseline: ConstructionBaseline):
    playbook = DualRunCheckPlaybook(baseline, seed=42)
    allocator = IdAllocator(baseline.next_ids)
    event = playbook.generate(
        org_id=4,
        event_date=date(2026, 9, 5),
        id_allocator=allocator,
        force_diff=True,
    )
    assert event.dual_run.result == "不一致"
    assert event.dual_run.diff_amount > Decimal("0.00")
    assert event.associated_task.status == "进行中"


def test_dual_run_check_playbook_gate_violation(baseline: ConstructionBaseline):
    playbook = DualRunCheckPlaybook(baseline)
    # Unit 2 is in 准备中, not 双轨运行中 -> MUST fail causal gate!
    with pytest.raises(ValueError, match="Gate violated: org 2 status is '准备中', expected '双轨运行中'"):
        playbook.generate(org_id=2, event_date=date(2026, 9, 5))


def test_transition_review_playbook_success(baseline: ConstructionBaseline):
    playbook = TransitionReviewPlaybook(baseline, seed=42)
    event = playbook.generate(
        org_id=3,
        event_date=date(2026, 9, 5),
        from_status="已具备双轨条件",
        to_status="双轨运行中",
    )
    assert event.status_update.to_status == "双轨运行中"
    assert event.snapshot.status == "双轨运行中"
    assert len(event.review_notes) > 10


def test_transition_review_playbook_gate_violation(baseline: ConstructionBaseline):
    playbook = TransitionReviewPlaybook(baseline)
    # Unit 1 is 未启动, trying to review from 准备中
    with pytest.raises(ValueError, match="Gate violated: org 1 current status is '未启动', expected '准备中'"):
        playbook.generate(
            org_id=1,
            event_date=date(2026, 9, 5),
            from_status="准备中",
            to_status="已具备双轨条件",
        )


def test_batch_rollout_playbook_success(baseline: ConstructionBaseline):
    playbook = BatchRolloutPlaybook(baseline, seed=42)
    event = playbook.generate(
        batch_id=1,
        event_date=date(2026, 9, 5),
        from_status="准备中",
        to_status="双轨运行中",
    )
    assert event.batch_update.status == "双轨运行中"
    assert "第一批" in event.batch_update.name
