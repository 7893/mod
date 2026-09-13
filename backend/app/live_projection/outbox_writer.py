"""Transactional outbox writes on the simulator's existing DB-API transaction.

No DDL, commits, rollback, filesystem writes or independent connections here.
Lock the singleton until the caller commits: sequence order equals commit order.

KI-085 #3: Prune logic is decoupled from the hot write path. The append_outbox
function now only writes new events and updates state; pruning is deferred to
a separate prune_outbox_async() call that should run outside the critical path.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

MAX_RETAINED_EVENTS = 150_000
RETENTION_DAYS = 30
PRUNE_BATCH_SIZE = 1000

# Module-level deferred prune state: accumulates prune floor to be applied async
_deferred_prune_floor: int | None = None
_deferred_prune_cutoff: datetime | None = None


def append_outbox(conn, records: list[dict], *, now: datetime | None = None) -> None:
    """Append events to outbox within caller's transaction. Prune is deferred."""
    global _deferred_prune_floor, _deferred_prune_cutoff

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

        # Update state with new sequence (no prune in hot path)
        cur.execute("UPDATE sim_event_outbox_state SET last_sequence=%s, "
                    "documents=%s, vouchers=%s, integrations=%s WHERE singleton_id=1",
                    (sequence, documents, vouchers, integrations))

        # Schedule deferred prune check (will be executed outside this transaction)
        _deferred_prune_floor = sequence - MAX_RETAINED_EVENTS
        _deferred_prune_cutoff = created_at - timedelta(days=RETENTION_DAYS)


def prune_outbox_deferred(conn, *, auto_commit: bool = False) -> int:
    """Execute deferred outbox pruning outside the critical transaction path.

    Call this after the main business transaction commits, ideally in a
    background thread or at the end of a cycle. Returns count of pruned rows.

    KI-085 #3: This separates the expensive DELETE operation from the hot
    write path, eliminating lock contention on the business-critical transaction.

    Args:
        conn: Database connection (caller owns transaction lifecycle)
        auto_commit: If True, commit after pruning (use only when caller
                     explicitly delegates transaction control for this operation)
    """
    global _deferred_prune_floor, _deferred_prune_cutoff

    if _deferred_prune_floor is None or _deferred_prune_cutoff is None:
        return 0

    floor_threshold = _deferred_prune_floor
    cutoff = _deferred_prune_cutoff
    _deferred_prune_floor = None
    _deferred_prune_cutoff = None

    pruned = 0
    with conn.cursor() as cur:
        # Find current pruned_through
        cur.execute("SELECT pruned_through FROM sim_event_outbox_state WHERE singleton_id = 1")
        row = cur.fetchone()
        if row is None:
            return 0
        current_floor = int(row[0])

        # Scan for pruneable prefix (oldest events first)
        cur.execute("SELECT sequence, created_at FROM sim_event_outbox "
                    "WHERE sequence > %s ORDER BY sequence LIMIT %s",
                    (current_floor, PRUNE_BATCH_SIZE))
        new_floor = current_floor
        for seq, created_at_val in cur.fetchall():
            if isinstance(created_at_val, str):
                created_at_val = datetime.fromisoformat(created_at_val)
            # Keep if: not too old AND not exceeding max retained count
            if created_at_val >= cutoff and seq > floor_threshold:
                break
            new_floor = seq

        if new_floor > current_floor:
            cur.execute("DELETE FROM sim_event_outbox WHERE sequence <= %s", (new_floor,))
            pruned = cur.rowcount
            cur.execute("UPDATE sim_event_outbox_state SET pruned_through = %s WHERE singleton_id = 1",
                        (new_floor,))

    return pruned
