#!/usr/bin/env python3
"""
scripts/project/add_dual_run_result_index.py

KI-085 #5: Add missing index on dual_run_result.check_date to eliminate
full table scans during dashboard snapshot aggregation queries.

Usage:
    python scripts/project/add_dual_run_result_index.py [--dry-run]

The index enables covering scan for the frequent aggregation:
    SELECT check_type, result, COUNT(*) FROM dual_run_result
    WHERE check_date <= :anchor_date GROUP BY check_type, result
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pymysql
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]

INDEX_NAME = "idx_check_date_type_result"
TABLE_NAME = "dual_run_result"
INDEX_COLUMNS = "(check_date, check_type, result)"


def get_connection() -> pymysql.connections.Connection:
    """Get database connection from environment."""
    env_file = REPO_ROOT / ".env.systemd"
    cfg: dict[str, str | None] = {}
    if env_file.exists():
        cfg = dotenv_values(str(env_file))

    host = os.getenv("MOD_DB_HOST") or cfg.get("MOD_DB_HOST", "127.0.0.1")
    port = int(os.getenv("MOD_DB_PORT") or cfg.get("MOD_DB_PORT", "3306"))
    user = os.getenv("MOD_DB_USER") or cfg.get("MOD_DB_USER", "root")
    password = os.getenv("MOD_DB_PASSWORD") or cfg.get("MOD_DB_PASSWORD", "")
    database = os.getenv("MOD_DB_NAME") or cfg.get("MOD_DB_NAME", "mod")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,  # secret-scan: allow
        database=database,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def index_exists(conn: pymysql.connections.Connection) -> bool:
    """Check if the index already exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
            (TABLE_NAME, INDEX_NAME),
        )
        row = cur.fetchone()
        return row and row["cnt"] > 0


def create_index(conn: pymysql.connections.Connection, dry_run: bool = False) -> bool:
    """Create the index if it doesn't exist."""
    if index_exists(conn):
        print(f"✓ Index {INDEX_NAME} already exists on {TABLE_NAME}")
        return True

    ddl = f"ALTER TABLE {TABLE_NAME} ADD INDEX {INDEX_NAME} {INDEX_COLUMNS}"
    print(f"Creating index: {ddl}")

    if dry_run:
        print("  [DRY RUN] Skipping actual execution")
        return True

    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        print(f"✓ Successfully created index {INDEX_NAME}")
        return True
    except pymysql.Error as e:
        print(f"✗ Failed to create index: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Add dual_run_result index migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    args = parser.parse_args()

    print("=" * 60)
    print("KI-085 #5: dual_run_result index migration")
    print("=" * 60)

    try:
        conn = get_connection()
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return 1

    try:
        success = create_index(conn, dry_run=args.dry_run)
        return 0 if success else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
