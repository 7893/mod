"""Unit tests for construction event footprint models and deterministic validation rules.

Phase A: Pure generation & validation in-memory tests (no database access, no writes).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.simulation.construction_models import (
    BatchRolloutEventFootprint,
    ConstructionTaskFootprint,
    DataReadinessEventFootprint,
    DataReadinessRecordFootprint,
    DualRunCheckEventFootprint,
    DualRunResultRecordFootprint,
    InterfaceDebuggingEventFootprint,
    OrgUnitStatusUpdateFootprint,
    PoolOnboardingEventFootprint,
    RolloutBatchUpdateFootprint,
    RolloutStatusSnapshotFootprint,
    TrainingCertificationEventFootprint,
    TrainingRecordFootprint,
    TransitionReviewEventFootprint,
    validate_batch_rollout,
    validate_construction_event,
    validate_data_readiness,
    validate_dual_run_check,
    validate_interface_debugging,
    validate_pool_onboarding,
    validate_training_certification,
    validate_transition_review,
)


# ---------------------------------------------------------------------------
# Helpers for valid test fixtures
# ---------------------------------------------------------------------------


def _create_sample_task(
    id: int = 101,
    org_id: int = 10,
    name: str = "生产与容灾服务器资源规划",
    task_type: str = "基础环境",
    owner: str = "张三",
    plan_time: date = date(2026, 9, 10),
    actual_time: date | None = None,
    status: str = "进行中",
    progress: int = 50,
    update_time: date = date(2026, 9, 5),
) -> ConstructionTaskFootprint:
    return ConstructionTaskFootprint(
        id=id,
        org_id=org_id,
        name=name,
        type=task_type,
        owner=owner,
        plan_time=plan_time,
        actual_time=actual_time,
        status=status,
        progress=progress,
        update_time=update_time,
    )


def _create_sample_onboarding(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
) -> PoolOnboardingEventFootprint:
    task = _create_sample_task(
        org_id=org_id,
        name="网络专线连通与防火墙策略开通",
        task_type="基础环境",
        status="进行中",
        progress=20,
        update_time=event_date,
    )
    return PoolOnboardingEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        status_update=OrgUnitStatusUpdateFootprint(
            id=org_id,
            from_status="未启动",
            to_status="准备中",
            update_date=event_date,
        ),
        snapshot=RolloutStatusSnapshotFootprint(
            org_id=org_id,
            snapshot_date=event_date,
            status="准备中",
        ),
        initial_tasks=[task],
    )


def _create_sample_readiness(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
) -> DataReadinessEventFootprint:
    readiness = DataReadinessRecordFootprint(
        org_id=org_id,
        batch_id=batch_id,
        static_total=100,
        static_completed=85,
        static_rate="85.0%",
        opening_total=50,
        opening_completed=40,
        opening_rate="80.0%",
        opening_diff_amount=Decimal("0.00"),
        dynamic_total=200,
        dynamic_completed=180,
        dynamic_sync_success=170,
        dynamic_sync_fail=10,
        dynamic_sync_pending=20,
        dynamic_rate="85.0%",
        overall_status="收集中",
        last_sync_time="2026-09-05 10:00:00",
    )
    task = _create_sample_task(
        org_id=org_id,
        name="存货与物料编码分类标准对齐",
        task_type="基础数据",
        status="进行中",
        progress=85,
        update_time=event_date,
    )
    return DataReadinessEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        readiness=readiness,
        associated_task=task,
    )


def _create_sample_training(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
) -> TrainingCertificationEventFootprint:
    training = TrainingRecordFootprint(
        id=501,
        org_id=org_id,
        batch_id=batch_id,
        type="业务操作与财务处理培训",
        date=event_date,
        mode="现场实操",
        expected=20,
        actual=18,
        absent=2,
        passed=16,
        makeup=2,
        cert_count=18,
    )
    task = _create_sample_task(
        org_id=org_id,
        name="骨干业务人员与关键用户专题深化培训",
        task_type="用户培训",
        status="进行中",
        progress=90,
        update_time=event_date,
    )
    return TrainingCertificationEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        training=training,
        associated_task=task,
    )


def _create_sample_debugging(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
) -> InterfaceDebuggingEventFootprint:
    task = _create_sample_task(
        org_id=org_id,
        name="资金管理系统银企直联流水回传联调",
        task_type="接口联调",
        status="已完成",
        progress=100,
        actual_time=event_date,
        update_time=event_date,
    )
    return InterfaceDebuggingEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        task=task,
        interface_name="银企直联流水回传接口",
        test_case_count=25,
        test_passed_count=25,
    )


def _create_sample_dual_run(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
    matched: bool = True,
) -> DualRunCheckEventFootprint:
    v1 = Decimal("1502400.50")
    v2 = v1 if matched else Decimal("1502100.00")
    diff = abs(v1 - v2)
    res = "一致" if matched else "不一致"
    record = DualRunResultRecordFootprint(
        id=601,
        org_id=org_id,
        check_type="业务单据金额核对",
        v1_amount=v1,
        v2_amount=v2,
        diff_amount=diff,
        result=res,
        check_date=event_date,
    )
    task = _create_sample_task(
        org_id=org_id,
        name="新旧系统首周业务单据与凭证平行核对",
        task_type="双轨验证",
        status="进行中",
        progress=80,
        update_time=event_date,
    )
    return DualRunCheckEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        dual_run=record,
        associated_task=task,
    )


def _create_sample_transition(
    org_id: int = 10,
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
    from_status: str = "已具备双轨条件",
    to_status: str = "双轨运行中",
) -> TransitionReviewEventFootprint:
    return TransitionReviewEventFootprint(
        org_id=org_id,
        batch_id=batch_id,
        event_date=event_date,
        from_status=from_status,
        to_status=to_status,
        review_notes="经专家组综合评审，前期接口联调全部跑通，数据准确性达标，准予进入双轨运行阶段。",
        status_update=OrgUnitStatusUpdateFootprint(
            id=org_id,
            from_status=from_status,
            to_status=to_status,
            update_date=event_date,
        ),
        snapshot=RolloutStatusSnapshotFootprint(
            org_id=org_id,
            snapshot_date=event_date,
            status=to_status,
        ),
    )


def _create_sample_batch_rollout(
    batch_id: int = 2,
    event_date: date = date(2026, 9, 5),
    from_status: str = "准备中",
    to_status: str = "双轨运行中",
) -> BatchRolloutEventFootprint:
    return BatchRolloutEventFootprint(
        batch_id=batch_id,
        event_date=event_date,
        from_status=from_status,
        to_status=to_status,
        batch_update=RolloutBatchUpdateFootprint(
            id=batch_id,
            name="第二批",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 10, 15),
            status=to_status,
        ),
        reason="第二批过半数单位已满足双轨条件，批次整体转入双轨推进。",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_pool_onboarding_success():
    event = _create_sample_onboarding()
    validate_pool_onboarding(event)
    validate_construction_event(event)


def test_pool_onboarding_invalid_from_status():
    event = _create_sample_onboarding()
    event.status_update.from_status = "准备中"
    with pytest.raises(ValueError, match="Pool onboarding must start from '未启动'"):
        validate_pool_onboarding(event)


def test_pool_onboarding_missing_tasks():
    event = _create_sample_onboarding()
    event.initial_tasks = []
    with pytest.raises(ValueError, match="must produce at least one initial task"):
        validate_pool_onboarding(event)


def test_pool_onboarding_empty_task_owner():
    event = _create_sample_onboarding()
    event.initial_tasks[0].owner = "   "
    with pytest.raises(ValueError, match="Task owner must not be empty"):
        validate_pool_onboarding(event)


def test_data_readiness_success():
    event = _create_sample_readiness()
    validate_data_readiness(event)
    validate_construction_event(event)


def test_data_readiness_rate_mismatch():
    event = _create_sample_readiness()
    event.readiness.static_rate = "90.0%"  # actual is 85/100 -> 85.0%
    with pytest.raises(ValueError, match="Static rate mismatch"):
        validate_data_readiness(event)


def test_data_readiness_sync_sum_mismatch():
    event = _create_sample_readiness()
    event.readiness.dynamic_sync_pending = 15  # 170 + 10 + 15 = 195 != 200
    with pytest.raises(ValueError, match="Dynamic sync sum mismatch"):
        validate_data_readiness(event)


def test_data_readiness_invalid_task_type():
    event = _create_sample_readiness()
    event.associated_task.type = "用户培训"
    with pytest.raises(ValueError, match="must be 基础数据/期初数据"):
        validate_data_readiness(event)


def test_training_certification_success():
    event = _create_sample_training()
    validate_training_certification(event)
    validate_construction_event(event)


def test_training_attendance_mismatch():
    event = _create_sample_training()
    event.training.absent = 5  # 18 + 5 != 20
    with pytest.raises(ValueError, match="Training attendance mismatch"):
        validate_training_certification(event)


def test_training_passed_exceeds_actual():
    event = _create_sample_training()
    event.training.passed = 19  # actual is 18
    with pytest.raises(ValueError, match="passed count .* out of range"):
        validate_training_certification(event)


def test_training_cert_exceeds_qualified():
    event = _create_sample_training()
    event.training.cert_count = 19  # passed(16) + makeup(2) = 18
    with pytest.raises(ValueError, match="Cert count .* exceeds total qualified"):
        validate_training_certification(event)


def test_interface_debugging_success():
    event = _create_sample_debugging()
    validate_interface_debugging(event)
    validate_construction_event(event)


def test_interface_debugging_incomplete_tests_marked_complete():
    event = _create_sample_debugging()
    event.test_passed_count = 20  # only 20 passed out of 25, but task is 已完成
    with pytest.raises(ValueError, match="completed but not all test cases passed"):
        validate_interface_debugging(event)


def test_interface_debugging_empty_name():
    event = _create_sample_debugging()
    event.interface_name = "  "
    with pytest.raises(ValueError, match="Interface name must not be empty"):
        validate_interface_debugging(event)


def test_dual_run_check_matched():
    event = _create_sample_dual_run(matched=True)
    validate_dual_run_check(event)
    validate_construction_event(event)


def test_dual_run_check_unmatched():
    event = _create_sample_dual_run(matched=False)
    validate_dual_run_check(event)
    validate_construction_event(event)


def test_dual_run_check_diff_mismatch():
    event = _create_sample_dual_run(matched=False)
    event.dual_run.diff_amount = Decimal("10.00")  # recorded diff doesn't match |v1 - v2|
    with pytest.raises(ValueError, match="diff_amount mismatch"):
        validate_dual_run_check(event)


def test_dual_run_check_inconsistent_result():
    event = _create_sample_dual_run(matched=True)
    event.dual_run.result = "不一致"  # diff is 0.00 but result says 不一致
    with pytest.raises(ValueError, match="Zero diff_amount must have result '一致'"):
        validate_dual_run_check(event)


def test_transition_review_success():
    event = _create_sample_transition(
        from_status="已具备双轨条件", to_status="双轨运行中"
    )
    validate_transition_review(event)
    validate_construction_event(event)


def test_transition_review_prevent_regression():
    # Only forward single-step transitions are allowed! Regressions are forbidden.
    event = _create_sample_transition(
        from_status="双轨运行中", to_status="已具备双轨条件"
    )
    with pytest.raises(ValueError, match="Invalid transition progression"):
        validate_transition_review(event)


def test_transition_review_prevent_skipping_stages():
    # Skipping steps (未启动 -> 已具备双轨条件) is forbidden.
    event = _create_sample_transition(
        from_status="未启动", to_status="已具备双轨条件"
    )
    with pytest.raises(ValueError, match="Invalid transition progression"):
        validate_transition_review(event)


def test_transition_review_empty_notes():
    event = _create_sample_transition()
    event.review_notes = ""
    with pytest.raises(ValueError, match="review_notes must not be empty"):
        validate_transition_review(event)


def test_batch_rollout_success():
    event = _create_sample_batch_rollout(
        from_status="准备中", to_status="双轨运行中"
    )
    validate_batch_rollout(event)
    validate_construction_event(event)


def test_batch_rollout_invalid_dates():
    event = _create_sample_batch_rollout()
    event.batch_update.start_date = date(2026, 12, 1)
    event.batch_update.end_date = date(2026, 1, 1)
    with pytest.raises(ValueError, match="start_date .* later than end_date"):
        validate_batch_rollout(event)


def test_construction_event_type_error():
    with pytest.raises(TypeError, match="Unknown construction event footprint type"):
        validate_construction_event("invalid_event")
