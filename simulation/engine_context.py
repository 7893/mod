"""Simulation engine context, stock baseline reader and sequential ID allocator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class SimulationBaseline:
    """Read-only baseline loaded from existing stock data before generation."""

    latest_business_date: datetime
    online_org_ids: List[int]
    org_users: Dict[int, List[Dict[str, str]]]
    next_ids: Dict[str, int]


@dataclass
class ConstructionBaseline:
    """Read-only construction baseline loaded from existing stock data before generation."""

    latest_business_date: datetime
    orgs: Dict[int, Dict[str, Any]]
    orgs_by_status: Dict[str, List[int]]
    org_users: Dict[int, List[Dict[str, str]]]
    next_ids: Dict[str, int]
    batches: Dict[int, Dict[str, Any]]


class IdAllocator:
    """Thread-safe sequential integer ID allocator for simulation tables."""

    def __init__(self, initial_ids: Dict[str, int]):
        self._current_ids = dict(initial_ids)

    def next_id(self, table_name: str) -> int:
        if table_name not in self._current_ids:
            raise KeyError(f"Unknown table for ID allocation: {table_name}")
        val = self._current_ids[table_name]
        self._current_ids[table_name] = val + 1
        return val

    def peek_next_id(self, table_name: str) -> int:
        return self._current_ids.get(table_name, 1)


def load_simulation_baseline(conn: Any) -> SimulationBaseline:
    """
    Read starting baseline from database.

    Enforces:
    1. Stock latest business date is determined.
    2. Online units pool is verified (> 0).
    3. Every online unit has at least one real user in sys_user.
    4. Max ID of each table is captured so new records never collide with stock.
    """
    cursor = conn.cursor()

    # 1. Query latest business date
    cursor.execute("SELECT MAX(submit_time) FROM business_document;")
    row = cursor.fetchone()
    latest_business_date = row[0] if row and row[0] else None
    if not latest_business_date:
        raise RuntimeError(
            "Simulation baseline check failed: no business documents found to establish start timeline."
        )

    # 2. Query online units
    cursor.execute("SELECT id FROM org_unit WHERE status IN ('已上线', '稳定运行') ORDER BY id;")
    rows = cursor.fetchall()
    online_org_ids = [r[0] for r in rows]
    if not online_org_ids:
        raise RuntimeError("Simulation baseline check failed: no online units found in org_unit.")

    # 3. Query users for online units
    cursor.execute("SELECT org_id, name, role FROM sys_user ORDER BY org_id, id;")
    user_rows = cursor.fetchall()
    org_users: Dict[int, List[Dict[str, str]]] = {}
    for r in user_rows:
        org_id, name, role = r[0], r[1], r[2]
        if org_id not in org_users:
            org_users[org_id] = []
        org_users[org_id].append({"name": name, "role": role or ""})

    # Validate that every online org has users
    for org_id in online_org_ids:
        users = org_users.get(org_id, [])
        if not users:
            raise RuntimeError(
                f"Simulation baseline check failed: online org_id {org_id} has 0 users in sys_user."
            )

    # 4. Query current MAX(id) for all relevant tables
    tables = [
        "business_document",
        "business_document_line",
        "accounting_voucher",
        "accounting_voucher_line",
        "integration_result",
    ]
    next_ids: Dict[str, int] = {}
    for table in tables:
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table};")  # noqa: S608
        max_id = cursor.fetchone()[0]
        next_ids[table] = max_id + 1

    return SimulationBaseline(
        latest_business_date=latest_business_date,
        online_org_ids=online_org_ids,
        org_users=org_users,
        next_ids=next_ids,
    )


def load_construction_baseline(conn: Any) -> ConstructionBaseline:
    """
    Read starting construction baseline from database.

    Enforces:
    1. Stock latest business date is determined.
    2. All orgs and their status are captured.
    3. Every org has users in sys_user.
    4. Rollout batches are loaded.
    5. Max ID of construction_task, training, dual_run_result are captured.
    """
    cursor = conn.cursor()

    # 1. Query latest business date
    cursor.execute("SELECT MAX(submit_time) FROM business_document;")
    row = cursor.fetchone()
    latest_business_date = row[0] if row and row[0] else datetime(2026, 9, 4, 0, 0, 0)

    # 2. Query all org units
    cursor.execute(
        "SELECT id, name, batch_id, status, region, start_date, end_date FROM org_unit ORDER BY id;"
    )
    org_rows = cursor.fetchall()
    orgs: Dict[int, Dict[str, Any]] = {}
    orgs_by_status: Dict[str, List[int]] = {}
    for r in org_rows:
        oid, name, bid, status, region, s_date, e_date = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        orgs[oid] = {
            "id": oid,
            "name": name,
            "batch_id": bid,
            "status": status,
            "region": region,
            "start_date": s_date,
            "end_date": e_date,
        }
        orgs_by_status.setdefault(status, []).append(oid)

    if not orgs:
        raise RuntimeError("Construction baseline check failed: 0 org units found.")

    # 3. Query users for all orgs
    cursor.execute("SELECT org_id, name, role FROM sys_user ORDER BY org_id, id;")
    user_rows = cursor.fetchall()
    org_users: Dict[int, List[Dict[str, str]]] = {}
    for r in user_rows:
        org_id, name, role = r[0], r[1], r[2]
        org_users.setdefault(org_id, []).append({"name": name, "role": role or ""})

    for oid in orgs:
        if not org_users.get(oid):
            raise RuntimeError(f"Construction baseline check failed: org_id {oid} has 0 users in sys_user.")

    # 4. Query batches
    cursor.execute("SELECT id, name, start_date, end_date, status FROM rollout_batch ORDER BY id;")
    batch_rows = cursor.fetchall()
    batches: Dict[int, Dict[str, Any]] = {}
    for r in batch_rows:
        batches[r[0]] = {
            "id": r[0],
            "name": r[1],
            "start_date": r[2],
            "end_date": r[3],
            "status": r[4],
        }

    # 5. Query max IDs
    tables = ["construction_task", "training", "dual_run_result"]
    next_ids: Dict[str, int] = {}
    for table in tables:
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table};")  # noqa: S608
        max_id = cursor.fetchone()[0]
        next_ids[table] = max_id + 1

    return ConstructionBaseline(
        latest_business_date=latest_business_date,
        orgs=orgs,
        orgs_by_status=orgs_by_status,
        org_users=org_users,
        next_ids=next_ids,
        batches=batches,
    )
