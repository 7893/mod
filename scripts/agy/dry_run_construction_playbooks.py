#!/usr/bin/env python3
"""
Phase B Dry-Run Script: 7 Construction Playbooks Generation & Audit.

Connects to MySQL database in read-only mode, loads the construction baseline,
executes all 7 construction playbooks across sample units according to strict
causal gates, validates all generated footprints, and prints an impact report.

ZERO writes are performed against the database.
"""

from __future__ import annotations

from datetime import date
import os
import sys

from dotenv import load_dotenv
import pymysql

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from simulation.construction_models import validate_construction_event  # noqa: E402
from simulation.construction_playbooks import (  # noqa: E402
    BatchRolloutPlaybook,
    DataReadinessPlaybook,
    DualRunCheckPlaybook,
    InterfaceDebuggingPlaybook,
    PoolOnboardingPlaybook,
    TrainingCertificationPlaybook,
    TransitionReviewPlaybook,
)
from simulation.engine_context import IdAllocator, load_construction_baseline  # noqa: E402


def get_db_connection() -> pymysql.Connection:
    """Connect to MySQL using environment credentials."""
    env_file = os.path.join(BASE_DIR, ".env.systemd")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()

    host = os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST", "127.0.0.1")
    port = int(os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT", "3306"))
    user = os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER", "root")
    password = os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD", "")
    database = os.getenv("MOD_DB_NAME") or os.getenv("MOD_V2_DB_NAME", "mod_s_v2")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,  # secret-scan: allow
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )


def run_dry_run():
    print("=" * 70)
    print(" [DRY-RUN] MOD Construction Playbooks Footprint Audit (Read-Only)")
    print("=" * 70)

    conn = get_db_connection()
    try:
        print("[1/4] Loading construction baseline from database...")
        baseline = load_construction_baseline(conn)
        allocator = IdAllocator(baseline.next_ids)

        latest_dt = baseline.latest_business_date
        sim_date = date(latest_dt.year, latest_dt.month, latest_dt.day)
        print(f"      - Latest business date: {latest_dt} (Sim Date: {sim_date})")
        print(f"      - Total org units: {len(baseline.orgs)}")
        for st, org_list in baseline.orgs_by_status.items():
            print(f"        * {st}: {len(org_list)} units")
        print(f"      - Next IDs: {baseline.next_ids}")

        print("\n[2/4] Generating footprints for 7 construction events...")
        generated_events = []
        table_impacts = {
            "org_unit (UPDATE)": 0,
            "rollout_status_snapshot (INSERT)": 0,
            "data_readiness (UPDATE)": 0,
            "training (INSERT)": 0,
            "dual_run_result (INSERT)": 0,
            "construction_task (INSERT/UPDATE)": 0,
            "rollout_batch (UPDATE)": 0,
        }

        # 1. Pool Onboarding (未启动 -> 准备中)
        p1 = PoolOnboardingPlaybook(baseline, seed=101)
        unstarted_orgs = baseline.orgs_by_status.get("未启动", [])
        if unstarted_orgs:
            org_id = unstarted_orgs[0]
            e1 = p1.generate(org_id=org_id, event_date=sim_date, id_allocator=allocator)
            generated_events.append(("入池 (PoolOnboarding)", e1))
            table_impacts["org_unit (UPDATE)"] += 1
            table_impacts["rollout_status_snapshot (INSERT)"] += 1
            table_impacts["construction_task (INSERT/UPDATE)"] += len(e1.initial_tasks)
            print(f"      ✓ Event 1 [入池]: Org {org_id} ('{baseline.orgs[org_id]['name']}') -> 准备中")

        # 2. Data Readiness (准备中)
        p2 = DataReadinessPlaybook(baseline, seed=102)
        prep_orgs = baseline.orgs_by_status.get("准备中", [])
        if prep_orgs:
            org_id = prep_orgs[0]
            e2 = p2.generate(org_id=org_id, event_date=sim_date, task_id=allocator.next_id("construction_task"))
            generated_events.append(("数据准备 (DataReadiness)", e2))
            table_impacts["data_readiness (UPDATE)"] += 1
            table_impacts["construction_task (INSERT/UPDATE)"] += 1
            print(f"      ✓ Event 2 [数据准备]: Org {org_id} -> static={e2.readiness.static_rate}, dynamic={e2.readiness.dynamic_rate}")

        # 3. Training Certification (准备中)
        p3 = TrainingCertificationPlaybook(baseline, seed=103)
        if prep_orgs and len(prep_orgs) > 1:
            org_id = prep_orgs[1]
            e3 = p3.generate(org_id=org_id, event_date=sim_date, id_allocator=allocator)
            generated_events.append(("培训认证 (TrainingCertification)", e3))
            table_impacts["training (INSERT)"] += 1
            table_impacts["construction_task (INSERT/UPDATE)"] += 1
            print(f"      ✓ Event 3 [培训认证]: Org {org_id} -> {e3.training.type} (attendees={e3.training.actual}, passed={e3.training.passed})")

        # 4. Interface Debugging (已具备双轨条件)
        p4 = InterfaceDebuggingPlaybook(baseline, seed=104)
        ready_orgs = baseline.orgs_by_status.get("已具备双轨条件", [])
        if ready_orgs:
            org_id = ready_orgs[0]
            e4 = p4.generate(org_id=org_id, event_date=sim_date, id_allocator=allocator, completed=True)
            generated_events.append(("接口联调 (InterfaceDebugging)", e4))
            table_impacts["construction_task (INSERT/UPDATE)"] += 1
            print(f"      ✓ Event 4 [接口联调]: Org {org_id} -> {e4.interface_name} (all {e4.test_case_count} tests passed)")

        # 5. Dual Run Check (双轨运行中)
        p5 = DualRunCheckPlaybook(baseline, seed=105)
        dual_orgs = baseline.orgs_by_status.get("双轨运行中", [])
        if dual_orgs:
            # 5a. Matched unit
            org_id_a = dual_orgs[0]
            e5a = p5.generate(org_id=org_id_a, event_date=sim_date, id_allocator=allocator, force_diff=False)
            generated_events.append(("双轨核对 (DualRun-一致)", e5a))
            table_impacts["dual_run_result (INSERT)"] += 1
            table_impacts["construction_task (INSERT/UPDATE)"] += 1
            print(f"      ✓ Event 5a [双轨核对-正常]: Org {org_id_a} -> {e5a.dual_run.check_type}: {e5a.dual_run.result} (diff={e5a.dual_run.diff_amount})")

            # 5b. Discrepancy unit (困难户样例)
            if len(dual_orgs) > 1:
                org_id_b = dual_orgs[1]
                e5b = p5.generate(org_id=org_id_b, event_date=sim_date, id_allocator=allocator, force_diff=True)
                generated_events.append(("双轨核对 (DualRun-差异困难户)", e5b))
                table_impacts["dual_run_result (INSERT)"] += 1
                table_impacts["construction_task (INSERT/UPDATE)"] += 1
                print(f"      ✓ Event 5b [双轨核对-差异]: Org {org_id_b} -> {e5b.dual_run.check_type}: {e5b.dual_run.result} (diff={e5b.dual_run.diff_amount})")

        # 6. Transition Review (已具备双轨条件 -> 双轨运行中)
        p6 = TransitionReviewPlaybook(baseline, seed=106)
        if ready_orgs and len(ready_orgs) > 1:
            org_id = ready_orgs[1]
            e6 = p6.generate(
                org_id=org_id,
                event_date=sim_date,
                from_status="已具备双轨条件",
                to_status="双轨运行中",
            )
            generated_events.append(("跃迁评审 (TransitionReview)", e6))
            table_impacts["org_unit (UPDATE)"] += 1
            table_impacts["rollout_status_snapshot (INSERT)"] += 1
            print(f"      ✓ Event 6 [跃迁评审]: Org {org_id} -> 已具备双轨条件 -> 双轨运行中 (留痕已生成)")

        # 7. Batch Rollout
        p7 = BatchRolloutPlaybook(baseline, seed=107)
        # Check an active batch in 准备中
        target_batch = None
        for b_id, b_info in baseline.batches.items():
            if b_info["status"] == "准备中":
                target_batch = b_info
                break
        if target_batch:
            e7 = p7.generate(
                batch_id=target_batch["id"],
                event_date=sim_date,
                from_status="准备中",
                to_status="双轨运行中",
            )
            generated_events.append(("批次推进 (BatchRollout)", e7))
            table_impacts["rollout_batch (UPDATE)"] += 1
            print(f"      ✓ Event 7 [批次推进]: Batch {target_batch['id']} ('{target_batch['name']}') -> 准备中 -> 双轨运行中")

        print("\n[3/4] Validating all generated footprints through deterministic validators...")
        for name, ev in generated_events:
            validate_construction_event(ev)
            print(f"      ✓ Validated: {name}")

        print("\n[4/4] Projected Database Table Impact:")
        for tbl, count in table_impacts.items():
            print(f"      * {tbl:<35}: {count:>3} rows")

        print("\n" + "=" * 70)
        print(" [RESULT] DRY-RUN PASSED. 0 database modifications committed.")
        print("=" * 70)

    finally:
        conn.close()


if __name__ == "__main__":
    run_dry_run()
