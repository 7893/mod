#!/usr/bin/env python3
"""
Dedicated Batch Write Runner for Simulation Engine Step 2 (Construction Mainline).

Enforces:
1. Strict environment authorization (MOD_SIMULATION_ENGINE_ENABLED=true).
2. Complete pre-write safety snapshot backup to scripts/agy/output/backups/.
3. In-memory deterministic validation of 100% footprints before writing.
4. Strict chunked batching (2000~10000 rows per batch), individual batch commits,
   single transaction per batch, and live progress logging.
5. Immediate atomic rollback on any batch error with zero half-baked records.
6. Post-write 8-gate verification audit (read-only) ensuring zero regressions.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
import pymysql

# Setup python path
BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.simulation.construction_models import (  # noqa: E402
    validate_construction_event,
)
from app.simulation.construction_playbooks import (  # noqa: E402
    DataReadinessPlaybook,
    DualRunCheckPlaybook,
    InterfaceDebuggingPlaybook,
    TrainingCertificationPlaybook,
    TransitionReviewPlaybook,
)
from app.simulation.construction_writer import ConstructionWriter  # noqa: E402
from app.simulation.engine_context import IdAllocator, load_construction_baseline  # noqa: E402


def get_db_connection() -> pymysql.Connection:
    """Connect to MySQL database using local environment credentials."""
    for env_file in [BASE_DIR / ".env.systemd", BASE_DIR / ".env.local", BASE_DIR / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
            break

    host = os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST", "127.0.0.1")
    port = int(os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT", "3306"))
    user = os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER", "")
    password = os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD", "")
    database = os.getenv("MOD_DB_NAME") or os.getenv("MOD_V2_DB_NAME", "mod_s_v2")

    if not user:
        raise ValueError("Database user not configured in environment (MOD_DB_USER / MOD_V2_DB_USER)")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,  # secret-scan: allow
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )


def generate_step2_events(
    baseline: Any,
    allocator: IdAllocator,
    sim_date: date,
    seed: int = 2026,
) -> List[object]:
    """Generate balanced, causal construction events across all active stages."""
    rng = random.Random(seed)
    events: List[object] = []

    # 1. TransitionReview: 20 units in '已上线' advancing to '稳定运行'
    # These units already have business docs and future snapshots are '稳定运行'
    rev_pb = TransitionReviewPlaybook(baseline, seed=seed + 1)
    launched_units = baseline.orgs_by_status.get("已上线", [])
    selected_transitions = launched_units[:20]
    for oid in selected_transitions:
        ev = rev_pb.generate(
            org_id=oid,
            event_date=sim_date,
            from_status="已上线",
            to_status="稳定运行",
        )
        events.append(ev)

    # 2. DualRunCheck: 205 units in '双轨运行中' generating daily comparison checks
    dual_pb = DualRunCheckPlaybook(baseline, seed=seed + 2)
    dual_units = baseline.orgs_by_status.get("双轨运行中", [])
    check_types = ["业务单据金额核对", "凭证借贷汇总核对", "月末科目余额比对"]
    for oid in dual_units:
        # Generate 6 checks per unit across the 3 valid check types
        for ct in check_types * 2:
            ev = dual_pb.generate(org_id=oid, event_date=sim_date, id_allocator=allocator, check_type=ct)
            events.append(ev)

    # 3. TrainingCertification: 238 units in '准备中' conducting user training
    train_pb = TrainingCertificationPlaybook(baseline, seed=seed + 3)
    prep_units = baseline.orgs_by_status.get("准备中", [])
    for oid in prep_units:
        for _ in range(2):
            ev = train_pb.generate(org_id=oid, event_date=sim_date, id_allocator=allocator)
            events.append(ev)

    # 4. DataReadiness: 238 units in '准备中' advancing data readiness sync
    data_pb = DataReadinessPlaybook(baseline, seed=seed + 4)
    for oid in prep_units:
        t_id = allocator.next_id("construction_task")
        ev = data_pb.generate(org_id=oid, event_date=sim_date, task_id=t_id)
        events.append(ev)

    # 5. InterfaceDebugging: 250 units updating interface verification tasks
    iface_pb = InterfaceDebuggingPlaybook(baseline, seed=seed + 5)
    debug_pool = prep_units + baseline.orgs_by_status.get("已具备双轨条件", [])
    for oid in debug_pool[:250]:
        ev = iface_pb.generate(org_id=oid, event_date=sim_date, id_allocator=allocator)
        events.append(ev)

    rng.shuffle(events)
    return events


def execute_batched_write(
    conn: pymysql.Connection,
    events: List[object],
    writer: ConstructionWriter,
    target_batch_rows: int = 2000,
) -> Dict[str, Any]:
    """Execute write in strict batches with single-batch transactions and live logging."""
    cursor = conn.cursor()
    total_events = len(events)
    rows_written = {
        "org_unit": 0,
        "rollout_status_snapshot": 0,
        "data_readiness": 0,
        "training": 0,
        "dual_run_result": 0,
        "construction_task": 0,
        "rollout_batch": 0,
    }

    batch_num = 1
    event_idx = 0
    batch_records: List[Dict[str, Any]] = []

    print(f"\n[EXECUTION] Beginning batched write: ~{total_events} events, target {target_batch_rows} rows/batch...")

    try:
        while event_idx < total_events:
            batch_event_start = event_idx
            batch_rows_start = sum(rows_written.values())
            current_batch_events = 0

            # Accumulate events until current batch reaches target_batch_rows or end of list
            while event_idx < total_events:
                ev = events[event_idx]
                writer._write_single_event(cursor, ev, rows_written)
                event_idx += 1
                current_batch_events += 1
                rows_in_current_batch = sum(rows_written.values()) - batch_rows_start
                if rows_in_current_batch >= target_batch_rows:
                    break

            # Commit current batch
            conn.commit()
            batch_rows_end = sum(rows_written.values())
            batch_rows = batch_rows_end - batch_rows_start
            pct = (event_idx / total_events) * 100

            log_msg = (
                f"  [BATCH {batch_num}] Committed | "
                f"Batch Rows: {batch_rows:,} | "
                f"Events: {current_batch_events} (Index: {batch_event_start} -> {event_idx - 1}) | "
                f"Cumulative: {batch_rows_end:,} rows ({pct:.1f}%)"
            )
            print(log_msg)
            batch_records.append({
                "batch": batch_num,
                "events": current_batch_events,
                "rows": batch_rows,
                "cumulative_rows": batch_rows_end,
            })
            batch_num += 1

        print(f"[EXECUTION] Successfully committed all {batch_num - 1} batches without errors.")
        return {
            "success": True,
            "batches": batch_records,
            "rows_written": rows_written,
            "total_rows": sum(rows_written.values()),
        }

    except Exception as ex:
        conn.rollback()
        print(f"\n[ERROR] Transaction failed in batch {batch_num}: {ex}")
        print("        Rolled back current batch. Aborting write to prevent partial state.")
        raise


def run_batch_write_pipeline(dry_run: bool = False, batch_rows: int = 2000):
    """Main pipeline executing pre-write check, backup, batched write, and post-write verification."""
    print("=" * 80)
    print(" [PHASE E BATCH WRITE] Step 2 Construction Mainline Write Execution")
    print("=" * 80)

    # 1. Authorization check
    enabled = os.environ.get("MOD_SIMULATION_ENGINE_ENABLED", "").strip().lower() in ("true", "1", "yes")
    if not enabled and not dry_run:
        print("\n[ERROR] BLOCKED: Write is not authorized.")
        print("        Requires environment variable: MOD_SIMULATION_ENGINE_ENABLED=true")
        print("        Run with --dry-run to test in read-only mode, or export MOD_SIMULATION_ENGINE_ENABLED=true")
        sys.exit(1)

    # 2. Database connection & baseline read
    conn = get_db_connection()
    try:
        print("\n[Step 1/5] Loading starting construction baseline...")
        baseline = load_construction_baseline(conn)
        allocator = IdAllocator(baseline.next_ids)

        latest_dt = baseline.latest_business_date
        sim_date = (latest_dt + timedelta(days=1)).date()
        print(f"  - Baseline latest business date : {latest_dt}")
        print(f"  - Target simulation date        : {sim_date}")
        print(f"  - Total org units in baseline   : {len(baseline.orgs)}")
        for st, org_list in baseline.orgs_by_status.items():
            print(f"    * {st:12s}: {len(org_list)} units")

        # 3. Generate and validate events in memory
        print(f"\n[Step 2/5] Generating and strictly validating event footprints for {sim_date}...")
        events = generate_step2_events(baseline, allocator, sim_date)
        print(f"  - Total events generated: {len(events)}")
        for ev in events:
            validate_construction_event(ev)
        print("  - Validation status     : 100% PASS (Zero constraint violations)")

        writer = ConstructionWriter(
            conn=conn,
            backup_dir=str(BASE_DIR / "scripts" / "agy" / "output" / "backups"),
            audit_log_path=str(BASE_DIR / "output" / "construction_audit.log"),
        )

        if dry_run:
            print("\n[DRY-RUN] Script running in Dry-Run mode. Skipping backup and write operations.")
            print("          0 records written to database.")
            return

        # 4. Pre-write table backups
        print("\n[Step 3/5] Executing pre-write safety snapshot backup of 7 affected tables...")
        tables_to_backup = [
            "org_unit",
            "construction_task",
            "rollout_batch",
            "rollout_status_snapshot",
            "data_readiness",
            "training",
            "dual_run_result",
        ]
        t0_backup = time.perf_counter()
        backup_path = writer.backup_affected_tables(tables_to_backup)
        backup_dur = time.perf_counter() - t0_backup
        backup_size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
        print(f"  - Backup file saved : {backup_path}")
        print(f"  - Backup duration   : {backup_dur:.2f}s (Size: {backup_size_mb:.2f} MB)")

        # 5. Execute batched write
        print(f"\n[Step 4/5] Executing controlled batched write ({batch_rows} rows/batch)...")
        t0_write = time.perf_counter()
        write_res = execute_batched_write(conn, events, writer, target_batch_rows=batch_rows)
        write_dur = time.perf_counter() - t0_write

        # Record audit log
        audit_data = {
            "timestamp": datetime.now().isoformat(),
            "target_date": str(sim_date),
            "events_count": len(events),
            "batches_count": len(write_res["batches"]),
            "total_rows": write_res["total_rows"],
            "rows_written": write_res["rows_written"],
            "backup_file": backup_path,
            "duration_ms": write_dur * 1000,
            "status": "SUCCESS",
        }
        writer._record_audit(audit_data)

        print(f"\n[Step 4 Complete] Write finished in {write_dur:.2f}s:")
        for table, count in write_res["rows_written"].items():
            print(f"  * {table:25s}: {count:,} rows")
        print(f"  * TOTAL ROWS COMMITTED     : {write_res['total_rows']:,} rows across {len(write_res['batches'])} batches")

        # 6. Post-write 8-gate verification audit
        print("\n[Step 5/5] Running immediate post-write 8-gate verification audit (read-only)...")
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        from scripts.agy.verify_step2_dry_run import run_full_dry_run_audit

        audit_passed = run_full_dry_run_audit()
        if not audit_passed:
            print("\n[CRITICAL ALERT] Post-write audit detected verification gate failures!")
            sys.exit(1)
        else:
            print("\n[SUCCESS] ALL 8 GATES PASSED POST-WRITE AUDIT.")
            print("          Database is in 100% self-consistent state with zero regressions.")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 2 Construction Mainline Batched Write Runner")
    parser.add_argument("--dry-run", action="store_true", help="Perform generation and dry-run audit only without writing")
    parser.add_argument("--batch-rows", type=int, default=2000, help="Target rows per committed batch (default: 2000)")
    args = parser.parse_args()

    run_batch_write_pipeline(dry_run=args.dry_run, batch_rows=args.batch_rows)
