"""Transactional outbox writes on the simulator's existing DB-API transaction.

No DDL, commits, rollback, filesystem writes or independent connections here.
Lock the singleton until the caller commits: sequence order equals commit order.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

MAX_RETAINED_EVENTS = 150_000
RETENTION_DAYS = 30
PRUNE_BATCH_SIZE = 1000


def append_outbox(conn, records: list[dict], *, now: datetime | None = None) -> None:
    if not records:
        return
    if len(records) > PRUNE_BATCH_SIZE:
        raise ValueError("Outbox transaction batch exceeds retention work bound")
    if conn.get_autocommit():
        raise ValueError("Outbox requires the caller's explicit transaction")
    created_at = (now or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    with conn.cursor() as cur:
        cur.execute("SELECT last_sequence, pruned_through, documents, vouchers, integrations "
                    "FROM sim_event_outbox_state WHERE singleton_id = 1 FOR UPDATE")
        state = cur.fetchone()
        if state is None:
            raise RuntimeError("Outbox schema/state not provisioned")
        sequence, floor, documents, vouchers, integrations = map(int, state)
        for record in records:
            inc = record['increments']
            deltas = [inc[k] for k in ('documents', 'vouchers', 'integrations')]
            if any(type(v) is not int or v < 0 for v in deltas):
                raise ValueError("Invalid outbox increments")
            sequence += 1
            documents += deltas[0]
            vouchers += deltas[1]
            integrations += deltas[2]
            # Duplicate IDs and malformed records must fail the entire business transaction.
            cur.execute(
                "INSERT INTO sim_event_outbox "
                "(sequence, event_id, payload, created_at, documents, vouchers, integrations) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (sequence, record['event_id'], json.dumps(record, ensure_ascii=False, allow_nan=False),
                 created_at, documents, vouchers, integrations),
            )
        # Prune only a contiguous old prefix. A slow client sees an explicit floor/reset.
        cur.execute("SELECT sequence, created_at FROM sim_event_outbox "
                    "ORDER BY sequence LIMIT %s", (PRUNE_BATCH_SIZE,))
        cutoff = created_at - timedelta(days=RETENTION_DAYS)
        for old_sequence, old_at in cur.fetchall():
            if isinstance(old_at, str):
                old_at = datetime.fromisoformat(old_at)
            if old_at >= cutoff and old_sequence > sequence - MAX_RETAINED_EVENTS:
                break
            floor = old_sequence
        if floor > state[1]:
            cur.execute("DELETE FROM sim_event_outbox WHERE sequence <= %s", (floor,))
        cur.execute("UPDATE sim_event_outbox_state SET last_sequence=%s, pruned_through=%s, "
                    "documents=%s, vouchers=%s, integrations=%s WHERE singleton_id=1",
                    (sequence, floor, documents, vouchers, integrations))
