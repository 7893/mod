"""Construction event playbooks generating realistic footprints for the 7 lifecycle events.

Phase B: Generators for:
1. PoolOnboardingPlaybook (入池)
2. DataReadinessPlaybook (数据准备)
3. TrainingCertificationPlaybook (培训认证)
4. InterfaceDebuggingPlaybook (接口联调)
5. DualRunCheckPlaybook (双轨核对)
6. TransitionReviewPlaybook (跃迁评审)
7. BatchRolloutPlaybook (批次推进)

All playbooks strictly enforce causal gates, assign owners from unit's real sys_user
roster (100% compliant with KI-017), and execute deterministic footprint validation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import random
from typing import Any, Dict, Optional

from .construction_models import (
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
    validate_data_readiness,
    validate_dual_run_check,
    validate_interface_debugging,
    validate_pool_onboarding,
    validate_training_certification,
    validate_transition_review,
)
from .engine_context import ConstructionBaseline, IdAllocator

INTERFACE_NAMES = [
    "资金管理系统银企直联流水回传接口",
    "总账系统自动记账凭证回传接口",
    "电子发票服务平台查验与认证接口",
    "固定资产条码管理系统数据交互接口",
    "人力资源系统员工组织架构同步接口",
]

TRAINING_TYPES = [
    "业务操作与财务处理培训",
    "双轨运行与上线切换培训",
    "数据准备与系统管理培训",
    "项目管理与关键用户培训",
]

CHECK_TYPES = [
    "业务单据金额核对",
    "凭证借贷汇总核对",
    "月末科目余额比对",
]


class BaseConstructionPlaybook:
    """Base helper providing user selection and causal gate validation."""

    def __init__(self, baseline: ConstructionBaseline, seed: Optional[int] = None):
        self.baseline = baseline
        self.rng = random.Random(seed)

    def _get_org_user(self, org_id: int) -> str:
        """Pick a real employee from the organization's sys_user roster."""
        users = self.baseline.org_users.get(org_id, [])
        if not users:
            raise ValueError(f"Organization {org_id} has no users in baseline sys_user")
        return self.rng.choice(users)["name"]

    def _get_org(self, org_id: int) -> Dict[str, Any]:
        """Fetch organization info from baseline."""
        org = self.baseline.orgs.get(org_id)
        if not org:
            raise ValueError(f"Organization {org_id} not found in baseline")
        return org


class PoolOnboardingPlaybook(BaseConstructionPlaybook):
    """Playbook 1: Org unit enters construction preparation (未启动 -> 准备中)."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        id_allocator: Optional[IdAllocator] = None,
    ) -> PoolOnboardingEventFootprint:
        org = self._get_org(org_id)
        if org["status"] != "未启动":
            raise ValueError(f"Gate violated: org {org_id} status is '{org['status']}', expected '未启动'")

        owner = self._get_org_user(org_id)
        task_id = id_allocator.next_id("construction_task") if id_allocator else 100000 + org_id

        initial_tasks = [
            ConstructionTaskFootprint(
                id=task_id,
                org_id=org_id,
                name="生产与容灾服务器资源规划",
                type="基础环境",
                owner=owner,
                plan_time=event_date,
                actual_time=None,
                status="进行中",
                progress=25,
                update_time=event_date,
            ),
            ConstructionTaskFootprint(
                id=task_id + 1,
                org_id=org_id,
                name="组织架构及法人主体主数据同步",
                type="组织权限",
                owner=owner,
                plan_time=event_date,
                actual_time=None,
                status="进行中",
                progress=30,
                update_time=event_date,
            ),
        ]

        event = PoolOnboardingEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
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
            initial_tasks=initial_tasks,
        )
        validate_pool_onboarding(event)
        return event


class DataReadinessPlaybook(BaseConstructionPlaybook):
    """Playbook 2: Data readiness progression & sync."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        static_completed: int = 60,
        static_total: int = 60,
        opening_completed: int = 80,
        opening_total: int = 80,
        dynamic_total: int = 100,
        dynamic_fail: int = 0,
        dynamic_pending: int = 0,
        opening_diff_amount: Decimal = Decimal("0.00"),
        task_id: Optional[int] = None,
    ) -> DataReadinessEventFootprint:
        org = self._get_org(org_id)
        if org["status"] not in ("准备中", "已具备双轨条件"):
            raise ValueError(
                f"Gate violated: org {org_id} status is '{org['status']}', expected 准备中/已具备双轨条件"
            )

        dynamic_success = dynamic_total - dynamic_fail - dynamic_pending
        if dynamic_success < 0:
            raise ValueError("Dynamic success count cannot be negative")

        static_rate = f"{(static_completed / static_total * 100):.1f}%" if static_total > 0 else "100.0%"
        opening_rate = f"{(opening_completed / opening_total * 100):.1f}%" if opening_total > 0 else "100.0%"
        dynamic_rate = f"{(dynamic_success / dynamic_total * 100):.1f}%" if dynamic_total > 0 else "100.0%"

        overall_status = (
            "已导入"
            if static_completed == static_total
            and opening_completed == opening_total
            and dynamic_fail == 0
            and dynamic_pending == 0
            else "校验通过"
        )

        readiness = DataReadinessRecordFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            static_total=static_total,
            static_completed=static_completed,
            static_rate=static_rate,
            opening_total=opening_total,
            opening_completed=opening_completed,
            opening_rate=opening_rate,
            opening_diff_amount=opening_diff_amount,
            dynamic_total=dynamic_total,
            dynamic_completed=dynamic_success,
            dynamic_sync_success=dynamic_success,
            dynamic_sync_fail=dynamic_fail,
            dynamic_sync_pending=dynamic_pending,
            dynamic_rate=dynamic_rate,
            overall_status=overall_status,
            last_sync_time=f"{event_date} 15:30:00",
        )

        owner = self._get_org_user(org_id)
        is_done = overall_status == "已导入"
        task = ConstructionTaskFootprint(
            id=task_id or 200000 + org_id,
            org_id=org_id,
            name="期初未达账项与银行对账单平衡调节",
            type="期初数据",
            owner=owner,
            plan_time=event_date,
            actual_time=event_date if is_done else None,
            status="已完成" if is_done else "进行中",
            progress=100 if is_done else 80,
            update_time=event_date,
        )

        event = DataReadinessEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            event_date=event_date,
            readiness=readiness,
            associated_task=task,
        )
        validate_data_readiness(event)
        return event


class TrainingCertificationPlaybook(BaseConstructionPlaybook):
    """Playbook 3: User training session and certification record."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        id_allocator: Optional[IdAllocator] = None,
        mode: str = "现场实操",
        training_type: Optional[str] = None,
        expected: int = 16,
        absent: int = 0,
        unpassed: int = 0,
    ) -> TrainingCertificationEventFootprint:
        org = self._get_org(org_id)
        if org["status"] not in ("准备中", "已具备双轨条件", "双轨运行中"):
            raise ValueError(
                f"Gate violated: org {org_id} status '{org['status']}' not eligible for training"
            )

        t_type = training_type or self.rng.choice(TRAINING_TYPES)
        training_id = id_allocator.next_id("training") if id_allocator else 300000 + org_id
        actual = expected - absent
        passed = actual - unpassed
        makeup = unpassed  # passed on makeup
        cert_count = passed + makeup

        record = TrainingRecordFootprint(
            id=training_id,
            org_id=org_id,
            batch_id=org["batch_id"],
            type=t_type,
            date=event_date,
            mode=mode,
            expected=expected,
            actual=actual,
            absent=absent,
            passed=passed,
            makeup=makeup,
            cert_count=cert_count,
        )

        owner = self._get_org_user(org_id)
        task_id = id_allocator.next_id("construction_task") if id_allocator else 350000 + org_id
        task = ConstructionTaskFootprint(
            id=task_id,
            org_id=org_id,
            name="骨干业务人员与关键用户专题深化培训",
            type="用户培训",
            owner=owner,
            plan_time=event_date,
            actual_time=event_date,
            status="已完成",
            progress=100,
            update_time=event_date,
        )

        event = TrainingCertificationEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            event_date=event_date,
            training=record,
            associated_task=task,
        )
        validate_training_certification(event)
        return event


class InterfaceDebuggingPlaybook(BaseConstructionPlaybook):
    """Playbook 4: Interface testing, debugging, and verification."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        id_allocator: Optional[IdAllocator] = None,
        interface_name: Optional[str] = None,
        completed: bool = True,
    ) -> InterfaceDebuggingEventFootprint:
        org = self._get_org(org_id)
        if org["status"] not in ("准备中", "已具备双轨条件"):
            raise ValueError(
                f"Gate violated: org {org_id} status '{org['status']}' not eligible for interface debug"
            )

        name = interface_name or self.rng.choice(INTERFACE_NAMES)
        total_cases = 25
        passed_cases = total_cases if completed else total_cases - 3
        owner = self._get_org_user(org_id)
        task_id = id_allocator.next_id("construction_task") if id_allocator else 400000 + org_id

        task = ConstructionTaskFootprint(
            id=task_id,
            org_id=org_id,
            name="资金管理系统银企直联流水回传联调",
            type="接口联调",
            owner=owner,
            plan_time=event_date,
            actual_time=event_date if completed else None,
            status="已完成" if completed else "进行中",
            progress=100 if completed else 88,
            update_time=event_date,
        )

        event = InterfaceDebuggingEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            event_date=event_date,
            task=task,
            interface_name=name,
            test_case_count=total_cases,
            test_passed_count=passed_cases,
        )
        validate_interface_debugging(event)
        return event


class DualRunCheckPlaybook(BaseConstructionPlaybook):
    """Playbook 5: Parallel dual-run comparison between V1 and V2."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        id_allocator: Optional[IdAllocator] = None,
        check_type: Optional[str] = None,
        force_diff: bool = False,
    ) -> DualRunCheckEventFootprint:
        org = self._get_org(org_id)
        if org["status"] != "双轨运行中":
            raise ValueError(
                f"Gate violated: org {org_id} status is '{org['status']}', expected '双轨运行中'"
            )

        c_type = check_type or self.rng.choice(CHECK_TYPES)
        dual_id = id_allocator.next_id("dual_run_result") if id_allocator else 500000 + org_id
        base_amt = Decimal(f"{self.rng.randint(500000, 4500000)}.{self.rng.randint(10, 99)}")

        if force_diff:
            diff_val = Decimal(f"{self.rng.randint(50, 800)}.{self.rng.randint(10, 99)}")
            v1_amt = base_amt
            v2_amt = base_amt + diff_val
            diff_amt = diff_val
            result_str = "不一致"
        else:
            v1_amt = base_amt
            v2_amt = base_amt
            diff_amt = Decimal("0.00")
            result_str = "一致"

        record = DualRunResultRecordFootprint(
            id=dual_id,
            org_id=org_id,
            check_type=c_type,
            v1_amount=v1_amt,
            v2_amount=v2_amt,
            diff_amount=diff_amt,
            result=result_str,
            check_date=event_date,
        )

        owner = self._get_org_user(org_id)
        task_id = id_allocator.next_id("construction_task") if id_allocator else 550000 + org_id
        task = ConstructionTaskFootprint(
            id=task_id,
            org_id=org_id,
            name="新旧系统首周业务单据与凭证平行核对",
            type="双轨验证",
            owner=owner,
            plan_time=event_date,
            actual_time=event_date if not force_diff else None,
            status="已完成" if not force_diff else "进行中",
            progress=100 if not force_diff else 85,
            update_time=event_date,
        )

        event = DualRunCheckEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            event_date=event_date,
            dual_run=record,
            associated_task=task,
        )
        validate_dual_run_check(event)
        return event


class TransitionReviewPlaybook(BaseConstructionPlaybook):
    """Playbook 6: Formal milestone review & lifecycle phase transition."""

    def generate(
        self,
        org_id: int,
        event_date: date,
        from_status: str,
        to_status: str,
        review_notes: Optional[str] = None,
        milestone_task: Optional[ConstructionTaskFootprint] = None,
    ) -> TransitionReviewEventFootprint:
        org = self._get_org(org_id)
        if org["status"] != from_status:
            raise ValueError(
                f"Gate violated: org {org_id} current status is '{org['status']}', expected '{from_status}'"
            )

        notes = review_notes or (
            f"经项目推进办公室组织专家进行现场综合验收评审，该单位各项前置指标已稳定达标，"
            f"业务验证无阻断性缺陷，准予由[{from_status}]阶段跃迁至[{to_status}]阶段。"
        )

        event = TransitionReviewEventFootprint(
            org_id=org_id,
            batch_id=org["batch_id"],
            event_date=event_date,
            from_status=from_status,
            to_status=to_status,
            review_notes=notes,
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
            milestone_task=milestone_task,
        )
        validate_transition_review(event)
        return event


class BatchRolloutPlaybook(BaseConstructionPlaybook):
    """Playbook 7: Rollout batch overall milestone advancement."""

    def generate(
        self,
        batch_id: int,
        event_date: date,
        from_status: str,
        to_status: str,
        reason: Optional[str] = None,
    ) -> BatchRolloutEventFootprint:
        batch = self.baseline.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found in baseline")
        if batch["status"] != from_status:
            raise ValueError(
                f"Gate violated: batch {batch_id} status is '{batch['status']}', expected '{from_status}'"
            )

        expl = reason or (
            f"第{batch_id}批次所属单位平均建设完成度已达既定目标，"
            f"批次整体状态由[{from_status}]推进至[{to_status}]。"
        )

        batch_update = RolloutBatchUpdateFootprint(
            id=batch_id,
            name=batch["name"],
            start_date=batch["start_date"],
            end_date=batch["end_date"],
            status=to_status,
        )

        event = BatchRolloutEventFootprint(
            batch_id=batch_id,
            event_date=event_date,
            from_status=from_status,
            to_status=to_status,
            batch_update=batch_update,
            reason=expl,
        )
        validate_batch_rollout(event)
        return event
