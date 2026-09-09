"""
simulation/pool_onboarding.py
=============================
Batch 8 Dynamic Reserve Pool Admission Playbook & Execution Service (KI-035).

Implements realistic, low-frequency SOE organization admission into the Batch 8
dynamic reserve pool (未启动蓄水池).

Atomic chained generation:
  - org_unit (1 row: batch_id=8, status='未启动', progress=0.0)
  - sys_user (3~5 rows: 财务总监, 项目经理, 经办人)
  - construction_task (~30 rows: standard lifecycle tasks, all progress=0, status='未开始')
  - data_readiness (1 row: batch_id=8, rates 0.0%, status='未收集')
  - rollout_status_snapshot (1 row: status='未启动')
  - daily_stats (synchronous cascade increment: org_count + 1, user_count + N)

Strictly zero business data: no documents, vouchers, integrations, or dual-run records.
Full transactional atomicity and audit logging.
"""

from __future__ import annotations

from datetime import date
import logging
from typing import Any, List, Optional, Set, Tuple

from .construction_models import (
    ConstructionTaskFootprint,
    DataReadinessRecordFootprint,
    NewOrgAdmissionFootprint,
    RolloutStatusSnapshotFootprint,
    SysUserFootprint,
    validate_new_org_admission,
)
from .construction_playbooks import BaseConstructionPlaybook
from .construction_writer import ConstructionWriteResult, ConstructionWriter
from .engine_context import ConstructionBaseline, IdAllocator
from .org_generator import OrgNameGenerator

logger = logging.getLogger(__name__)


class ReservePoolAdmissionPlaybook(BaseConstructionPlaybook):
    """
    Playbook for admitting a brand new SOE unit into the Batch 8 dynamic reserve pool.
    """

    def __init__(
        self,
        baseline: ConstructionBaseline,
        id_allocator: Optional[IdAllocator] = None,
        existing_names: Optional[Set[str]] = None,
        seed: Optional[int] = None,
    ):
        super().__init__(baseline, seed=seed)
        all_names = set(existing_names) if existing_names else {org["name"] for org in baseline.orgs.values()}
        self.name_gen = OrgNameGenerator(existing_names=all_names, seed=seed)
        self.allocator = id_allocator

    def generate(
        self,
        region: Optional[str] = None,
        event_date: Optional[date] = None,
        user_count: Optional[int] = None,
        id_allocator: Optional[IdAllocator] = None,
    ) -> NewOrgAdmissionFootprint:
        """
        Generate complete chained footprint for a new unit entering Batch 8 reserve pool.
        """
        alloc = id_allocator or self.allocator
        today = event_date or date.today()
        profile = self.name_gen.generate_org_profile(
            region=region,
            event_date=today,
            user_count=user_count,
        )

        org_id = alloc.next_id("org_unit") if alloc else (max(self.baseline.orgs.keys(), default=2000) + 1)

        # Build user footprints with allocated IDs
        user_footprints: List[SysUserFootprint] = []
        for u in profile.users:
            u_id = alloc.next_id("sys_user") if alloc else (org_id * 100 + len(user_footprints) + 1)
            user_footprints.append(
                SysUserFootprint(
                    id=u_id,
                    name=u.name,
                    org_id=org_id,
                    role=u.role,
                    job=u.job,
                )
            )

        # Build construction tasks
        task_footprints: List[ConstructionTaskFootprint] = []
        for t in profile.tasks:
            t_id = alloc.next_id("construction_task") if alloc else (org_id * 1000 + len(task_footprints) + 1)
            task_footprints.append(
                ConstructionTaskFootprint(
                    id=t_id,
                    org_id=org_id,
                    name=t["name"],
                    type=t["type"],
                    owner=t["owner"],
                    plan_time=t["plan_time"],
                    actual_time=t["actual_time"],
                    status=t["status"],
                    progress=t["progress"],
                    update_time=t["update_time"],
                )
            )

        # Build data readiness record
        r = profile.readiness
        readiness_footprint = DataReadinessRecordFootprint(
            org_id=org_id,
            batch_id=8,
            static_total=r["static_total"],
            static_completed=r["static_completed"],
            static_rate=r["static_rate"],
            opening_total=r["opening_total"],
            opening_completed=r["opening_completed"],
            opening_rate=r["opening_rate"],
            opening_diff_amount=r["opening_diff_amount"],
            dynamic_total=r["dynamic_total"],
            dynamic_completed=r["dynamic_completed"],
            dynamic_sync_success=r["dynamic_sync_success"],
            dynamic_sync_fail=r["dynamic_sync_fail"],
            dynamic_sync_pending=r["dynamic_sync_pending"],
            dynamic_rate=r["dynamic_rate"],
            last_sync_time=r["last_sync_time"],
            overall_status=r["overall_status"],
        )

        snapshot_footprint = RolloutStatusSnapshotFootprint(
            org_id=org_id,
            snapshot_date=today,
            status="未启动",
        )

        event = NewOrgAdmissionFootprint(
            org_id=org_id,
            name=profile.name,
            region=profile.region,
            batch_id=8,
            status="未启动",
            start_date=profile.start_date,
            end_date=profile.end_date,
            users=user_footprints,
            tasks=task_footprints,
            readiness=readiness_footprint,
            snapshot=snapshot_footprint,
        )

        validate_new_org_admission(event)
        return event


def admit_organization_to_reserve_pool(
    conn: Any,
    baseline: ConstructionBaseline,
    id_allocator: IdAllocator,
    region: Optional[str] = None,
    event_date: Optional[date] = None,
    execute: bool = False,
    audit_log_path: Optional[str] = "output/construction_audit.log",
) -> Tuple[NewOrgAdmissionFootprint, ConstructionWriteResult]:
    """
    High-level entry point to admit a new organization into Batch 8 dynamic reserve pool.
    Guarantees atomic multi-table write, daily_stats cascade, and audit logging.
    """
    playbook = ReservePoolAdmissionPlaybook(
        baseline=baseline,
        id_allocator=id_allocator,
    )
    admission_event = playbook.generate(
        region=region,
        event_date=event_date,
        id_allocator=id_allocator,
    )

    writer = ConstructionWriter(conn=conn, audit_log_path=audit_log_path)
    result = writer.write_construction_events([admission_event], execute=execute)

    if result.success and execute:
        # Dynamically update in-memory baseline
        baseline.orgs[admission_event.org_id] = {
            "id": admission_event.org_id,
            "name": admission_event.name,
            "batch_id": 8,
            "status": "未启动",
            "region": admission_event.region,
            "start_date": admission_event.start_date,
            "end_date": admission_event.end_date,
        }
        baseline.orgs_by_status.setdefault("未启动", []).append(admission_event.org_id)
        baseline.org_users[admission_event.org_id] = [
            {"name": u.name, "role": u.role} for u in admission_event.users
        ]
        logger.info(
            f"Admitted org {admission_event.org_id} ({admission_event.name}, {admission_event.region}) "
            f"into Batch 8 reserve pool. Users: {len(admission_event.users)}, Tasks: {len(admission_event.tasks)}."
        )

    return admission_event, result
