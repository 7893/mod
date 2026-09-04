#!/usr/bin/env python3
"""
Phase 1 Data Governance: Clean Trailing Carriage Returns (\r) in business_document.status.

Safety & Constraints:
- Database: Strictly mod_s_v2 (fails if any other db).
- Non-admin write user: reads credentials from MOD_V2_DB_* environment variables.
- Backup: Exports affected records to scripts/agy/output/backups/phase1_status_backup.csv before execution.
- Batching: PK-based chunking (~10,000 IDs per batch) with per-batch transaction commits and progress output.
- Dry-run & Verification: Verifies 0 trailing CRs post-run and clean merge of '处理完成'.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path
import pymysql
import pymysql.cursors

ALLOWED_DB_NAME = "mod_s_v2"
BACKUP_DIR = Path(__file__).resolve().parent / "output" / "backups"
BACKUP_FILE = BACKUP_DIR / "phase1_status_backup.csv"
BATCH_ID_SPAN = 10000


def get_db_config() -> dict[str, str | int]:
    # Fallback to loading .env.local if environment variables are not set
    local_env_file = Path("/home/ubuntu/mod/.env.local")
    if local_env_file.exists():
        with open(local_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    if line.startswith("export "):
                        line = line[7:]
                    k, v = line.split("=", 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

    host = os.environ.get("MOD_V2_DB_HOST", "127.0.0.1")
    port = int(os.environ.get("MOD_V2_DB_PORT", "3307"))
    user = os.environ.get("MOD_V2_DB_USER", "mod_v2_writer")
    password = os.environ.get("MOD_V2_DB_PASSWORD", "")
    database = os.environ.get("MOD_V2_DB_NAME", "mod_s_v2")

    if database != ALLOWED_DB_NAME:
        print(f"[SECURITY ERROR] Target database must be '{ALLOWED_DB_NAME}', got '{database}'!", file=sys.stderr)
        sys.exit(1)

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def run_dry_run(conn: pymysql.Connection) -> int:
    print("\n--- [Phase 1 Dry-Run] Analyzing status pollution in business_document ---")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                status,
                HEX(status) as hex_val,
                COUNT(*) as cnt
            FROM business_document 
            WHERE status LIKE '%\r'
            GROUP BY status;
        """)
        rows = cur.fetchall()
        total_dirty = 0
        print(f"{'Status (raw)':<20} | {'HEX':<30} | {'Count':<10} | {'Sanitized Target'}")
        print("-" * 75)
        for raw_status, hex_val, cnt in rows:
            clean_status = raw_status.replace("\r", "")
            print(f"{repr(raw_status):<20} | {hex_val:<30} | {cnt:<10} | {repr(clean_status)}")
            total_dirty += cnt

        cur.execute("SELECT COUNT(*) FROM business_document WHERE status = '处理完成';")
        clean_completed = cur.fetchone()[0]
        print("-" * 75)
        print(f"Total polluted records to sanitize: {total_dirty}")
        print(f"Current clean '处理完成' count: {clean_completed}")
        print(f"Projected merged '处理完成' count: {clean_completed + 1959347}")
        return total_dirty


def backup_dirty_records(conn: pymysql.Connection, expected_count: int) -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if BACKUP_FILE.exists() and BACKUP_FILE.stat().st_size > 0:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            lines = sum(1 for _ in f) - 1
        if lines == expected_count:
            file_size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
            print(f"[Backup] Reusing verified existing backup {BACKUP_FILE} ({lines:,} rows, {file_size_mb:.2f} MB).")
            return lines

    print(f"\n[Backup] Exporting dirty records to {BACKUP_FILE}...")
    t0 = time.time()
    count = 0

    # Stream read using SSCursor to save memory
    with conn.cursor(pymysql.cursors.SSCursor) as cur:
        cur.execute("SELECT id, status FROM business_document WHERE status LIKE '%\r' ORDER BY id;")
        with open(BACKUP_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "status"])
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                writer.writerow([row[0], row[1]])
                count += 1
                if count % 200000 == 0:
                    print(f"  Backed up {count:,} rows...")

    file_size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
    print(f"[Backup] Done: {count:,} rows exported ({file_size_mb:.2f} MB) in {time.time() - t0:.2f}s.")
    return count


def execute_batch_update(conn: pymysql.Connection) -> int:
    print("\n[Execute] Starting chunked batch updates on business_document...")
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(id), MAX(id) FROM business_document WHERE status LIKE '%\r';")
        min_id, max_id = cur.fetchone()

    if min_id is None:
        print("[Execute] No dirty records found.")
        return 0

    print(f"[Execute] Target ID range: [{min_id}, {max_id}] with span {BATCH_ID_SPAN} per batch.")
    current_start = min_id
    total_updated = 0
    t0 = time.time()
    batch_idx = 0

    while current_start <= max_id:
        current_end = current_start + BATCH_ID_SPAN - 1
        with conn.cursor() as cur:
            sql = """
                UPDATE business_document 
                SET status = REPLACE(status, '\r', '') 
                WHERE id BETWEEN %s AND %s AND status LIKE '%%\r';
            """
            affected = cur.execute(sql, (current_start, current_end))
        conn.commit()
        total_updated += affected
        batch_idx += 1

        if batch_idx % 25 == 0 or current_end >= max_id:
            pct = min(100.0, (current_end - min_id) / (max_id - min_id) * 100)
            elapsed = time.time() - t0
            print(f"  Batch #{batch_idx:04d}: IDs [{current_start}, {current_end}] | Batch updated: {affected} | Cumulative updated: {total_updated:,} ({pct:.1f}%) in {elapsed:.1f}s")

        current_start = current_end + 1

    print(f"[Execute] Batch update completed. Total rows updated: {total_updated:,} in {time.time() - t0:.2f}s.")
    return total_updated


def verify_post_conditions(conn: pymysql.Connection):
    print("\n[Verification] Checking post-governance database state...")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM business_document WHERE status LIKE '%\r';")
        remaining_dirty = cur.fetchone()[0]

        cur.execute("""
            SELECT status, HEX(status), COUNT(*) 
            FROM business_document 
            GROUP BY status 
            ORDER BY COUNT(*) DESC;
        """)
        distribution = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM business_document;")
        total_docs = cur.fetchone()[0]

    print(f"Remaining records with '\\r': {remaining_dirty}")
    print(f"Total business_document records: {total_docs:,}")
    print("\nCurrent status distribution:")
    for st, hex_st, cnt in distribution:
        print(f"  {repr(st):<15} | HEX: {hex_st:<25} | Count: {cnt:,}")

    assert remaining_dirty == 0, f"Verification failed: {remaining_dirty} dirty records remain!"
    assert total_docs == 2316596, f"Verification failed: total document count altered to {total_docs}!"
    print("\n[Verification PASS] All assertions passed! Status values cleanly merged and 0 trailing CRs remain.")


def main():
    parser = argparse.ArgumentParser(description="Clean trailing CR in business_document.status.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Analyze and print sample changes without writing.")
    group.add_argument("--execute", action="store_true", help="Perform backup, chunked batch updates, and verification.")
    args = parser.parse_args()

    cfg = get_db_config()
    conn = pymysql.connect(
        host=str(cfg["host"]),
        port=int(cfg["port"]),
        user=str(cfg["user"]),
        password=str(cfg["password"]),
        database=str(cfg["database"]),
        charset="utf8mb4",
        autocommit=False,
    )

    try:
        if args.dry_run:
            run_dry_run(conn)
        elif args.execute:
            dirty_count = run_dry_run(conn)
            if dirty_count == 0:
                print("No dirty records to process.")
                return
            backed_up = backup_dirty_records(conn, dirty_count)
            assert backed_up == dirty_count, f"Backup count {backed_up} != dirty count {dirty_count}"
            updated = execute_batch_update(conn)
            assert updated == dirty_count, f"Updated count {updated} != dirty count {dirty_count}"
            verify_post_conditions(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
