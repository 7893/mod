"""Read-only, bounded outbox pages. One SQL snapshot includes rows and retention metadata."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from typing import Callable

from sqlalchemy import create_engine, text


@lru_cache
def get_outbox_engine():
    # A separate small pool bounds subscriber load and socket waits without changing
    # the dashboard's engine or importing the simulator into the API process.
    from ..config import get_settings
    return create_engine(
        get_settings().database_url, isolation_level='AUTOCOMMIT', pool_pre_ping=True,
        pool_size=4, max_overflow=0, pool_timeout=3, pool_recycle=1800,
        connect_args={'connect_timeout': 3, 'read_timeout': 3, 'write_timeout': 3},
    )


@dataclass(frozen=True)
class OutboxPage:
    stream_id: str
    head: int
    floor: int
    cumulative: dict[str, int]
    records: list[dict]


class OutboxReader:
    def __init__(self, engine_factory: Callable | None = None):
        if engine_factory is None:
            engine_factory = get_outbox_engine
        self.engine_factory = engine_factory

    def read_page(self, after: int | None, limit: int = 100) -> OutboxPage:
        if not 1 <= limit <= 100:
            raise ValueError("Outbox page limit must be within 1..100")
        with self.engine_factory().connect() as conn:
            rows = conn.execute(text("""
                SELECT s.stream_id, s.last_sequence, s.pruned_through,
                       s.documents AS total_documents, s.vouchers AS total_vouchers,
                       s.integrations AS total_integrations,
                       e.sequence, e.payload, e.documents, e.vouchers, e.integrations
                FROM sim_event_outbox_state s
                LEFT JOIN sim_event_outbox e ON e.sequence > COALESCE(:after, s.last_sequence)
                    AND e.sequence <= s.last_sequence
                WHERE s.singleton_id = 1
                ORDER BY e.sequence LIMIT :limit
            """), {'after': after, 'limit': limit}).mappings().all()
        if not rows:
            raise RuntimeError("Outbox state unavailable")
        state = rows[0]
        records = []
        for row in rows:
            if row['sequence'] is None:
                continue
            payload = row['payload']
            record = dict(json.loads(payload) if isinstance(payload, str) else payload)
            record['sequence'] = int(row['sequence'])
            record['cumulative'] = {k: int(row[k]) for k in ('documents', 'vouchers', 'integrations')}
            records.append(record)
        return OutboxPage(
            str(state['stream_id']), int(state['last_sequence']), int(state['pruned_through']),
            {k: int(state['total_' + k]) for k in ('documents', 'vouchers', 'integrations')}, records,
        )
