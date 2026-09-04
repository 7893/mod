#!/usr/bin/env python3
"""
Phase 3 Data Governance: Delete Orphan Accounting Vouchers and Related Records.

Requirements:
- 11,144 accounting_voucher records have no document_voucher_link to any business_document.
- Delete these orphan vouchers and their child records:
  - integration_result (10,556 records referencing orphan vouchers)
  - accounting_voucher_line (0 records, but checked defensively)
  - accounting_voucher (11,144 records)
- Acceptance criteria:
  - Orphan vouchers count == 0.
  - No broken foreign keys or orphaned child records.
  - Full local backups created before deletion.
  - Batching: Chunked deletion (1,000 IDs per batch) committed per batch.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path
import pymysql

ALLOWED_DB_NAME = "mod_s_v2"
BACKUP_DIR = Path(__file__).resolve().parent / "output" / "backups"
BACKUP_VOUCHERS_FILE = BACKUP_DIR / "phase3_orphan_vouchers_backup.csv"
BACKUP_INTEG_FILE = BACKUP_DIR / "phase3_orphan_integration_backup.csv"
BATCH_SIZE = 1000


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


def find_orphan_voucher_ids(conn: pymysql.Connection) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT av.id
            FROM accounting_voucher av
            LEFT JOIN document_voucher_link dvl ON av.id = dvl.voucher_id
            WHERE dvl.voucher_id IS NULL
            ORDER BY av.id;
        """)
        return [row[0] for row in cur.fetchall()]


def run_dry_run(conn: pymysql.Connection) -> tuple[list[int], int, int]:
    print("\n--- [Phase 3 Dry-Run] Analyzing orphan vouchers and children ---")
    orphan_ids = find_orphan_voucher_ids(conn)
    total_orphans = len(orphan_ids)

    if not orphan_ids:
        print("No orphan vouchers found.")
        return [], 0, 0

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) 
            FROM integration_result ir
            JOIN accounting_voucher av ON ir.voucher_id = av.id
            LEFT JOIN document_voucher_link dvl ON av.id = dvl.voucher_id
            WHERE dvl.voucher_id IS NULL;
        """)
        orphan_integ = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) 
            FROM accounting_voucher_line avl
            JOIN accounting_voucher av ON avl.voucher_id = av.id
            LEFT JOIN document_voucher_link dvl ON av.id = dvl.voucher_id
            WHERE dvl.voucher_id IS NULL;
        """)
        orphan_lines = cur.fetchone()[0]

        cur.execute(f"""
            SELECT id, org_id, voucher_no, type, gen_time, status, debit, credit
            FROM accounting_voucher
            WHERE id IN ({','.join(str(i) for i in orphan_ids[:5])});
        """)
        sample_vouchers = cur.fetchall()

    print(f"Total orphan accounting_voucher records : {total_orphans:,}")
    print(f"Related integration_result records     : {orphan_integ:,}")
    print(f"Related accounting_voucher_line records: {orphan_lines:,}")
    print("\nSample orphan vouchers to be deleted:")
    for v in sample_vouchers:
        print(f"  ID {v[0]}: Org {v[1]} | No {v[2]} | Type {v[3]} | Gen {v[4]} | Status {v[5]} | Debit {v[6]}")

    return orphan_ids, orphan_integ, orphan_lines


def backup_records(conn: pymysql.Connection, orphan_ids: list[int]):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print("\n[Backup] Exporting orphan vouchers and child records to local files...")
    t0 = time.time()

    # 1. Backup orphan accounting_voucher
    with conn.cursor() as cur:
        # Fetch columns
        cur.execute("SHOW COLUMNS FROM accounting_voucher;")
        v_cols = [r[0] for r in cur.fetchall()]

        # Query and write in batches
        with open(BACKUP_VOUCHERS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(v_cols)
            for i in range(0, len(orphan_ids), BATCH_SIZE):
                chunk = orphan_ids[i:i + BATCH_SIZE]
                placeholders = ",".join(["%s"] * len(chunk))
                cur.execute(f"SELECT * FROM accounting_voucher WHERE id IN ({placeholders})", chunk)
                for row in cur.fetchall():
                    writer.writerow(list(row))

    v_size_mb = BACKUP_VOUCHERS_FILE.stat().st_size / (1024 * 1024)
    print(f"  Backed up {len(orphan_ids):,} vouchers to {BACKUP_VOUCHERS_FILE} ({v_size_mb:.2f} MB)")

    # 2. Backup orphan integration_result
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM integration_result;")
        ir_cols = [r[0] for r in cur.fetchall()]

        integ_backed = 0
        with open(BACKUP_INTEG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(ir_cols)
            for i in range(0, len(orphan_ids), BATCH_SIZE):
                chunk = orphan_ids[i:i + BATCH_SIZE]
                placeholders = ",".join(["%s"] * len(chunk))
                cur.execute(f"SELECT * FROM integration_result WHERE voucher_id IN ({placeholders})", chunk)
                rows = cur.fetchall()
                for row in rows:
                    writer.writerow(list(row))
                integ_backed += len(rows)

    ir_size_mb = BACKUP_INTEG_FILE.stat().st_size / (1024 * 1024)
    print(f"  Backed up {integ_backed:,} integration results to {BACKUP_INTEG_FILE} ({ir_size_mb:.2f} MB)")
    print(f"[Backup] Completed in {time.time() - t0:.2f}s.")


def execute_batch_delete(conn: pymysql.Connection, orphan_ids: list[int]):
    print(f"\n[Execute] Starting batch deletion of {len(orphan_ids):,} orphan vouchers in chunks of {BATCH_SIZE}...")
    t0 = time.time()
    total_integ_deleted = 0
    total_vouchers_deleted = 0
    total_lines_deleted = 0

    for i in range(0, len(orphan_ids), BATCH_SIZE):
        chunk = orphan_ids[i:i + BATCH_SIZE]
        placeholders = ",".join(["%s"] * len(chunk))

        with conn.cursor() as cur:
            # 1. Delete child: integration_result
            d_ir = cur.execute(f"DELETE FROM integration_result WHERE voucher_id IN ({placeholders})", chunk)
            total_integ_deleted += d_ir

            # 2. Delete child: accounting_voucher_line
            d_avl = cur.execute(f"DELETE FROM accounting_voucher_line WHERE voucher_id IN ({placeholders})", chunk)
            total_lines_deleted += d_avl

            # 3. Delete parent: accounting_voucher
            d_v = cur.execute(f"DELETE FROM accounting_voucher WHERE id IN ({placeholders})", chunk)
            total_vouchers_deleted += d_v

        conn.commit()

        pct = min(100.0, (i + len(chunk)) / len(orphan_ids) * 100)
        print(f"  Batch #{i // BATCH_SIZE + 1:02d}: Vouchers deleted: {d_v} | Integration deleted: {d_ir} | Cumulative: {total_vouchers_deleted:,} ({pct:.1f}%) in {time.time() - t0:.2f}s")

    print(f"[Execute] Deletion finished in {time.time() - t0:.2f}s.")
    print(f"  Total accounting_voucher deleted: {total_vouchers_deleted:,}")
    print(f"  Total integration_result deleted: {total_integ_deleted:,}")
    print(f"  Total accounting_voucher_line deleted: {total_lines_deleted:,}")


def verify_post_conditions(conn: pymysql.Connection):
    print("\n[Verification] Checking post-deletion database state & foreign key consistency...")
    with conn.cursor() as cur:
        # Check orphan count
        cur.execute("""
            SELECT COUNT(*)
            FROM accounting_voucher av
            LEFT JOIN document_voucher_link dvl ON av.id = dvl.voucher_id
            WHERE dvl.voucher_id IS NULL;
        """)
        remaining_orphans = cur.fetchone()[0]

        # Check total remaining counts
        cur.execute("SELECT COUNT(*) FROM accounting_voucher;")
        total_v = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM integration_result;")
        total_ir = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounting_voucher_line;")
        total_avl = cur.fetchone()[0]

        # Check foreign key consistency (0 broken references)
        cur.execute("""
            SELECT COUNT(*) 
            FROM integration_result ir 
            LEFT JOIN accounting_voucher av ON ir.voucher_id = av.id 
            WHERE av.id IS NULL;
        """)
        broken_ir = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) 
            FROM accounting_voucher_line avl 
            LEFT JOIN accounting_voucher av ON avl.voucher_id = av.id 
            WHERE av.id IS NULL;
        """)
        broken_avl = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) 
            FROM document_voucher_link dvl 
            LEFT JOIN accounting_voucher av ON dvl.voucher_id = av.id 
            WHERE av.id IS NULL;
        """)
        broken_dvl = cur.fetchone()[0]

    print(f"Remaining orphan vouchers                  : {remaining_orphans}")
    print(f"Remaining total accounting_voucher         : {total_v:,} (expected 1,469,547)")
    print(f"Remaining total integration_result         : {total_ir:,} (expected 1,382,379)")
    print(f"Remaining total accounting_voucher_line    : {total_avl:,} (expected 2,939,094)")
    print(f"Broken FKs in integration_result           : {broken_ir}")
    print(f"Broken FKs in accounting_voucher_line      : {broken_avl}")
    print(f"Broken FKs in document_voucher_link        : {broken_dvl}")

    assert remaining_orphans == 0, f"Verification failed: {remaining_orphans} orphan vouchers remain!"
    assert total_v == 1469547, f"Verification failed: total vouchers {total_v} != 1,469,547!"
    assert total_ir == 1382379, f"Verification failed: total integration {total_ir} != 1,382,379!"
    assert total_avl == 2939094, f"Verification failed: total lines {total_avl} != 2,939,094!"
    assert broken_ir == 0 and broken_avl == 0 and broken_dvl == 0, "Verification failed: broken foreign keys detected!"

    print("\n[Verification PASS] All assertions passed! 0 orphan vouchers, 0 broken foreign keys.")


def main():
    parser = argparse.ArgumentParser(description="Delete orphan accounting vouchers and child records.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Analyze and print sample changes without deleting.")
    group.add_argument("--execute", action="store_true", help="Perform backup, chunked batch deletion, and verification.")
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
            orphan_ids, expected_ir, _ = run_dry_run(conn)
            if not orphan_ids:
                print("No orphan vouchers to delete.")
                return
            assert len(orphan_ids) == 11144, f"Unexpected orphan voucher count: {len(orphan_ids)}"
            assert expected_ir == 10556, f"Unexpected orphan integration_result count: {expected_ir}"
            backup_records(conn, orphan_ids)
            execute_batch_delete(conn, orphan_ids)
            verify_post_conditions(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
