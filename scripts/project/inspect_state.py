#!/usr/bin/env python3
"""
Derive the current project state facts from live sources (database + git).

Run when you need the real current numbers for CURRENT-STATE.md or a status report.
Reads env credentials only; never writes anything.

Usage:
    python3 scripts/project/inspect_state.py
    python3 scripts/project/inspect_state.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _db_conn():
    """Return a pymysql connection using env credentials. Fail clearly if missing."""
    try:
        import pymysql
    except ImportError:
        sys.exit("ERROR: pymysql not installed. Run: pip install pymysql")

    host = os.environ.get("MOD_DB_HOST", "")
    user = os.environ.get("MOD_DB_USER", "")
    password = os.environ.get("MOD_DB_PASSWORD", "")
    database = os.environ.get("MOD_DB_NAME", "mod")
    port = int(os.environ.get("MOD_DB_PORT", "3306"))

    if not (host and user and password):
        sys.exit(
            "ERROR: Set MOD_DB_HOST, MOD_DB_USER, MOD_DB_PASSWORD "
            "(source .env.local or .env.systemd first)"
        )
    return pymysql.connect(
        host=host, port=port, user=user, password=password,  # secret-scan: allow
        database=database, charset="utf8mb4", connect_timeout=5,
    )


def fetch_db_facts() -> dict:
    """Read key row counts and latest timestamps from the live database."""
    conn = _db_conn()
    facts: dict = {}
    try:
        cur = conn.cursor()

        rows = [
            ("business_document",       "SELECT COUNT(*), MAX(submit_time) FROM business_document"),
            ("accounting_voucher",      "SELECT COUNT(*), NULL FROM accounting_voucher"),
            ("org_unit",                "SELECT COUNT(*), NULL FROM org_unit"),
            ("sys_user",                "SELECT COUNT(*), NULL FROM sys_user"),
            ("construction_task",       "SELECT COUNT(*), MAX(update_time) FROM construction_task"),
            ("rollout_status_snapshot", "SELECT COUNT(*), MAX(snapshot_date) FROM rollout_status_snapshot"),
            ("training",                "SELECT COUNT(*), MAX(date) FROM training"),
            ("dual_run_result",         "SELECT COUNT(*), MAX(check_date) FROM dual_run_result"),
        ]
        for name, sql in rows:
            cur.execute(sql)
            row = cur.fetchone()
            facts[name] = {"count": row[0], "latest": str(row[1]) if row[1] else None}

        # Org unit stage distribution
        cur.execute("SELECT status, COUNT(*) FROM org_unit GROUP BY status ORDER BY COUNT(*) DESC")
        facts["org_unit_stages"] = {r[0]: r[1] for r in cur.fetchall()}

        # Database name
        cur.execute("SELECT DATABASE()")
        facts["database"] = cur.fetchone()[0]

        # KI-017 health check
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM business_document bd
                 LEFT JOIN sys_user su ON su.org_id=bd.org_id AND su.name=bd.applicant
                 WHERE su.name IS NULL) AS applicant_miss,
                (SELECT COUNT(*) FROM business_document WHERE approve_time < submit_time) AS time_inv,
                (SELECT COUNT(*) FROM accounting_voucher av
                 LEFT JOIN document_voucher_link dvl ON dvl.voucher_id=av.id
                 WHERE dvl.voucher_id IS NULL) AS orphan_v
        """)
        h = cur.fetchone()
        facts["ki017_health"] = {
            "applicant_miss": h[0],
            "time_inversions": h[1],
            "orphan_vouchers": h[2],
            "status": "OK" if h[0] == 0 and h[1] == 0 and h[2] == 0 else "FAIL",
        }

    finally:
        conn.close()
    return facts


def fetch_git_facts() -> dict:
    """Read test count and last commit from git/codebase."""
    facts: dict = {}
    try:
        result = subprocess.run(
            ["backend/.venv/bin/python", "-m", "pytest", "--collect-only", "-q", "--no-header"],
            cwd=ROOT / "backend", capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().splitlines()
        # last line is typically "N tests collected"
        for line in reversed(lines):
            if "test" in line and ("selected" in line or "collected" in line):
                facts["test_count"] = line.strip()
                break
    except Exception:
        facts["test_count"] = "(unavailable)"

    try:
        commit = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%ai)"],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.strip()
        facts["last_commit"] = commit
    except Exception:
        facts["last_commit"] = "(unavailable)"

    return facts


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive live project state facts (read-only)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    db = fetch_db_facts()
    git = fetch_git_facts()

    all_facts = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": db,
        "codebase": git,
    }

    if args.json:
        print(json.dumps(all_facts, ensure_ascii=False, indent=2, default=str))
        return

    print("=" * 60)
    print(f"  MOD Project State — {all_facts['generated_at']}")
    print("=" * 60)
    print(f"\n[Database: {db.get('database')}]")
    for table, v in db.items():
        if table in ("database", "ki017_health", "org_unit_stages"):
            continue
        count = v["count"]
        latest = v["latest"] or "—"
        print(f"  {table:<30} {count:>10,}   latest: {latest}")

    print(f"\n[Org Unit Stages]")
    for stage, cnt in db.get("org_unit_stages", {}).items():
        print(f"  {stage:<20} {cnt:>6}")

    h = db.get("ki017_health", {})
    print(f"\n[KI-017 Health]  {h.get('status','?')}")
    print(f"  applicant_miss={h.get('applicant_miss')}  "
          f"time_inv={h.get('time_inversions')}  "
          f"orphan_v={h.get('orphan_vouchers')}")

    print(f"\n[Codebase]")
    print(f"  tests:       {git.get('test_count')}")
    print(f"  last commit: {git.get('last_commit')}")
    print()


if __name__ == "__main__":
    main()
