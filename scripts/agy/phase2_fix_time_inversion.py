#!/usr/bin/env python3
"""
Phase 2 Data Governance: Fix inverted approve_time in business_document.

Requirements:
- About 344,898 records have approve_time < submit_time (or '0000-00-00 00:00:00').
- Fix approve_time to: submit_time + random 1~72 hours.
- Acceptance criteria: COUNT(approve_time < submit_time) == 0.
- Safety: Strictly target mod_s_v2, non-admin credentials from env, export backup before modification,
  batch updates commit per chunk, and verify post-conditions.
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
BACKUP_FILE = BACKUP_DIR / "phase2_inverted_time_backup.csv"
BATCH_ID_SPAN = 10000


def get_db_config() -> dict[str, str | int]:
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
    print("\n--- [Phase 2 Dry-Run] Analyzing inverted approve_time in business_document ---")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status, COUNT(*) 
            FROM business_document 
            WHERE approve_time IS NOT NULL AND approve_time < submit_time
            GROUP BY status;
        """)
        breakdown = cur.fetchall()
        total_inverted = sum(cnt for _, cnt in breakdown)

        print(f"{'Status':<15} | {'Inverted Count':<15}")
        print("-" * 35)
        for st, cnt in breakdown:
            print(f"{st:<15} | {cnt:<15,}")
        print("-" * 35)
        print(f"Total inverted records: {total_inverted:,}")

        cur.execute("""
            SELECT 
                id, submit_time, approve_time,
                DATE_ADD(submit_time, INTERVAL (3600 + FLOOR(RAND() * 255600)) SECOND) as sample_new_approve
            FROM business_document 
            WHERE approve_time IS NOT NULL AND approve_time < submit_time
            LIMIT 5;
        """)
        print("\nSample adjustments (submit_time -> sample_new_approve):")
        for row in cur.fetchall():
            print(f"  ID {row[0]:<7}: Submit {row[1]} | Old Approve {repr(row[2])} -> New Approve {row[3]}")

        return total_inverted


def backup_dirty_records(conn: pymysql.Connection, expected_count: int) -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if BACKUP_FILE.exists() and BACKUP_FILE.stat().st_size > 0:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            lines = sum(1 for _ in f) - 1
        if lines == expected_count:
            file_size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
            print(f"[Backup] Reusing verified existing backup {BACKUP_FILE} ({lines:,} rows, {file_size_mb:.2f} MB).")
            return lines

    print(f"\n[Backup] Exporting inverted time records to {BACKUP_FILE}...")
    t0 = time.time()
    count = 0

    with conn.cursor(pymysql.cursors.SSCursor) as cur:
        cur.execute("""
            SELECT id, submit_time, approve_time 
            FROM business_document 
            WHERE approve_time IS NOT NULL AND approve_time < submit_time
            ORDER BY id;
        """)
        with open(BACKUP_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "submit_time", "approve_time"])
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                writer.writerow([row[0], str(row[1]), str(row[2])])
                count += 1
                if count % 100000 == 0:
                    print(f"  Backed up {count:,} rows...")

    file_size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
    print(f"[Backup] Done: {count:,} rows exported ({file_size_mb:.2f} MB) in {time.time() - t0:.2f}s.")
    return count


def execute_batch_update(conn: pymysql.Connection) -> int:
    print("\n[Execute] Starting chunked batch updates on business_document...")
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(id), MAX(id) FROM business_document WHERE approve_time IS NOT NULL AND approve_time < submit_time;")
        min_id, max_id = cur.fetchone()

    if min_id is None:
        print("[Execute] No inverted records found.")
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
                SET approve_time = DATE_ADD(submit_time, INTERVAL (3600 + FLOOR(RAND() * 255600)) SECOND)
                WHERE id BETWEEN %s AND %s 
                  AND approve_time IS NOT NULL 
                  AND approve_time < submit_time;
            """
            affected = cur.execute(sql, (current_start, current_end))
        conn.commit()
        total_updated += affected
        batch_idx += 1

        if batch_idx % 25 == 0 or current_end >= max_id:
            pct = min(100.0, (current_end - min_id) / (max_id - min_id) * 100)
            elapsed = time.time() - t0
            print(f"  Batch #{batch_idx:04d}: IDs [{current_start}, {current_end}] | Updated: {affected} | Cumulative: {total_updated:,} ({pct:.1f}%) in {elapsed:.1f}s")

        current_start = current_end + 1

    print(f"[Execute] Batch update completed. Total rows updated: {total_updated:,} in {time.time() - t0:.2f}s.")
    return total_updated


def verify_post_conditions(conn: pymysql.Connection):
    print("\n[Verification] Checking post-governance database state...")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM business_document WHERE approve_time IS NOT NULL AND approve_time < submit_time;")
        remaining_inverted = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM business_document;")
        total_docs = cur.fetchone()[0]

        cur.execute("""
            SELECT 
                MIN(TIMESTAMPDIFF(HOUR, submit_time, approve_time)) as min_diff_h,
                MAX(TIMESTAMPDIFF(HOUR, submit_time, approve_time)) as max_diff_h,
                AVG(TIMESTAMPDIFF(HOUR, submit_time, approve_time)) as avg_diff_h
            FROM business_document 
            WHERE approve_time IS NOT NULL;
        """)
        diff_stats = cur.fetchone()

    print(f"Remaining records with approve_time < submit_time: {remaining_inverted}")
    print(f"Total business_document records: {total_docs:,}")
    print(f"Overall approval time diff (hours): Min={diff_stats[0]}, Max={diff_stats[1]}, Avg={diff_stats[2]:.2f}")

    assert remaining_inverted == 0, f"Verification failed: {remaining_inverted} inverted records remain!"
    assert total_docs == 2316596, f"Verification failed: total document count altered to {total_docs}!"
    print("\n[Verification PASS] All assertions passed! 0 inverted timestamps remain.")


def main():
    parser = argparse.ArgumentParser(description="Fix inverted approve_time in business_document.")
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
                print("No inverted records to process.")
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
