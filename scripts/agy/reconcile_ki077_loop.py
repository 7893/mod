#!/usr/bin/env python3
"""
scripts/agy/reconcile_ki077_loop.py
Audits, backs up, and reconciles:
1. dual_run_result future rows (> '2026-09-11')
2. daily_stats cumulative counts for '2026-09-11'
3. simulator fuse state in output/simulator_fuse_state.json

Usage:
  backend/.venv/bin/python scripts/agy/reconcile_ki077_loop.py --dry-run
  backend/.venv/bin/python scripts/agy/reconcile_ki077_loop.py --backup
  backend/.venv/bin/python scripts/agy/reconcile_ki077_loop.py --execute
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env.systemd")
sys.path.insert(0, str(BASE_DIR / "backend"))

from sqlalchemy import create_engine, text
from app.config import get_settings

HK_TZ = ZoneInfo("Asia/Hong_Kong")
BACKUP_DIR = BASE_DIR / "artifacts" / "v2-sim-data"


def get_db_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        execution_options={"isolation_level": "AUTOCOMMIT"},
        pool_pre_ping=True,
    )


def audit(conn):
    print("==================================================")
    print("  AUDIT: Current Financial & Simulation State")
    print("==================================================")

    # 1. dual_run_result check
    dr_all = conn.execute(text("SELECT COUNT(*) AS total, MAX(check_date) AS max_date FROM dual_run_result")).mappings().one()
    dr_future = conn.execute(text("SELECT COUNT(*) AS future_cnt FROM dual_run_result WHERE check_date > '2026-09-11'")).mappings().one()
    print(f"[dual_run_result] Total: {dr_all['total']}, Max Date: {dr_all['max_date']}, Future (> 2026-09-11): {dr_future['future_cnt']}")

    # 2. Real counts in core tables
    org_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM org_unit")).mappings().one()["c"]
    user_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM sys_user")).mappings().one()["c"]
    doc_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM business_document WHERE submit_time <= '2026-09-11 23:59:59'")).mappings().one()["c"]
    vc_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM accounting_voucher WHERE gen_time <= '2026-09-11 23:59:59'")).mappings().one()["c"]
    doc_line_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM business_document_line")).mappings().one()["c"]
    vc_line_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM accounting_voucher_line")).mappings().one()["c"]
    link_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM document_voucher_link")).mappings().one()["c"]
    ir_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM integration_result WHERE integration_time <= '2026-09-11 23:59:59'")).mappings().one()["c"]
    ir_succ = conn.execute(text("SELECT COUNT(*) AS c FROM integration_result WHERE integration_time <= '2026-09-11 23:59:59' AND status = 'SUCCESS'")).mappings().one()["c"]
    dr_valid = conn.execute(text("SELECT COUNT(*) AS c FROM dual_run_result WHERE check_date <= '2026-09-11'")).mappings().one()["c"]

    print(f"[Real Core Counts as of 2026-09-11]")
    print(f"  org_count:            {org_cnt}")
    print(f"  user_count:           {user_cnt}")
    print(f"  doc_count:            {doc_cnt}")
    print(f"  voucher_count:        {vc_cnt}")
    print(f"  doc_line_count:       {doc_line_cnt}")
    print(f"  voucher_line_count:   {vc_line_cnt}")
    print(f"  link_count:           {link_cnt}")
    print(f"  integration_count:    {ir_cnt} (success: {ir_succ})")
    print(f"  dual_run_count:       {dr_valid}")

    # 3. daily_stats current row
    ds_row = conn.execute(text("SELECT * FROM daily_stats WHERE stat_date = '2026-09-11'")).mappings().first()
    if ds_row:
        print(f"\n[daily_stats Current Record for 2026-09-11]")
        print(f"  org_count:            {ds_row['org_count']}  (gap: {org_cnt - ds_row['org_count']})")
        print(f"  user_count:           {ds_row['user_count']}  (gap: {user_cnt - ds_row['user_count']})")
        print(f"  doc_count:            {ds_row['doc_count']}  (gap: {doc_cnt - ds_row['doc_count']})")
        print(f"  voucher_count:        {ds_row['voucher_count']}  (gap: {vc_cnt - ds_row['voucher_count']})")
        print(f"  doc_line_count:       {ds_row['doc_line_count']}")
        print(f"  voucher_line_count:   {ds_row['voucher_line_count']}")
        print(f"  link_count:           {ds_row['link_count']}")
        print(f"  integration_count:    {ds_row['integration_count']}")
        print(f"  dual_run_count:       {ds_row['dual_run_count']}")
    else:
        print("\n[daily_stats] No record for 2026-09-11!")

    # 4. Simulator fuse file
    fuse_path = BASE_DIR / "output" / "simulator_fuse_state.json"
    if fuse_path.exists():
        with open(fuse_path, "r", encoding="utf-8") as f:
            fuse_data = json.load(f)
        print(f"\n[Simulator Fuse State]")
        print(f"  business_date: {fuse_data.get('business_date')}")
        print(f"  day_count:     {fuse_data.get('day_count')}")
        print(f"  minute_count:  {fuse_data.get('minute_count')}")
        print(f"  updated_at:    {fuse_data.get('updated_at')}")

    return {
        "org_cnt": org_cnt,
        "user_cnt": user_cnt,
        "doc_cnt": doc_cnt,
        "vc_cnt": vc_cnt,
        "doc_line_cnt": doc_line_cnt,
        "vc_line_cnt": vc_line_cnt,
        "link_cnt": link_cnt,
        "ir_cnt": ir_cnt,
        "ir_succ": ir_succ,
        "dr_valid": dr_valid,
        "future_dr_cnt": dr_future["future_cnt"],
    }


def backup(conn):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Backup future dual_run_result
    future_dr_rows = [dict(r) for r in conn.execute(
        text("SELECT * FROM dual_run_result WHERE check_date > '2026-09-11'")
    ).mappings().all()]
    dr_backup_path = BACKUP_DIR / f"backup_dual_run_result_future_{ts}.json"
    with open(dr_backup_path, "w", encoding="utf-8") as f:
        json.dump(future_dr_rows, f, ensure_ascii=False, indent=2, default=str)
    print(f"[BACKUP] Exported {len(future_dr_rows)} future dual_run_result rows to {dr_backup_path}")

    # 2. Backup daily_stats for 2026-09-11
    ds_rows = [dict(r) for r in conn.execute(
        text("SELECT * FROM daily_stats WHERE stat_date = '2026-09-11'")
    ).mappings().all()]
    ds_backup_path = BACKUP_DIR / f"backup_daily_stats_20260911_{ts}.json"
    with open(ds_backup_path, "w", encoding="utf-8") as f:
        json.dump(ds_rows, f, ensure_ascii=False, indent=2, default=str)
    print(f"[BACKUP] Exported {len(ds_rows)} daily_stats row(s) to {ds_backup_path}")
    return dr_backup_path, ds_backup_path


def execute_reconciliation(conn, stats):
    print("\n==================================================")
    print("  EXECUTING RECONCILIATION")
    print("==================================================")

    # 1. Delete future dual_run_result rows
    print("Step 1: Deleting future dual_run_result (> '2026-09-11')...")
    del_res = conn.execute(text("DELETE FROM dual_run_result WHERE check_date > '2026-09-11'"))
    print(f"  Deleted {del_res.rowcount} future rows from dual_run_result.")

    # 2. Update daily_stats for 2026-09-11
    print("Step 2: Updating daily_stats for 2026-09-11 with accurate cumulative numbers...")
    update_sql = text("""
    UPDATE daily_stats
    SET
        org_count = :org_cnt,
        user_count = :user_cnt,
        doc_count = :doc_cnt,
        voucher_count = :vc_cnt,
        doc_line_count = :doc_line_cnt,
        voucher_line_count = :vc_line_cnt,
        link_count = :link_cnt,
        integration_count = :ir_cnt,
        integration_success = :ir_succ,
        dual_run_count = :dr_valid,
        updated_at = NOW()
    WHERE stat_date = '2026-09-11'
    """)
    upd_res = conn.execute(update_sql, {
        "org_cnt": stats["org_cnt"],
        "user_cnt": stats["user_cnt"],
        "doc_cnt": stats["doc_cnt"],
        "vc_cnt": stats["vc_cnt"],
        "doc_line_cnt": stats["doc_line_cnt"],
        "vc_line_cnt": stats["vc_line_cnt"],
        "link_cnt": stats["link_cnt"],
        "ir_cnt": stats["ir_cnt"],
        "ir_succ": stats["ir_succ"],
        "dr_valid": stats["dr_valid"],
    })
    print(f"  Updated {upd_res.rowcount} row in daily_stats.")

    # 3. Reset simulator fuse state
    print("Step 3: Resetting simulator fuse state in output/simulator_fuse_state.json...")
    fuse_path = BASE_DIR / "output" / "simulator_fuse_state.json"
    now_hkt = datetime.now(HK_TZ)
    new_fuse_data = {
        "business_date": "2026-09-11",
        "day_count": 100,  # Reset to safe non-saturated level
        "minute_key": now_hkt.strftime("%Y-%m-%d %H:%M"),
        "minute_count": 0,
        "timezone": "Asia/Hong_Kong",
        "updated_at": now_hkt.isoformat()
    }
    with open(fuse_path, "w", encoding="utf-8") as f:
        json.dump(new_fuse_data, f, indent=2)
    print(f"  Reset fuse state: day_count=100 (cap is 5000).")

    # 4. Restart mod-simulator
    print("Step 4: Restarting mod-simulator.service...")
    os.system("sudo systemctl restart mod-simulator")
    print("  Service restarted.")


def main():
    parser = argparse.ArgumentParser(description="Audit and reconcile financial and simulator loops.")
    parser.add_argument("--dry-run", action="store_true", help="Run audit and dry-run only")
    parser.add_argument("--backup", action="store_true", help="Perform backup of target records")
    parser.add_argument("--execute", action="store_true", help="Execute the remediation")
    args = parser.parse_args()

    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("SET use_secondary_engine = ON"))
        stats = audit(conn)

        if args.backup:
            backup(conn)
        elif args.execute:
            backup(conn)
            execute_reconciliation(conn, stats)
            print("\nReconciliation completed. Please verify with --dry-run and API probes.")
        else:
            print("\nDefault is dry-run mode. Run with --backup or --execute to take action.")


if __name__ == "__main__":
    main()
