"""Evolution coordinator coupling the fast movie (business/construction flow) with slow movie (lifecycle).

Phase D:
1. 快电影喂慢电影: Daily events push units' metrics toward graduation ("终将达标"),
   while natural friction produces difficult units (困难户, ~3%-5%) that lag behind.
2. 矛盾咬合: Both the Lifecycle Advancer (spear) and Decision Support/Risk Overview (shield)
   inspect the EXACT same underlying metrics and facts. Difficult units held back from
   graduation are identically identified by the risk view as at-risk units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import hashlib
import random
from typing import Dict, List, Optional, Set, Tuple

from .construction_playbooks import (
    DataReadinessPlaybook,
    DualRunCheckPlaybook,
    InterfaceDebuggingPlaybook,
    PoolOnboardingPlaybook,
    TrainingCertificationPlaybook,
)
from .engine_context import ConstructionBaseline, IdAllocator
from .lifecycle_advancer import LifecycleAdvancer, LifecycleThresholds, OrgMetricsSnapshot


@dataclass
class ContradictionMeshingReport:
    """Audit report verifying consistency between the lifecycle state machine and risk view."""

    evaluation_date: date
    total_evaluated_units: int
    advanced_units_count: int
    held_back_units_count: int
    risk_flagged_units_count: int
    # Units held back that are also flagged by risk view
    meshed_units: Set[int]
    # Any discrepancies between the two views
    unmeshed_advancer_only: Set[int] = field(default_factory=set)
    unmeshed_risk_only: Set[int] = field(default_factory=set)

    @property
    def is_perfectly_meshed(self) -> bool:
        """True if advancer blockers and risk flags completely align on the same facts."""
        return len(self.unmeshed_advancer_only) == 0 and len(self.unmeshed_risk_only) == 0


class EvolutionCoordinator:
    """Coordinates daily simulation activities, metric evolution, and contradiction meshing."""

    def __init__(
        self,
        baseline: ConstructionBaseline,
        thresholds: Optional[LifecycleThresholds] = None,
        seed: Optional[int] = None,
    ):
        self.baseline = baseline
        self.thresholds = thresholds or LifecycleThresholds()
        self.rng = random.Random(seed)
        self.allocator = IdAllocator(baseline.next_ids)

        # Playbooks
        self.p_onboard = PoolOnboardingPlaybook(baseline, seed=seed)
        self.p_readiness = DataReadinessPlaybook(baseline, seed=seed)
        self.p_training = TrainingCertificationPlaybook(baseline, seed=seed)
        self.p_debug = InterfaceDebuggingPlaybook(baseline, seed=seed)
        self.p_dual = DualRunCheckPlaybook(baseline, seed=seed)

        # Advancer
        self.advancer = LifecycleAdvancer(baseline, thresholds=self.thresholds, seed=seed)

        # Unit internal metric states: org_id -> OrgMetricsSnapshot
        self.unit_metrics: Dict[int, OrgMetricsSnapshot] = {}
        self._init_unit_metrics()

    def _init_unit_metrics(self) -> None:
        """Initialize metric snapshot for all baseline orgs."""
        for oid, info in self.baseline.orgs.items():
            st = info["status"]
            s_date = info["start_date"]
            self.unit_metrics[oid] = OrgMetricsSnapshot(
                org_id=oid,
                current_status=st,
                batch_id=info["batch_id"],
                stage_entered_date=s_date,
                static_rate=100.0 if st in ("已具备双轨条件", "双轨运行中", "已上线", "稳定运行") else 60.0,
                opening_rate=100.0 if st in ("已具备双轨条件", "双轨运行中", "已上线", "稳定运行") else 50.0,
                opening_diff_amount=Decimal("0.00"),
                dynamic_rate=95.0 if st in ("已具备双轨条件", "双轨运行中", "已上线", "稳定运行") else 70.0,
                tasks_completed={
                    "基础环境": st != "未启动",
                    "基础数据": st not in ("未启动", "准备中"),
                    "组织权限": st not in ("未启动", "准备中"),
                    "期初数据": st not in ("未启动", "准备中"),
                },
                training_completed=st not in ("未启动", "准备中"),
                training_pass_rate=95.0 if st not in ("未启动", "准备中") else 0.0,
                interfaces_completed=st in ("双轨运行中", "已上线", "稳定运行"),
                dual_run_checks_total=10 if st in ("已上线", "稳定运行") else 0,
                dual_run_consistency_rate=99.5 if st in ("已上线", "稳定运行") else 0.0,
                dual_run_recent_matches=5 if st in ("已上线", "稳定运行") else 0,
                has_blocking_risk=False,
            )

    def is_difficult_unit(self, org_id: int) -> Tuple[bool, Optional[str]]:
        """
        Deterministically determine whether an organization experiences business friction.

        Natural distribution: ~4% of units encounter real-world friction
        (e.g., complex legacy system discrepancies, multi-entity interface delays).
        Derived deterministically from org_id hash.
        """
        digest = hashlib.md5(f"org_friction_{org_id}".encode("utf-8")).hexdigest()  # noqa: S324
        val = int(digest[:6], 16) % 100
        if val < 4:
            friction_types = [
                "历史账套期初科目余额存在核销差异",
                "跨行银企直联接口专线网络间歇性超时",
                "老系统月末高频单据核对存在长尾差异",
            ]
            reason = friction_types[val % len(friction_types)]
            return True, reason
        return False, None

    def evolve_unit_step(
        self,
        org_id: int,
        current_date: date,
    ) -> List[object]:
        """Evolve an individual unit's metrics and generate daily fast-movie events."""
        metrics = self.unit_metrics.get(org_id)
        if not metrics:
            return []

        st = self.advancer.org_status.get(org_id, metrics.current_status)
        metrics.current_status = st
        is_difficult, diff_reason = self.is_difficult_unit(org_id)
        generated_events: List[object] = []

        if st == "未启动":
            batch = self.baseline.batches.get(metrics.batch_id)
            if batch and batch["start_date"] <= current_date:
                ev = self.p_onboard.generate(org_id, current_date, self.allocator)
                generated_events.append(ev)
                self.advancer.org_status[org_id] = "准备中"
                metrics.current_status = "准备中"
                metrics.stage_entered_date = current_date

        elif st == "准备中":
            if is_difficult and diff_reason and "期初科目余额" in diff_reason:
                # Difficult unit: opening diff variance persists
                metrics.static_rate = 95.0
                metrics.opening_rate = 90.0
                metrics.opening_diff_amount = Decimal("3540.80")
                metrics.dynamic_rate = 85.0
                metrics.has_blocking_risk = True
            else:
                # Normal unit: steadily improves towards 100%
                metrics.static_rate = min(100.0, metrics.static_rate + 15.0)
                metrics.opening_rate = min(100.0, metrics.opening_rate + 20.0)
                metrics.dynamic_rate = min(100.0, metrics.dynamic_rate + 10.0)
                metrics.opening_diff_amount = Decimal("0.00")
                metrics.tasks_completed["基础环境"] = True
                metrics.tasks_completed["基础数据"] = metrics.static_rate >= 100.0
                metrics.tasks_completed["期初数据"] = metrics.opening_rate >= 100.0
                metrics.has_blocking_risk = False

            ev = self.p_readiness.generate(
                org_id=org_id,
                event_date=current_date,
                static_completed=int(metrics.static_rate * 60 / 100),
                static_total=60,
                opening_completed=int(metrics.opening_rate * 80 / 100),
                opening_total=80,
                dynamic_total=100,
                dynamic_fail=5 if is_difficult else 0,
                opening_diff_amount=metrics.opening_diff_amount,
                task_id=self.allocator.next_id("construction_task"),
            )
            generated_events.append(ev)

        elif st == "已具备双轨条件":
            if is_difficult and diff_reason and "接口" in diff_reason:
                # Interface friction
                metrics.interfaces_completed = False
                metrics.training_completed = True
                metrics.training_pass_rate = 88.0  # below 90% threshold
                metrics.has_blocking_risk = True
                ev = self.p_debug.generate(org_id, current_date, self.allocator, completed=False)
            else:
                metrics.interfaces_completed = True
                metrics.training_completed = True
                metrics.training_pass_rate = 96.0
                metrics.tasks_completed["组织权限"] = True
                metrics.has_blocking_risk = False
                ev = self.p_debug.generate(org_id, current_date, self.allocator, completed=True)
            generated_events.append(ev)

        elif st == "双轨运行中":
            if is_difficult:
                # Discrepancy friction
                metrics.dual_run_checks_total += 1
                metrics.dual_run_consistency_rate = 94.2  # below 98.0% threshold
                metrics.dual_run_recent_matches = 0
                metrics.has_blocking_risk = True
                ev = self.p_dual.generate(org_id, current_date, self.allocator, force_diff=True)
            else:
                metrics.dual_run_checks_total += 1
                metrics.dual_run_consistency_rate = 99.2
                metrics.dual_run_recent_matches += 1
                metrics.has_blocking_risk = False
                ev = self.p_dual.generate(org_id, current_date, self.allocator, force_diff=False)
            generated_events.append(ev)

        return generated_events

    def inspect_contradiction_meshing(
        self,
        candidate_org_ids: List[int],
        current_date: date,
    ) -> ContradictionMeshingReport:
        """
        Verify that the Lifecycle Advancer (spear) and Decision Support Risk View (shield)
        perfectly mesh and identify the EXACT SAME units as delayed/at-risk.
        """
        advancer_held_back: Set[int] = set()
        risk_view_flagged: Set[int] = set()
        advanced_count = 0

        for oid in candidate_org_ids:
            metrics = self.unit_metrics.get(oid)
            if not metrics:
                continue

            # 1. Advancer perspective (spear)
            is_qualified, next_stage, _reasons = self.advancer.evaluate_qualification(metrics, current_date)
            if next_stage:
                if not is_qualified:
                    advancer_held_back.add(oid)
                else:
                    advanced_count += 1

            # 2. Risk view perspective (shield)
            # Evaluates the exact same metrics that HeatWave AutoML / Risk Dashboard inspects:
            # - Has blocking risk flag
            # - Data readiness opening difference > 0 or dynamic failure
            # - Dual run consistency rate < 98% (when in dual-run)
            # - Incomplete interfaces or training < 90% (when in dual-ready)
            is_at_risk = False
            if metrics.has_blocking_risk:
                is_at_risk = True
            elif metrics.current_status == "未启动":
                batch = self.baseline.batches.get(metrics.batch_id)
                if not batch or batch["start_date"] > current_date:
                    is_at_risk = True
            elif metrics.current_status == "准备中":
                if (
                    metrics.opening_diff_amount > Decimal("0.00")
                    or metrics.static_rate < self.thresholds.readiness_static_rate_min
                    or metrics.opening_rate < self.thresholds.readiness_opening_rate_min
                    or metrics.dynamic_rate < self.thresholds.readiness_dynamic_rate_min
                    or not all(metrics.tasks_completed.get(k, False) for k in ("基础环境", "基础数据", "期初数据"))
                ):
                    is_at_risk = True
            elif metrics.current_status == "已具备双轨条件":
                if (
                    not metrics.interfaces_completed
                    or metrics.training_pass_rate < self.thresholds.training_pass_rate_min
                    or not metrics.tasks_completed.get("组织权限", False)
                ):
                    is_at_risk = True
            elif metrics.current_status == "双轨运行中":
                duration_days = (current_date - metrics.stage_entered_date).days
                if (
                    metrics.dual_run_consistency_rate < self.thresholds.dual_run_consistency_rate_min
                    or metrics.dual_run_recent_matches < self.thresholds.dual_run_consecutive_matches_min
                    or metrics.dual_run_checks_total < self.thresholds.dual_run_min_checks
                    or duration_days < self.thresholds.dual_run_days_min
                ):
                    is_at_risk = True
            elif metrics.current_status == "已上线":
                online_days = (current_date - metrics.stage_entered_date).days
                if online_days < self.thresholds.online_days_min:
                    is_at_risk = True

            if is_at_risk and next_stage:
                risk_view_flagged.add(oid)

        meshed = advancer_held_back.intersection(risk_view_flagged)
        advancer_only = advancer_held_back - risk_view_flagged
        risk_only = risk_view_flagged - advancer_held_back

        return ContradictionMeshingReport(
            evaluation_date=current_date,
            total_evaluated_units=len(candidate_org_ids),
            advanced_units_count=advanced_count,
            held_back_units_count=len(advancer_held_back),
            risk_flagged_units_count=len(risk_view_flagged),
            meshed_units=meshed,
            unmeshed_advancer_only=advancer_only,
            unmeshed_risk_only=risk_only,
        )
