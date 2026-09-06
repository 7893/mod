"""Verification script for Simulation Engine Step 1 (Expense Reimbursement Footprint & Writer).

Follows ENFORCEMENT Gate B rules:
- Reads DB credentials from environment (.env.local).
- Tests switch gate (fail-closed).
- Tests atomic rollback (half-baked write leaves zero records).
- Executes controlled small batch write (100 events on 2026-09-04).
- Verifies 10 multi-table assertions and all KI-017 zero-regression checks.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

import pymysql

from simulation.engine_context import IdAllocator, load_simulation_baseline
from simulation.expense_playbook import ExpensePlaybook
from simulation.simulation_writer import SimulationWriter, is_simulation_engine_enabled


def load_env():
    env_file = Path(__file__).resolve().parents[2] / ".env.local"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("export "):
                    k, v = line[7:].strip().split("=", 1)
                    os.environ[k] = v


def get_connection():
    return pymysql.connect(
        host=os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT", "3306")),
        user=os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER", "mod_v2_writer"),
        password=os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD", ""),  # secret-scan: allow
        database=os.getenv("MOD_DB_NAME_V2") or os.getenv("MOD_V2_DB_NAME", "mod_s_v2"),
        autocommit=False,
        charset="utf8mb4",
    )


def run_verification():
    load_env()
    print("=== Simulation Engine Step 1: Verification Started ===")

    # 1. Gate check: switch disabled behavior
    print("\n[Step 1/5] Testing switch gate (fail-closed)...")
    os.environ["MOD_SIMULATION_ENGINE_ENABLED"] = "false"
    assert not is_simulation_engine_enabled()
    audit_log = Path("output/simulation_audit.log")
    writer = SimulationWriter(audit_log_path=str(audit_log))
    try:
        writer.write_events([])
    except RuntimeError as ex:
        print(f"  Passed: write rejected when switch=false ({ex})")
    else:
        print("  FAILED: write was not rejected!")
        sys.exit(1)

    # 2. Baseline read from live database
    print("\n[Step 2/5] Reading simulation baseline from database...")
    conn = get_connection()
    baseline = load_simulation_baseline(conn)
    print(f"  Stock latest business date: {baseline.latest_business_date}")
    print(f"  Online units count: {len(baseline.online_org_ids)}")
    print(f"  Total orgs in user map: {len(baseline.org_users)}")
    print(f"  Captured next IDs: {baseline.next_ids}")

    assert baseline.latest_business_date is not None
    assert len(baseline.online_org_ids) >= 700
    for org_id in baseline.online_org_ids:
        assert len(baseline.org_users.get(org_id, [])) > 0

    # 3. Transaction atomic rollback test
    print("\n[Step 3/5] Testing transactional atomic rollback...")
    allocator = IdAllocator(baseline.next_ids)
    playbook = ExpensePlaybook(baseline=baseline, id_allocator=allocator, seed=2026)
    next_day = baseline.latest_business_date.date() + timedelta(days=1)
    target_dt = datetime.combine(next_day, time(8, 30))
    dummy_event = playbook.generate_event(target_date=target_dt)

    # Tamper with an ID inside integration to violate foreign key or unique constraint intentionally
    dummy_event.integration.voucher_id = -999999  # Non-existent FK voucher_id

    os.environ["MOD_SIMULATION_ENGINE_ENABLED"] = "true"
    rollback_writer = SimulationWriter(conn=conn, audit_log_path=str(audit_log))
    try:
        rollback_writer.write_events([dummy_event])
        print("  FAILED: write should have raised exception!")
        sys.exit(1)
    except Exception as ex:
        print(f"  Passed: write failed as expected ({type(ex).__name__}: {ex})")

    # Verify no partial rows were committed
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM business_document WHERE id = %s;", (dummy_event.document.id,))
        doc_exists = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounting_voucher WHERE id = %s;", (dummy_event.voucher.id,))
        vch_exists = cur.fetchone()[0]
        assert doc_exists == 0, "Partial document was written!"
        assert vch_exists == 0, "Partial voucher was written!"
        print("  Passed: 0 partial records found. Full transaction rollback verified.")

    # 4. Small batch real write (100 events)
    print(f"\n[Step 4/5] Executing controlled write of 100 expense reimbursement events on {next_day}...")
    # Re-fetch fresh IDs from DB
    baseline = load_simulation_baseline(conn)
    allocator = IdAllocator(baseline.next_ids)
    playbook = ExpensePlaybook(baseline=baseline, id_allocator=allocator, seed=8888)

    events = playbook.generate_batch(count=100, target_date=target_dt)
    print(f"  Generated {len(events)} events for target date {target_dt.date()}")

    real_writer = SimulationWriter(conn=conn, audit_log_path=str(audit_log))
    res = real_writer.write_events(events)
    print(f"  Write completed in {res.duration_ms} ms: {res.rows_written}")

    # 5. Full regression and assertion checks
    print("\n[Step 5/5] Running verification assertions and KI-017 regression queries...")
    with conn.cursor() as cur:
        # Check newly inserted documents
        inserted_doc_ids = [e.document.id for e in events]
        cur.execute(
            f"SELECT COUNT(*) FROM business_document WHERE id IN ({','.join(map(str, inserted_doc_ids))});"
        )
        assert cur.fetchone()[0] == 100, "Not all 100 documents found!"

        # Check applicants 100% hit sys_user for same org
        cur.execute(f"""
            SELECT COUNT(*)
            FROM business_document d
            LEFT JOIN sys_user u ON d.org_id = u.org_id AND d.applicant = u.name
            WHERE d.id IN ({','.join(map(str, inserted_doc_ids))}) AND u.name IS NULL;
        """)
        mismatch_cnt = cur.fetchone()[0]
        print(f"  Applicant mismatch (must be 0): {mismatch_cnt}")
        assert mismatch_cnt == 0, "Applicant mismatch found!"

        # Check line sums match document amounts exactly
        cur.execute(f"""
            SELECT d.id, d.amount, SUM(l.amount)
            FROM business_document d
            JOIN business_document_line l ON d.id = l.doc_id
            WHERE d.id IN ({','.join(map(str, inserted_doc_ids))})
            GROUP BY d.id, d.amount
            HAVING d.amount != SUM(l.amount);
        """)
        imbalanced_docs = cur.fetchall()
        print(f"  Document amount vs lines mismatch (must be 0): {len(imbalanced_docs)}")
        assert len(imbalanced_docs) == 0, f"Imbalanced docs: {imbalanced_docs}"

        # Check voucher debit == credit == doc amount
        inserted_vch_ids = [e.voucher.id for e in events]
        cur.execute(f"""
            SELECT COUNT(*)
            FROM accounting_voucher
            WHERE id IN ({','.join(map(str, inserted_vch_ids))}) AND debit != credit;
        """)
        imbalanced_vchs = cur.fetchone()[0]
        print(f"  Voucher debit!=credit (must be 0): {imbalanced_vchs}")
        assert imbalanced_vchs == 0, "Imbalanced vouchers found!"

        # Check voucher lines debit sum == credit sum == voucher debit
        cur.execute(f"""
            SELECT v.id, v.debit, SUM(vl.debit), SUM(vl.credit)
            FROM accounting_voucher v
            JOIN accounting_voucher_line vl ON v.id = vl.voucher_id
            WHERE v.id IN ({','.join(map(str, inserted_vch_ids))})
            GROUP BY v.id, v.debit
            HAVING v.debit != SUM(vl.debit) OR v.debit != SUM(vl.credit);
        """)
        imbalanced_vlines = cur.fetchall()
        print(f"  Voucher lines imbalance (must be 0): {len(imbalanced_vlines)}")
        assert len(imbalanced_vlines) == 0, f"Imbalanced voucher lines: {imbalanced_vlines}"

        # Check orphan vouchers
        cur.execute(f"""
            SELECT COUNT(*)
            FROM accounting_voucher v
            LEFT JOIN document_voucher_link l ON v.id = l.voucher_id
            WHERE v.id IN ({','.join(map(str, inserted_vch_ids))}) AND l.voucher_id IS NULL;
        """)
        orphan_vchs = cur.fetchone()[0]
        print(f"  Orphan vouchers (must be 0): {orphan_vchs}")
        assert orphan_vchs == 0, "Orphan vouchers found!"

        # Check integration results
        cur.execute(f"""
            SELECT status, COUNT(*)
            FROM integration_result
            WHERE voucher_id IN ({','.join(map(str, inserted_vch_ids))})
            GROUP BY status;
        """)
        int_dist = dict(cur.fetchall())
        print(f"  Integration results distribution: {int_dist}")
        assert int_dist.get("SUCCESS", 0) > 85, f"Unexpected low success rate: {int_dist}"

        # Check daily_stats for target_dt
        cur.execute("SELECT * FROM daily_stats WHERE stat_date = %s;", (str(target_dt.date()),))
        stat_row = cur.fetchone()
        print(f"  daily_stats {target_dt.date()} row: {stat_row}")
        assert stat_row is not None, f"daily_stats for {target_dt.date()} was not created!"

        # Full KI-017 Global Regression Queries
        print("\n--- KI-017 Global Regression Checks ---")
        cur.execute("SELECT COUNT(*) FROM business_document WHERE status LIKE '%\\r';")
        assert cur.fetchone()[0] == 0, "Status trailing CR regression!"
        print("  Passed: 0 documents with trailing \\r")

        cur.execute("SELECT COUNT(*) FROM business_document WHERE approve_time < submit_time;")
        assert cur.fetchone()[0] == 0, "Time inversion regression!"
        print("  Passed: 0 documents with approve_time < submit_time")

        cur.execute("SELECT COUNT(*) FROM accounting_voucher WHERE debit != credit;")
        assert cur.fetchone()[0] == 0, "Voucher debit/credit imbalance regression!"
        print("  Passed: 0 imbalanced accounting vouchers in database")

        cur.execute("""
            SELECT COUNT(*)
            FROM accounting_voucher v
            LEFT JOIN document_voucher_link l ON v.id = l.voucher_id
            WHERE l.voucher_id IS NULL;
        """)
        assert cur.fetchone()[0] == 0, "Orphan voucher regression!"
        print("  Passed: 0 orphan vouchers across entire database")

        cur.execute("""
            SELECT COUNT(*)
            FROM business_document d
            LEFT JOIN sys_user u ON d.org_id = u.org_id AND d.applicant = u.name
            WHERE u.name IS NULL;
        """)
        assert cur.fetchone()[0] == 0, "Applicant cross-unit/mismatch regression!"
        print("  Passed: 100% documents applicant matches sys_user of the same org across entire database")

    conn.close()
    print("\n✅ All 10 verification assertions and all KI-017 regression checks PASSED!")


if __name__ == "__main__":
    run_verification()
