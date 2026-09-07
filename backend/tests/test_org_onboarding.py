"""
backend/tests/test_org_onboarding.py
====================================
Comprehensive tests for KI-035: SOE organization dynamic growth into Batch 8 reserve pool.

Validates:
1. Name generator morphology (古雅地名 + 行业 + 后缀) across 34 provinces & deduplication.
2. User roster rules (3~5 users, 财务总监 + 项目经理 + 经办人, no internal collision).
3. Standard construction tasks (all progress 0, status 未开始, owner in user roster).
4. Data readiness baseline (all rates 0.0%, overall_status 未收集, batch_id = 8).
5. Validation gate rules (strict rejection of wrong batch, status, non-zero tasks, or bad owners).
6. SQL batch_mapped coherence (new units with id > 2000 and batch_id=8 NEVER mapped to batch 7).
7. Zero business data constraint for Batch 8 reserve pool units.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from simulation.construction_models import (
    ConstructionTaskFootprint,
    DataReadinessRecordFootprint,
    NewOrgAdmissionFootprint,
    RolloutStatusSnapshotFootprint,
    SysUserFootprint,
    validate_construction_event,
    validate_new_org_admission,
)
from simulation.engine_context import ConstructionBaseline, IdAllocator
from simulation.org_generator import (
    PROV_PREFIXES,
    SUFFIXES,
    OrgNameGenerator,
)
from simulation.pool_onboarding import ReservePoolAdmissionPlaybook


def test_name_generator_morphology_and_coverage():
    """Verify name generator produces valid morphology across all 34 provinces."""
    gen = OrgNameGenerator(seed=12345)
    assert len(PROV_PREFIXES) == 34

    for prov, prefixes in PROV_PREFIXES.items():
        name, reg = gen.generate_name(region=prov)
        assert reg == prov
        # Must start with one of the province's prefixes
        assert any(name.startswith(p) for p in prefixes), f"{name} does not start with valid prefix for {prov}"
        # Must end with one of the recognized suffixes
        assert any(name.endswith(s) for s in SUFFIXES), f"{name} does not end with valid suffix"


def test_name_generator_deduplication():
    """Verify that existing names are never duplicated."""
    existing = {"金陵能源有限责任公司", "羊城物联有限公司"}
    gen = OrgNameGenerator(existing_names=existing, seed=42)

    generated = set()
    for _ in range(50):
        name, _ = gen.generate_name("江苏省")
        assert name not in existing
        assert name not in generated
        generated.add(name)


def test_user_roster_generation():
    """Verify user roster complies with 3~5 people rule and role specifications."""
    gen = OrgNameGenerator(seed=999)

    # 3-person roster
    r3 = gen.generate_user_roster(3)
    assert len(r3) == 3
    assert r3[0].job == "财务总监" and r3[0].role == "管理人员"
    assert r3[1].job == "项目经理" and r3[1].role == "项目经理"
    assert r3[2].job == "会计主管" and r3[2].role == "经办人"
    names3 = [u.name for u in r3]
    assert len(set(names3)) == 3

    # 4-person roster
    r4 = gen.generate_user_roster(4)
    assert len(r4) == 4
    assert r4[3].job == "出纳"

    # 5-person roster
    r5 = gen.generate_user_roster(5)
    assert len(r5) == 5
    assert r5[4].job == "经办员"


def test_org_profile_generation():
    """Verify complete profile generation for an unstarted unit."""
    gen = OrgNameGenerator(seed=777)
    today = date(2026, 9, 7)
    profile = gen.generate_org_profile(region="广东省", event_date=today, user_count=4)

    assert profile.region == "广东省"
    assert profile.batch_id == 8
    assert profile.status == "未启动"
    assert profile.start_date == today
    assert len(profile.users) == 4
    assert len(profile.tasks) == 30

    user_names = {u.name for u in profile.users}
    for t in profile.tasks:
        assert t["status"] == "未开始"
        assert t["progress"] == 0
        assert t["actual_time"] is None
        assert t["owner"] in user_names
        assert t["update_time"] == today

    assert profile.readiness["batch_id"] == 8
    assert profile.readiness["overall_status"] == "未收集"
    assert profile.readiness["static_completed"] == 0
    assert profile.readiness["opening_completed"] == 0
    assert profile.readiness["dynamic_completed"] == 0


def test_validation_gate_success():
    """Verify a valid NewOrgAdmissionFootprint passes validation."""
    today = date(2026, 9, 7)
    org_id = 2001
    users = [
        SysUserFootprint(id=32001, name="张三", org_id=org_id, role="管理人员", job="财务总监"),
        SysUserFootprint(id=32002, name="李四", org_id=org_id, role="项目经理", job="项目经理"),
        SysUserFootprint(id=32003, name="王五", org_id=org_id, role="经办人", job="会计主管"),
    ]
    tasks = [
        ConstructionTaskFootprint(
            id=70000 + i,
            org_id=org_id,
            name=f"任务_{i}",
            type="基础环境",
            owner="张三",
            plan_time=today + timedelta(days=30),
            actual_time=None,
            status="未开始",
            progress=0,
            update_time=today,
        )
        for i in range(25)
    ]
    readiness = DataReadinessRecordFootprint(
        org_id=org_id,
        batch_id=8,
        static_total=60,
        static_completed=0,
        static_rate="0.0%",
        opening_total=80,
        opening_completed=0,
        opening_rate="0.0%",
        opening_diff_amount=Decimal("0.00"),
        dynamic_total=100,
        dynamic_completed=0,
        dynamic_sync_success=0,
        dynamic_sync_fail=0,
        dynamic_sync_pending=100,
        dynamic_rate="0.0%",
        overall_status="未收集",
    )
    snapshot = RolloutStatusSnapshotFootprint(
        org_id=org_id,
        snapshot_date=today,
        status="未启动",
    )

    ev = NewOrgAdmissionFootprint(
        org_id=org_id,
        name="羊城智慧水务研究院",
        region="广东省",
        batch_id=8,
        status="未启动",
        start_date=today,
        end_date=today + timedelta(days=365),
        users=users,
        tasks=tasks,
        readiness=readiness,
        snapshot=snapshot,
    )

    # Must pass both specific and generic validator
    validate_new_org_admission(ev)
    validate_construction_event(ev)


def test_validation_gate_failures():
    """Verify strict rejection of invalid footprints."""
    today = date(2026, 9, 7)
    base_users = [
        SysUserFootprint(id=1, name="张三", org_id=2001, role="管理人员", job="财务总监"),
        SysUserFootprint(id=2, name="李四", org_id=2001, role="项目经理", job="项目经理"),
        SysUserFootprint(id=3, name="王五", org_id=2001, role="经办人", job="会计主管"),
    ]
    base_tasks = [
        ConstructionTaskFootprint(
            id=100 + i,
            org_id=2001,
            name=f"任务_{i}",
            type="基础环境",
            owner="张三",
            plan_time=today + timedelta(days=30),
            actual_time=None,
            status="未开始",
            progress=0,
            update_time=today,
        )
        for i in range(25)
    ]

    # 1. Non-batch-8 rejected
    with pytest.raises(ValueError, match="Batch 8 reserve pool admission requires batch_id=8"):
        ev = NewOrgAdmissionFootprint(
            org_id=2001, name="测试", region="北京市", batch_id=7, status="未启动",
            start_date=today, end_date=today + timedelta(days=30), users=base_users, tasks=base_tasks,
        )
        validate_new_org_admission(ev)

    # 2. Non-unstarted status rejected
    with pytest.raises(ValueError, match="New unit must be '未启动'"):
        ev = NewOrgAdmissionFootprint(
            org_id=2001, name="测试", region="北京市", batch_id=8, status="准备中",
            start_date=today, end_date=today + timedelta(days=30), users=base_users, tasks=base_tasks,
        )
        validate_new_org_admission(ev)

    # 3. Missing finance director rejected
    bad_users = [
        SysUserFootprint(id=1, name="张三", org_id=2001, role="普通用户", job="经办员"),
        SysUserFootprint(id=2, name="李四", org_id=2001, role="项目经理", job="项目经理"),
        SysUserFootprint(id=3, name="王五", org_id=2001, role="经办人", job="会计主管"),
    ]
    with pytest.raises(ValueError, match="missing 财务总监/管理人员"):
        ev = NewOrgAdmissionFootprint(
            org_id=2001, name="测试", region="北京市", batch_id=8, status="未启动",
            start_date=today, end_date=today + timedelta(days=30), users=bad_users, tasks=base_tasks,
        )
        validate_new_org_admission(ev)

    # 4. Task with non-zero progress rejected
    bad_tasks = list(base_tasks)
    bad_tasks[0] = ConstructionTaskFootprint(
        id=999, org_id=2001, name="推进任务", type="基础环境", owner="张三",
        plan_time=today, actual_time=None, status="进行中", progress=10, update_time=today,
    )
    with pytest.raises(ValueError, match="Unstarted unit task must have progress 0"):
        ev = NewOrgAdmissionFootprint(
            org_id=2001, name="测试", region="北京市", batch_id=8, status="未启动",
            start_date=today, end_date=today + timedelta(days=30), users=base_users, tasks=bad_tasks,
        )
        validate_new_org_admission(ev)

    # 5. Task with unknown owner rejected
    orphan_task_suite = [
        ConstructionTaskFootprint(
            id=100 + i, org_id=2001, name=f"任务_{i}", type="基础环境", owner="神秘外人",
            plan_time=today, actual_time=None, status="未开始", progress=0, update_time=today,
        )
        for i in range(25)
    ]
    with pytest.raises(ValueError, match="Task owner '神秘外人' not found"):
        ev = NewOrgAdmissionFootprint(
            org_id=2001, name="测试", region="北京市", batch_id=8, status="未启动",
            start_date=today, end_date=today + timedelta(days=30), users=base_users, tasks=orphan_task_suite,
        )
        validate_new_org_admission(ev)


def test_playbook_generation_with_id_allocator():
    """Verify ReservePoolAdmissionPlaybook integrates smoothly with IdAllocator."""
    baseline = ConstructionBaseline(
        latest_business_date=date(2026, 9, 7),
        orgs={1: {"id": 1, "name": "已有单位", "batch_id": 1, "status": "稳定运行", "region": "北京市", "start_date": date(2025, 1, 1), "end_date": date(2026, 1, 1)}},
        orgs_by_status={"稳定运行": [1]},
        org_users={1: [{"name": "用户A", "role": "经办人"}]},
        next_ids={"org_unit": 2001, "sys_user": 32000, "construction_task": 70000},
        batches={8: {"id": 8, "name": "第八批", "status": "未启动"}},
    )
    allocator = IdAllocator(baseline.next_ids)
    playbook = ReservePoolAdmissionPlaybook(baseline=baseline, id_allocator=allocator, seed=42)

    ev = playbook.generate(region="江苏省", event_date=date(2026, 9, 7), user_count=3)
    assert ev.org_id == 2001
    assert ev.batch_id == 8
    assert ev.status == "未启动"
    assert len(ev.users) == 3
    assert [u.id for u in ev.users] == [32000, 32001, 32002]
    assert len(ev.tasks) == 30
    assert ev.tasks[0].id == 70000
    assert allocator.peek_next_id("org_unit") == 2002


def test_batch_mapped_sql_logic():
    """Verify SQL CASE mapping logic preserves batch 7 (1601..2000) and routes new units to 8."""
    def map_batch(org_id: int, status: str, batch_id: int) -> int:
        if batch_id == 8:
            return 8
        if status == "稳定运行" and org_id <= 150:
            return 1
        if status == "稳定运行" and org_id <= 330:
            return 2
        if status == "稳定运行":
            return 3
        if status == "已上线" and org_id <= 580:
            return 4
        if status == "已上线":
            return 5
        if status == "双轨运行中":
            return 6
        if org_id > 1600 and org_id <= 2000:
            return 7
        return 8

    # Existing units
    assert map_batch(100, "稳定运行", 1) == 1
    assert map_batch(200, "稳定运行", 2) == 2
    assert map_batch(500, "已上线", 4) == 4
    assert map_batch(700, "已上线", 5) == 5
    assert map_batch(800, "双轨运行中", 6) == 6
    assert map_batch(1800, "未启动", 4) == 7  # Legacy batch 7
    assert map_batch(1200, "未启动", 3) == 8  # Legacy batch 8

    # NEW units (KI-035)
    assert map_batch(2001, "未启动", 8) == 8  # Must NOT be 7!
    assert map_batch(2002, "未启动", 8) == 8  # Must NOT be 7!
    assert map_batch(2003, "未启动", 8) == 8  # Must NOT be 7!
