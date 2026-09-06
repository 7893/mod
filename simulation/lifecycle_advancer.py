"""B-Mode lifecycle state machine advancer driven by realistic metrics.

Implements the 6-stage lifecycle advancement engine:
未启动 -> 准备中 -> 已具备双轨条件 -> 双轨运行中 -> 已上线 -> 稳定运行

Enforces the Three Iron Rules:
1. 只进不退 (Forward-only, strictly monotonically increasing stages, zero regression).
2. 持续达标 N 天才跃迁 (Must sustain qualification metrics for N consecutive days before transition).
3. 跃迁有过程有留痕 (Formal review event, detailed governance notes, rollout_status_snapshot trail).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import random
from typing import Dict, List, Optional, Tuple

from .construction_models import (
    ORG_LIFECYCLE_STAGES,
    ConstructionTaskFootprint,
    TransitionReviewEventFootprint,
    validate_transition_review,
)
from .construction_playbooks import TransitionReviewPlaybook
from .engine_context import ConstructionBaseline


@dataclass
class LifecycleThresholds:
    """Configurable and documented threshold parameters for stage transitions."""

    # 准备中 -> 已具备双轨条件
    readiness_static_rate_min: float = 100.0
    readiness_opening_rate_min: float = 100.0
    readiness_opening_diff_max: Decimal = Decimal("0.00")
    readiness_dynamic_rate_min: float = 90.0
    prep_consecutive_days_min: int = 3

    # 已具备双轨条件 -> 双轨运行中
    training_pass_rate_min: float = 90.0
    dual_ready_consecutive_days_min: int = 3

    # 双轨运行中 -> 已上线
    dual_run_days_min: int = 14
    dual_run_consistency_rate_min: float = 98.0
    dual_run_min_checks: int = 5
    dual_run_consecutive_matches_min: int = 3
    dual_run_consecutive_days_min: int = 7

    # 已上线 -> 稳定运行
    online_days_min: int = 30
    stable_consecutive_days_min: int = 14


@dataclass
class OrgMetricsSnapshot:
    """Comprehensive snapshot of an organization's current metrics for evaluation."""

    org_id: int
    current_status: str
    batch_id: int
    stage_entered_date: date
    static_rate: float = 0.0
    opening_rate: float = 0.0
    opening_diff_amount: Decimal = Decimal("0.00")
    dynamic_rate: float = 0.0
    tasks_completed: Dict[str, bool] = field(default_factory=dict)
    training_completed: bool = False
    training_pass_rate: float = 0.0
    interfaces_completed: bool = False
    dual_run_checks_total: int = 0
    dual_run_consistency_rate: float = 0.0
    dual_run_recent_matches: int = 0
    has_blocking_risk: bool = False


class LifecycleAdvancer:
    """B-Mode 6-stage lifecycle state machine advancer."""

    def __init__(
        self,
        baseline: ConstructionBaseline,
        thresholds: Optional[LifecycleThresholds] = None,
        seed: Optional[int] = None,
    ):
        self.baseline = baseline
        self.thresholds = thresholds or LifecycleThresholds()
        self.rng = random.Random(seed)
        self.review_playbook = TransitionReviewPlaybook(baseline, seed=seed)

        # State tracking: org_id -> consecutive days qualified
        self.consecutive_qualified_days: Dict[int, int] = {}
        # Track current status of all units
        self.org_status: Dict[int, str] = {oid: info["status"] for oid, info in baseline.orgs.items()}
        # Track when unit entered current stage
        self.stage_entered_dates: Dict[int, date] = {
            oid: info["start_date"] for oid, info in baseline.orgs.items()
        }
        self.transition_log: List[TransitionReviewEventFootprint] = []

    def get_next_stage(self, current_status: str) -> Optional[str]:
        """Determine the next stage in the strictly ordered lifecycle chain."""
        if current_status not in ORG_LIFECYCLE_STAGES:
            raise ValueError(f"Unknown org lifecycle stage: '{current_status}'")
        idx = ORG_LIFECYCLE_STAGES.index(current_status)
        if idx + 1 < len(ORG_LIFECYCLE_STAGES):
            return ORG_LIFECYCLE_STAGES[idx + 1]
        return None

    def evaluate_qualification(
        self,
        metrics: OrgMetricsSnapshot,
        current_date: date,
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Evaluate if an organization qualifies for the immediate next stage.

        Returns (is_qualified, next_stage, list_of_reasons_or_gaps).
        """
        current_status = metrics.current_status
        next_stage = self.get_next_stage(current_status)
        if not next_stage:
            return False, None, ["已达到终态[稳定运行]，无需进一步跃迁"]

        reasons: List[str] = []
        is_qualified = True

        if current_status == "未启动":
            batch = self.baseline.batches.get(metrics.batch_id)
            if batch and batch["start_date"] <= current_date:
                reasons.append(f"所属批次[{batch['name']}]已启动入池")
            else:
                is_qualified = False
                reasons.append("所属批次尚未到达启动日期")

        elif current_status == "准备中":
            t = self.thresholds
            if metrics.static_rate < t.readiness_static_rate_min:
                is_qualified = False
                reasons.append(
                    f"静态数据完成率未达标: {metrics.static_rate}% < {t.readiness_static_rate_min}%"
                )
            if metrics.opening_rate < t.readiness_opening_rate_min:
                is_qualified = False
                reasons.append(
                    f"期初数据完成率未达标: {metrics.opening_rate}% < {t.readiness_opening_rate_min}%"
                )
            if metrics.opening_diff_amount > t.readiness_opening_diff_max:
                is_qualified = False
                reasons.append(f"期初差异金额不为零: {metrics.opening_diff_amount}")
            if metrics.dynamic_rate < t.readiness_dynamic_rate_min:
                is_qualified = False
                reasons.append(f"动态同步率未达标: {metrics.dynamic_rate}% < {t.readiness_dynamic_rate_min}%")
            for req_task in ("基础环境", "基础数据", "期初数据"):
                if not metrics.tasks_completed.get(req_task, False):
                    is_qualified = False
                    reasons.append(f"前置基础任务[{req_task}]未完成")
            if is_qualified:
                reasons.append("数据准备度全面达标，基础环境与数据任务全部完成")

        elif current_status == "已具备双轨条件":
            t = self.thresholds
            if not metrics.interfaces_completed:
                is_qualified = False
                reasons.append("核心外部业务接口联调尚未全部通过")
            if not metrics.training_completed or metrics.training_pass_rate < t.training_pass_rate_min:
                is_qualified = False
                reasons.append(
                    f"全员培训考核未达标: {metrics.training_pass_rate}% < {t.training_pass_rate_min}%"
                )
            if not metrics.tasks_completed.get("组织权限", False):
                is_qualified = False
                reasons.append("组织权限矩阵配置尚未完成")
            if is_qualified:
                reasons.append("接口联调全线跑通，培训考核达标，具备进入双轨运行资格")

        elif current_status == "双轨运行中":
            t = self.thresholds
            duration_days = (current_date - metrics.stage_entered_date).days
            if duration_days < t.dual_run_days_min:
                is_qualified = False
                reasons.append(f"双轨运行天数不足: {duration_days}天 < {t.dual_run_days_min}天")
            if metrics.dual_run_checks_total < t.dual_run_min_checks:
                is_qualified = False
                reasons.append(f"双轨核对笔数不足: {metrics.dual_run_checks_total} < {t.dual_run_min_checks}")
            if metrics.dual_run_consistency_rate < t.dual_run_consistency_rate_min:
                is_qualified = False
                reasons.append(
                    f"双轨一致率未达标: {metrics.dual_run_consistency_rate}% < {t.dual_run_consistency_rate_min}%"
                )
            if metrics.dual_run_recent_matches < t.dual_run_consecutive_matches_min:
                is_qualified = False
                reasons.append(
                    f"最近连续核对一致次数不足: {metrics.dual_run_recent_matches} < {t.dual_run_consecutive_matches_min}"
                )
            if metrics.has_blocking_risk:
                is_qualified = False
                reasons.append("存在未闭环的阻断性业务差异或高危风险")
            if is_qualified:
                reasons.append("双轨持续天数充足，核对一致率达标，无阻断缺陷，具备上线条件")

        elif current_status == "已上线":
            t = self.thresholds
            online_days = (current_date - metrics.stage_entered_date).days
            if online_days < t.online_days_min:
                is_qualified = False
                reasons.append(f"正式上线运行天数不足: {online_days}天 < {t.online_days_min}天")
            if metrics.has_blocking_risk:
                is_qualified = False
                reasons.append("上线后运行存在重大风险待处置")
            if is_qualified:
                reasons.append("系统平稳运行满月，月结核对平衡，无重大缺陷，准予转入稳定运行")

        return is_qualified, next_stage, reasons

    def get_required_consecutive_days(self, target_stage: str) -> int:
        """Return the required consecutive qualified days threshold for target stage."""
        t = self.thresholds
        mapping = {
            "准备中": 1,
            "已具备双轨条件": t.prep_consecutive_days_min,
            "双轨运行中": t.dual_ready_consecutive_days_min,
            "已上线": t.dual_run_consecutive_days_min,
            "稳定运行": t.stable_consecutive_days_min,
        }
        return mapping.get(target_stage, 3)

    def advance_unit_if_eligible(
        self,
        metrics: OrgMetricsSnapshot,
        current_date: date,
        milestone_task: Optional[ConstructionTaskFootprint] = None,
    ) -> Optional[TransitionReviewEventFootprint]:
        """
        Evaluate and advance an organization if all three iron rules are satisfied.

        1. Forward-only: target must be next stage.
        2. Sustained qualification: consecutive days >= required N.
        3. Transition with review footprint and snapshot trail.
        """
        org_id = metrics.org_id
        current_status = self.org_status.get(org_id, metrics.current_status)

        # Synchronize metrics current status with state machine
        if current_status != metrics.current_status:
            metrics.current_status = current_status

        is_qualified, next_stage, reasons = self.evaluate_qualification(metrics, current_date)
        if not next_stage:
            return None

        required_days = self.get_required_consecutive_days(next_stage)

        if is_qualified:
            current_consecutive = self.consecutive_qualified_days.get(org_id, 0) + 1
            self.consecutive_qualified_days[org_id] = current_consecutive
        else:
            # Rule 2: Any metric drop immediately resets consecutive days (prevents fluttering)
            self.consecutive_qualified_days[org_id] = 0
            return None

        # Check if sustained criteria met
        if self.consecutive_qualified_days[org_id] < required_days:
            return None

        # Rule 1 & 3: Execute formal forward transition review
        review_notes = (
            f"【阶段跃迁评审决议】经联合工作组综合评估，单位[{metrics.org_id}]各项指标持续达标"
            f"已达{self.consecutive_qualified_days[org_id]}天（要求≥{required_days}天）。"
            f"评审要点：{'; '.join(reasons)}。准予自[{current_status}]进入[{next_stage}]阶段。"
        )

        event = self.review_playbook.generate(
            org_id=org_id,
            event_date=current_date,
            from_status=current_status,
            to_status=next_stage,
            review_notes=review_notes,
            milestone_task=milestone_task,
        )
        validate_transition_review(event)

        # Update internal tracking
        self.org_status[org_id] = next_stage
        self.stage_entered_dates[org_id] = current_date
        self.consecutive_qualified_days[org_id] = 0  # Reset for subsequent phase
        self.transition_log.append(event)

        return event
