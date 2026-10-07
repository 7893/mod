#!/usr/bin/env python3
import sys
import os
import json
from contextlib import contextmanager
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env.systemd")
load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env")

from sqlalchemy import text, create_engine
from app.db import get_engine
from app.config import get_settings


@contextmanager
def read_only_connection(timeout_ms=3000):
    """Shared source reader. All export SELECTs run in one read-only snapshot."""
    base_engine = get_engine()
    engine = create_engine(base_engine.url, pool_pre_ping=True,
                           connect_args={"connect_timeout": 3, "read_timeout": 60})
    readonly_user = os.environ.get("MOD_DB_READONLY_USER")
    readonly_pass = os.environ.get("MOD_DB_READONLY_PASSWORD")
    if readonly_user and readonly_pass:
        engine = create_engine(engine.url.set(username=readonly_user, password=readonly_pass),
                               pool_pre_ping=True, connect_args={"connect_timeout": 3, "read_timeout": 60})
    with engine.connect() as conn:
        conn.execute(text("SET time_zone = '+00:00'"))
        conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        conn.execute(text(f"SET SESSION max_execution_time = {int(timeout_ms)}"))
        conn.execute(text("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY"))
        try:
            yield conn
        finally:
            conn.rollback()

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "Missing SQL query"}))
        sys.exit(1)
    
    sql = sys.argv[1].strip()
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    first_word = sql.split()[0].upper() if sql else ""
    if first_word not in ("SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN"):
        print(json.dumps({"success": False, "error": "Only read-only queries (SELECT/SHOW/DESC/EXPLAIN) are permitted"}))
        sys.exit(1)
        
    try:
        settings = get_settings()
        engine = get_engine()
        
        # Switch to mod_readonly user if available
        readonly_user = os.environ.get("MOD_DB_READONLY_USER")
        readonly_pass = os.environ.get("MOD_DB_READONLY_PASSWORD")
        if readonly_user and readonly_pass:
            url = engine.url.set(username=readonly_user, password=readonly_pass)  # secret-scan: allow
            engine = create_engine(url, **{k: v for k, v in engine.engine.__dict__.items() if k in ["pool_pre_ping", "pool_recycle", "pool_size", "max_overflow", "connect_args"]}) # Simple fallback, actually maybe just create new engine
            # Better to just set the url:
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3, "read_timeout": 60})

        with engine.connect() as conn:
            # Enforce read-only at the session level
            conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            # Limit execution resources
            conn.execute(text("SET SESSION max_execution_time = 3000"))
            
            res = conn.execute(text(sql))
            rows = [dict(r) for r in res.mappings().fetchmany(limit)]
            print(json.dumps({"success": True, "count": len(rows), "rows": rows}, default=str))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    main()
