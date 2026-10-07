#!/usr/bin/env python3
"""Container-only demo initializer/launcher. Owner: project.

Uses explicit Compose demo credentials; initializes only the named demo service.
Init writes the isolated demo DB in batches. API launches with read-only sessions.
Never loads host env files or production settings; failures never drop objects.
"""
import os
from pathlib import Path
import sys

from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]


def target_url():
    password = os.environ.get('MOD_DEMO_DB_PASSWORD')
    if not password:
        raise ValueError('MOD_DEMO_DB_PASSWORD must be provided')
    # These are private Compose service identifiers, not deployment addresses.
    return URL.create('mysql+pymysql', username='mod_demo', password=password,
                      host='demo-db', database='mod_demo', query={'charset': 'utf8mb4'}).render_as_string(hide_password=False)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {'init', 'serve'}:
        raise ValueError('Choose init or serve explicitly')
    target = target_url()
    if sys.argv[1] == 'init':
        from demo_data.importer import initialize
        print(initialize(ROOT / 'demo-data', target, apply=True, allow_remote=True, bulk_load=True))
        return
    os.environ.update(MOD_DEMO_MODE='true', MOD_DEMO_DATABASE_URL=target,
                      MOD_SIMULATION_ENGINE_ENABLED='false', MOD_CF_AI_ENABLED='false',
                      MOD_HW_ENABLED='false', MOD_HW_ML_ENABLED='false',
                      MOD_LIVE_PROJECTION_ENABLED='false', MOD_STARTUP_DB_PROBE_ENABLED='false')
    os.execvp('sh', ['sh', '-c', 'nginx && exec backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8100'])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Demo container failed: {type(exc).__name__}', file=sys.stderr)
        sys.exit(1)
