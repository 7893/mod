"""Construction event footprint models and deterministic validation rules.

Defines data structures and deterministic cross-table consistency checks for
the 7 core construction lifecycle events:
1. PoolOnboardingEventFootprint (入池事件)
2. DataReadinessEventFootprint (数据准备事件)
3. TrainingCertificationEventFootprint (培训认证事件)
4. InterfaceDebuggingEventFootprint (接口联调事件)
5. DualRunCheckEventFootprint (双轨核对事件)
6. TransitionReviewEventFootprint (跃迁评审事件)
7. BatchRolloutEventFootprint (批次推进事件)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

# Lifecycle stage chains (strictly ordered, forward-only)
ORG_LIFECYCLE_STAGES = (
    "未启动",
    "准备中",
    "已具备双轨条件",
    "双轨运行中",
    "已上线",
    "稳定运行",
)

BATCH_LIFECYCLE_STAGES = (
    "未启动",
    "准备中",
    "双轨运行中",
    "已上线",
    "稳定运行",
)

TASK_TYPES = (
    "基础环境",
    "基础数据",
    "组织权限",
    "期初数据",
    "用户培训",
    "接口联调",
    "双轨验证",
    "上线切换",
)

TASK_STATUSES = ("未开始", "进行中", "已完成")
DUAL_RUN_CHECK_TYPES = ("业务单据金额核对", "凭证借贷汇总核对", "月末科目余额比对")
DUAL_RUN_RESULTS = ("一致", "不一致")
READINESS_OVERALL_STATUSES = ("未收集", "收集中", "校验通过", "已导入")

# 真实财务双轨核对不一致原因专业语料库 (KI-053)
DUAL_RUN_DIFFERENCE_REASONS: Dict[str, List[str]] = {
    "月末科目余额比对": [
        "月末总账外币折算总账结汇截断时差（汇兑损益偏差）",
        "新老系统二级科目挂账科目映射规则不一致",
        "预付账款跨期分摊与待摊费用截断时差",
        "母子公司内部往来账双向抵销时间窗口未对齐",
        "月末计提税费重算时差导致科目余额微差",
    ],
    "凭证借贷汇总核对": [
        "新老系统银行对账单单边暂估调整分录未同步过账",
        "固定资产多级折旧计提四舍五入累计尾差（借贷微差）",
        "增值税多级税率重算分录尾差（借贷不平0.04~0.82元）",
        "跨期收付转借贷科目汇总截断时间窗口不一致",
        "工会经费与职工福利费计提科目归集口径微差",
    ],
    "业务单据金额核对": [
        "采购发票跨期认证结算单据与暂估冲销金额差异",
        "冲销凭证与历史红字发票关联钩稽时间差",
        "跨期差旅报销单据尾数拆分与扣税重算差异",
        "项目工程进度款预留质保金与应付款项账龄折算尾差",
        "合同分期付款单据币种换算小数位截断偏差",
    ],
}


# ---------------------------------------------------------------------------
# Single-table row footprint models
# ---------------------------------------------------------------------------


@dataclass
class ConstructionTaskFootprint:
    """Footprint for construction_task table."""

    id: int
    org_id: int
    name: str
    type: str
    owner: str
    plan_time: date
    actual_time: Optional[date]
    status: str
    progress: int
    update_time: date


@dataclass
class RolloutStatusSnapshotFootprint:
    """Footprint for rollout_status_snapshot table (composite PK: org_id + snapshot_date)."""

    org_id: int
    snapshot_date: date
    status: str


@dataclass
class OrgUnitStatusUpdateFootprint:
    """Footprint for controlled update to org_unit.status."""

    id: int
    from_status: str
    to_status: str
    update_date: date


@dataclass
class RolloutBatchUpdateFootprint:
    """Footprint for rollout_batch status advancement."""

    id: int
    name: str
    start_date: date
    end_date: date
    status: str


@dataclass
class SysUserFootprint:
    """Footprint for sys_user table."""

    id: int
    name: str
    org_id: int
    role: str
    job: str


@dataclass
class DataReadinessRecordFootprint:
    """Footprint for data_readiness table."""

    org_id: int
    batch_id: int
    static_total: int
    static_completed: int
    static_rate: str
    opening_total: int
    opening_completed: int
    opening_rate: str
    opening_diff_amount: Decimal
    dynamic_total: int
    dynamic_completed: int
    dynamic_sync_success: int
    dynamic_sync_fail: int
    dynamic_sync_pending: int
    dynamic_rate: str
    overall_status: str
    last_sync_time: Optional[str] = None


@dataclass
class TrainingRecordFootprint:
    """Footprint for training table."""

    id: int
    org_id: int
    batch_id: int
    type: str
    date: date
    mode: str
    expected: int
    actual: int
    absent: int
    passed: int
    makeup: int
    cert_count: int


@dataclass
class DualRunResultRecordFootprint:
    """Footprint for dual_run_result table."""

    id: int
    org_id: int
    check_type: str
    v1_amount: Decimal
    v2_amount: Decimal
    diff_amount: Decimal
    result: str
    check_date: date
    difference_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 7 Core Construction Event Footprints
# ---------------------------------------------------------------------------


@dataclass
class PoolOnboardingEventFootprint:
    """Event 1: Org unit onboarding into active construction batch (未启动 -> 准备中)."""

    org_id: int
    batch_id: int
    event_date: date
    status_update: OrgUnitStatusUpdateFootprint
    snapshot: RolloutStatusSnapshotFootprint
    initial_tasks: List[ConstructionTaskFootprint] = field(default_factory=list)


@dataclass
class DataReadinessEventFootprint:
    """Event 2: Data readiness progression & sync."""

    org_id: int
    batch_id: int
    event_date: date
    readiness: DataReadinessRecordFootprint
    associated_task: ConstructionTaskFootprint


@dataclass
class TrainingCertificationEventFootprint:
    """Event 3: User training session and certification record."""

    org_id: int
    batch_id: int
    event_date: date
    training: TrainingRecordFootprint
    associated_task: ConstructionTaskFootprint


@dataclass
class InterfaceDebuggingEventFootprint:
    """Event 4: Interface testing, debugging, and verification."""

    org_id: int
    batch_id: int
    event_date: date
    task: ConstructionTaskFootprint
    interface_name: str
    test_case_count: int
    test_passed_count: int


@dataclass
class DualRunCheckEventFootprint:
    """Event 5: Parallel dual-run comparison between V1 and V2."""

    org_id: int
    batch_id: int
    event_date: date
    dual_run: DualRunResultRecordFootprint
    associated_task: ConstructionTaskFootprint


@dataclass
class TransitionReviewEventFootprint:
    """Event 6: Formal milestone review & lifecycle phase transition."""

    org_id: int
    batch_id: int
    event_date: date
    from_status: str
    to_status: str
    review_notes: str
    status_update: OrgUnitStatusUpdateFootprint
    snapshot: RolloutStatusSnapshotFootprint
    milestone_task: Optional[ConstructionTaskFootprint] = None


@dataclass
class BatchRolloutEventFootprint:
    """Event 7: Rollout batch overall milestone advancement."""

    batch_id: int
    event_date: date
    from_status: str
    to_status: str
    batch_update: RolloutBatchUpdateFootprint
    reason: str


@dataclass
class NewOrgAdmissionFootprint:
    """Event 8 (KI-035): New SOE organization admission into Batch 8 dynamic reserve pool."""

    org_id: int
    name: str
    region: str
    batch_id: int = 8
    status: str = "未启动"
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=lambda: date.today() + timedelta(days=500))
    users: List[SysUserFootprint] = field(default_factory=list)
    tasks: List[ConstructionTaskFootprint] = field(default_factory=list)
    readiness: Optional[DataReadinessRecordFootprint] = None
    snapshot: Optional[RolloutStatusSnapshotFootprint] = None


# ---------------------------------------------------------------------------
# Deterministic Footprint Validation Functions
# ---------------------------------------------------------------------------


def _validate_task_common(task: ConstructionTaskFootprint, expected_org_id: int) -> None:
    """Validate common constraints on a construction task footprint."""
    if task.org_id != expected_org_id:
        raise ValueError(f"Task org_id mismatch: task has {task.org_id}, expected {expected_org_id}")
    if task.type not in TASK_TYPES:
        raise ValueError(f"Invalid construction_task type: '{task.type}'")
    if task.status not in TASK_STATUSES:
        raise ValueError(f"Invalid construction_task status: '{task.status}'")
    if not (0 <= task.progress <= 100):
        raise ValueError(f"Task progress out of range [0, 100]: {task.progress}")
    if not task.owner or not task.owner.strip():
        raise ValueError("Task owner must not be empty")

    if task.status == "已完成":
        if task.progress != 100:
            raise ValueError(f"Task status is '已完成' but progress is {task.progress} (expected 100)")
        if task.actual_time is None:
            raise ValueError("Completed task must have actual_time recorded")
        if task.actual_time > task.update_time:
            raise ValueError(
                f"Task actual_time {task.actual_time} is later than update_time {task.update_time}"
            )
    elif task.status == "未开始":
        if task.progress != 0:
            raise ValueError(f"Task status is '未开始' but progress is {task.progress} (expected 0)")
        if task.actual_time is not None:
            raise ValueError("Unstarted task must not have actual_time")
    elif task.status == "进行中":
        if not (0 <= task.progress < 100):
            raise ValueError(f"In-progress task progress must be in [0, 99], got {task.progress}")


def validate_pool_onboarding(event: PoolOnboardingEventFootprint) -> None:
    """Validate PoolOnboardingEventFootprint consistency."""
    if event.status_update.id != event.org_id:
        raise ValueError(f"OrgUnit update id ({event.status_update.id}) != event org_id ({event.org_id})")
    if event.status_update.from_status != "未启动":
        raise ValueError(f"Pool onboarding must start from '未启动', got '{event.status_update.from_status}'")
    if event.status_update.to_status != "准备中":
        raise ValueError(f"Pool onboarding target must be '准备中', got '{event.status_update.to_status}'")
    if event.snapshot.org_id != event.org_id:
        raise ValueError(f"Snapshot org_id ({event.snapshot.org_id}) != event org_id ({event.org_id})")
    if event.snapshot.status != "准备中":
        raise ValueError(f"Snapshot status must be '准备中', got '{event.snapshot.status}'")
    if event.snapshot.snapshot_date != event.event_date:
        raise ValueError(f"Snapshot date ({event.snapshot.snapshot_date}) != event_date ({event.event_date})")
    if not event.initial_tasks:
        raise ValueError("Pool onboarding must produce at least one initial task")

    for t in event.initial_tasks:
        _validate_task_common(t, event.org_id)
        if t.update_time > event.event_date:
            raise ValueError(f"Task update_time {t.update_time} exceeds event_date {event.event_date}")


def validate_data_readiness(event: DataReadinessEventFootprint) -> None:
    """Validate DataReadinessEventFootprint consistency and rate arithmetic."""
    r = event.readiness
    if r.org_id != event.org_id:
        raise ValueError(f"Readiness org_id mismatch: {r.org_id} != {event.org_id}")
    if r.batch_id != event.batch_id:
        raise ValueError(f"Readiness batch_id mismatch: {r.batch_id} != {event.batch_id}")
    if r.overall_status not in READINESS_OVERALL_STATUSES:
        raise ValueError(f"Invalid overall_status: '{r.overall_status}'")

    if not (0 <= r.static_completed <= r.static_total):
        raise ValueError(f"Static completed ({r.static_completed}) out of range [0, {r.static_total}]")
    expected_static_rate = (
        f"{(r.static_completed / r.static_total * 100):.1f}%" if r.static_total > 0 else "100.0%"
    )
    if r.static_rate != expected_static_rate:
        raise ValueError(f"Static rate mismatch: got '{r.static_rate}', expected '{expected_static_rate}'")

    if not (0 <= r.opening_completed <= r.opening_total):
        raise ValueError(f"Opening completed ({r.opening_completed}) out of range [0, {r.opening_total}]")
    expected_opening_rate = (
        f"{(r.opening_completed / r.opening_total * 100):.1f}%" if r.opening_total > 0 else "100.0%"
    )
    if r.opening_rate != expected_opening_rate:
        raise ValueError(f"Opening rate mismatch: got '{r.opening_rate}', expected '{expected_opening_rate}'")
    if r.opening_diff_amount < Decimal("0.00"):
        raise ValueError(f"opening_diff_amount must be non-negative: {r.opening_diff_amount}")

    if not (0 <= r.dynamic_completed <= r.dynamic_total):
        raise ValueError(f"Dynamic completed ({r.dynamic_completed}) out of range [0, {r.dynamic_total}]")
    sync_sum = r.dynamic_sync_success + r.dynamic_sync_fail + r.dynamic_sync_pending
    if sync_sum != r.dynamic_total:
        raise ValueError(
            f"Dynamic sync sum mismatch: {r.dynamic_sync_success} + {r.dynamic_sync_fail} + "
            f"{r.dynamic_sync_pending} = {sync_sum} != total {r.dynamic_total}"
        )
    expected_dynamic_rate = (
        f"{(r.dynamic_sync_success / r.dynamic_total * 100):.1f}%" if r.dynamic_total > 0 else "100.0%"
    )
    if r.dynamic_rate != expected_dynamic_rate:
        raise ValueError(f"Dynamic rate mismatch: got '{r.dynamic_rate}', expected '{expected_dynamic_rate}'")

    _validate_task_common(event.associated_task, event.org_id)
    if event.associated_task.type not in ("基础数据", "期初数据"):
        raise ValueError(f"Data readiness task must be 基础数据/期初数据, got '{event.associated_task.type}'")


def validate_training_certification(event: TrainingCertificationEventFootprint) -> None:
    """Validate TrainingCertificationEventFootprint counts and bounds."""
    t = event.training
    if t.org_id != event.org_id:
        raise ValueError(f"Training org_id mismatch: {t.org_id} != {event.org_id}")
    if t.batch_id != event.batch_id:
        raise ValueError(f"Training batch_id mismatch: {t.batch_id} != {event.batch_id}")
    if t.expected < 0 or t.actual < 0 or t.absent < 0:
        raise ValueError("Training participant counts must be non-negative")
    if t.actual + t.absent != t.expected:
        raise ValueError(
            f"Training attendance mismatch: actual ({t.actual}) + absent ({t.absent}) "
            f"!= expected ({t.expected})"
        )
    if not (0 <= t.passed <= t.actual):
        raise ValueError(f"Training passed count ({t.passed}) out of range [0, actual={t.actual}]")
    if not (0 <= t.makeup <= (t.actual - t.passed)):
        raise ValueError(f"Training makeup ({t.makeup}) exceeds non-passed attendees ({t.actual - t.passed})")
    if not (0 <= t.cert_count <= (t.passed + t.makeup)):
        raise ValueError(f"Cert count ({t.cert_count}) exceeds total qualified ({t.passed + t.makeup})")
    if t.date > event.event_date:
        raise ValueError(f"Training date {t.date} is in the future relative to {event.event_date}")

    _validate_task_common(event.associated_task, event.org_id)
    if event.associated_task.type != "用户培训":
        raise ValueError(f"Training associated task must be '用户培训', got '{event.associated_task.type}'")


def validate_interface_debugging(event: InterfaceDebuggingEventFootprint) -> None:
    """Validate InterfaceDebuggingEventFootprint."""
    if not event.interface_name or not event.interface_name.strip():
        raise ValueError("Interface name must not be empty")
    if event.test_case_count < 0:
        raise ValueError("test_case_count must be non-negative")
    if not (0 <= event.test_passed_count <= event.test_case_count):
        raise ValueError(
            f"test_passed_count ({event.test_passed_count}) out of range [0, {event.test_case_count}]"
        )

    _validate_task_common(event.task, event.org_id)
    if event.task.type != "接口联调":
        raise ValueError(f"Task type must be '接口联调', got '{event.task.type}'")
    if event.task.status == "已完成" and event.test_passed_count != event.test_case_count:
        raise ValueError("Interface debugging completed but not all test cases passed")


def validate_dual_run_check(event: DualRunCheckEventFootprint) -> None:
    """Validate DualRunCheckEventFootprint arithmetic and consistency."""
    dr = event.dual_run
    if dr.org_id != event.org_id:
        raise ValueError(f"Dual run org_id mismatch: {dr.org_id} != {event.org_id}")
    if dr.check_type not in DUAL_RUN_CHECK_TYPES:
        raise ValueError(f"Invalid dual run check_type: '{dr.check_type}'")
    if dr.result not in DUAL_RUN_RESULTS:
        raise ValueError(f"Invalid dual run result: '{dr.result}'")

    calc_diff = abs(dr.v1_amount - dr.v2_amount)
    if dr.diff_amount != calc_diff:
        raise ValueError(f"Dual run diff_amount mismatch: recorded={dr.diff_amount}, calculated={calc_diff}")

    if calc_diff == Decimal("0.00"):
        if dr.result != "一致":
            raise ValueError("Zero diff_amount must have result '一致'")
        if dr.difference_reason:
            raise ValueError("Consistent dual run record must not have discrepancy reason")
    else:
        if dr.result != "不一致":
            raise ValueError(f"Non-zero diff_amount ({calc_diff}) must have result '不一致'")

    if dr.check_date > event.event_date:
        raise ValueError(f"Dual run check_date ({dr.check_date}) later than event_date ({event.event_date})")

    _validate_task_common(event.associated_task, event.org_id)
    if event.associated_task.type != "双轨验证":
        raise ValueError(f"Dual run associated task must be '双轨验证', got '{event.associated_task.type}'")


def validate_transition_review(event: TransitionReviewEventFootprint) -> None:
    """Validate TransitionReviewEventFootprint strictly enforces forward-only lifecycle progression."""
    if event.from_status not in ORG_LIFECYCLE_STAGES:
        raise ValueError(f"Invalid from_status: '{event.from_status}'")
    if event.to_status not in ORG_LIFECYCLE_STAGES:
        raise ValueError(f"Invalid to_status: '{event.to_status}'")

    from_idx = ORG_LIFECYCLE_STAGES.index(event.from_status)
    to_idx = ORG_LIFECYCLE_STAGES.index(event.to_status)
    if to_idx != from_idx + 1:
        raise ValueError(
            f"Invalid transition progression: cannot move from '{event.from_status}' "
            f"to '{event.to_status}'. Must advance exactly one stage forward."
        )

    if not event.review_notes or not event.review_notes.strip():
        raise ValueError("Transition review_notes must not be empty")

    u = event.status_update
    if u.id != event.org_id or u.from_status != event.from_status or u.to_status != event.to_status:
        raise ValueError(
            f"Status update mismatch: update=({u.id}, {u.from_status}->{u.to_status}), "
            f"expected=({event.org_id}, {event.from_status}->{event.to_status})"
        )
    if u.update_date != event.event_date:
        raise ValueError(f"Update date ({u.update_date}) != event_date ({event.event_date})")

    s = event.snapshot
    if s.org_id != event.org_id or s.status != event.to_status or s.snapshot_date != event.event_date:
        raise ValueError(
            f"Snapshot mismatch: snapshot=({s.org_id}, {s.status}, {s.snapshot_date}), "
            f"expected=({event.org_id}, {event.to_status}, {event.event_date})"
        )

    if event.milestone_task is not None:
        _validate_task_common(event.milestone_task, event.org_id)


def validate_batch_rollout(event: BatchRolloutEventFootprint) -> None:
    """Validate BatchRolloutEventFootprint progression."""
    if event.from_status not in BATCH_LIFECYCLE_STAGES:
        raise ValueError(f"Invalid batch from_status: '{event.from_status}'")
    if event.to_status not in BATCH_LIFECYCLE_STAGES:
        raise ValueError(f"Invalid batch to_status: '{event.to_status}'")

    from_idx = BATCH_LIFECYCLE_STAGES.index(event.from_status)
    to_idx = BATCH_LIFECYCLE_STAGES.index(event.to_status)
    if to_idx != from_idx + 1:
        raise ValueError(
            f"Invalid batch progression: cannot move from '{event.from_status}' "
            f"to '{event.to_status}'. Must advance exactly one stage forward."
        )

    b = event.batch_update
    if b.id != event.batch_id or b.status != event.to_status:
        raise ValueError(
            f"Batch update mismatch: batch=({b.id}, {b.status}), expected=({event.batch_id}, {event.to_status})"
        )
    if b.start_date > b.end_date:
        raise ValueError(f"Batch start_date ({b.start_date}) later than end_date ({b.end_date})")
    if not event.reason or not event.reason.strip():
        raise ValueError("Batch transition reason must not be empty")


def validate_new_org_admission(event: NewOrgAdmissionFootprint) -> None:
    """Validate NewOrgAdmissionFootprint consistency and compliance with KI-035."""
    if event.batch_id != 8:
        raise ValueError(f"Gate violated: Batch 8 reserve pool admission requires batch_id=8, got {event.batch_id}")
    if event.status != "未启动":
        raise ValueError(f"Gate violated: New unit must be '未启动', got {event.status}")
    if not event.name or not event.name.strip():
        raise ValueError("Organization name must not be empty")
    if not event.region or not event.region.strip():
        raise ValueError("Organization region must not be empty")
    if event.start_date > event.end_date:
        raise ValueError(f"Time inversion: start_date ({event.start_date}) > end_date ({event.end_date})")

    # Validate users: 3~5 users, must have 财务总监/管理人员 and 项目经理
    if len(event.users) < 3:
        raise ValueError(f"User roster violated: minimum 3 users required, got {len(event.users)}")
    user_names = set()
    has_finance_director = False
    has_project_manager = False
    for u in event.users:
        if u.org_id != event.org_id:
            raise ValueError(f"User org_id mismatch: {u.org_id} != {event.org_id}")
        if not u.name or not u.name.strip():
            raise ValueError("User name must not be empty")
        if u.name in user_names:
            raise ValueError(f"Duplicate user name {u.name} within org {event.org_id}")
        user_names.add(u.name)
        if u.job == "财务总监" or u.role == "管理人员":
            has_finance_director = True
        if u.job == "项目经理" or u.role == "项目经理":
            has_project_manager = True
    if not has_finance_director:
        raise ValueError(f"User roster violated: missing 财务总监/管理人员 in org {event.org_id}")
    if not has_project_manager:
        raise ValueError(f"User roster violated: missing 项目经理 in org {event.org_id}")

    # Validate tasks: progress must be 0, status '未开始', actual_time None
    if len(event.tasks) < 20:
        raise ValueError(f"Construction tasks violated: standard suite requires >= 20 tasks, got {len(event.tasks)}")
    for t in event.tasks:
        if t.org_id != event.org_id:
            raise ValueError(f"Task org_id mismatch: {t.org_id} != {event.org_id}")
        if t.progress != 0:
            raise ValueError(f"Unstarted unit task must have progress 0, got {t.progress} on task {t.id}")
        if t.status != "未开始":
            raise ValueError(f"Unstarted unit task must have status '未开始', got '{t.status}' on task {t.id}")
        if t.actual_time is not None:
            raise ValueError(f"Unstarted unit task actual_time must be None, got {t.actual_time}")
        if t.owner not in user_names:
            raise ValueError(f"Task owner '{t.owner}' not found in organization user roster")

    # Validate data readiness: rates must be 0%, status '未收集'
    if event.readiness:
        r = event.readiness
        if r.org_id != event.org_id:
            raise ValueError(f"Readiness org_id mismatch: {r.org_id} != {event.org_id}")
        if r.batch_id != 8:
            raise ValueError(f"Readiness batch_id mismatch: {r.batch_id} != 8")
        if r.overall_status != "未收集":
            raise ValueError(f"Readiness overall_status must be '未收集', got '{r.overall_status}'")
        if r.static_completed != 0 or r.opening_completed != 0 or r.dynamic_completed != 0:
            raise ValueError("Readiness completed counts must all be 0 for new unstarted unit")

    # Validate rollout snapshot
    if event.snapshot:
        s = event.snapshot
        if s.org_id != event.org_id:
            raise ValueError(f"Snapshot org_id mismatch: {s.org_id} != {event.org_id}")
        if s.status != "未启动":
            raise ValueError(f"Snapshot status must be '未启动', got '{s.status}'")


def validate_construction_event(event: object) -> None:
    """Unified dispatcher to validate any of the construction event footprints."""
    if isinstance(event, NewOrgAdmissionFootprint):
        validate_new_org_admission(event)
    elif isinstance(event, PoolOnboardingEventFootprint):
        validate_pool_onboarding(event)
    elif isinstance(event, DataReadinessEventFootprint):
        validate_data_readiness(event)
    elif isinstance(event, TrainingCertificationEventFootprint):
        validate_training_certification(event)
    elif isinstance(event, InterfaceDebuggingEventFootprint):
        validate_interface_debugging(event)
    elif isinstance(event, DualRunCheckEventFootprint):
        validate_dual_run_check(event)
    elif isinstance(event, TransitionReviewEventFootprint):
        validate_transition_review(event)
    elif isinstance(event, BatchRolloutEventFootprint):
        validate_batch_rollout(event)
    else:
        raise TypeError(f"Unknown construction event footprint type: {type(event).__name__}")
