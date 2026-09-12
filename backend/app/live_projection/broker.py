"""Read-only SSE fan-out using per-connection persistent outbox cursors."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
import os

from .models import ProjectionEvent, ProjectionIncrements
from .outbox import OutboxPage, OutboxReader

logger = logging.getLogger(__name__)


def cursor_id(stream_id: str, sequence: int) -> str:
    return f"outbox:{stream_id}:{sequence}"


def parse_cursor(value: str | None) -> tuple[str, int] | None:
    if not value or len(value) > 160:
        return None
    parts = value.split(':')
    if len(parts) != 3 or parts[0] != 'outbox' or not parts[1] or not parts[2].isascii() or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


def event_payload(record: dict, stream_id: str) -> dict:
    """Pure conversion: replay does not mutate any broker-global sequence or totals."""
    occurred_at = datetime.fromisoformat(record['committed_at'])
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    result = ProjectionEvent(
        id=cursor_id(stream_id, record['sequence']), sequence=record['sequence'],
        occurred_at=occurred_at, business_type=record['business_type'],
        increments=ProjectionIncrements(**record['increments']),
        cumulative=ProjectionIncrements(**record['cumulative']), projection_id=stream_id,
        **{k: record.get(k) for k in ('unit_name', 'province', 'story_title', 'story_desc',
                                     'amount', 'badge_tone', 'batch_name')},
    ).as_payload()
    result['business_event_id'] = record['event_id']
    return result


class LiveProjectionBroker:
    """No shared consuming offset or dropping queues; each connection pages from its cursor.

    Delivery is at least once within retained history. New clients use the current
    snapshot boundary; unknown/expired cursors explicitly reset to that boundary.
    """
    def __init__(self, *, reader=None, poll_interval_seconds: float = 0.5):
        self.configured = os.getenv('MOD_LIVE_PROJECTION_ENABLED', 'true').lower() in {'1', 'true', 'yes'}
        self.reader = reader if reader is not None else OutboxReader()
        self.poll_interval_seconds = poll_interval_seconds
        self._available = False
        self._running = True
        self._last_page: OutboxPage | None = None

    @property
    def enabled(self) -> bool:
        return self.configured and self._available

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def _read(self, after: int | None) -> OutboxPage:
        page = await asyncio.to_thread(self.reader.read_page, after)
        self._last_page = page
        self._available = True
        return page

    def state_payload(self, page: OutboxPage | None = None, *, reset_reason: str | None = None) -> dict:
        page = page or self._last_page
        return {
            'id': cursor_id(page.stream_id, page.head) if page else '',
            'sequence': page.head if page else 0,
            'occurred_at': datetime.now(UTC).isoformat(),
            'business_type': 'projection_state',
            'increments': {'documents': 0, 'vouchers': 0, 'integrations': 0},
            'cumulative': page.cumulative if page else {'documents': 0, 'vouchers': 0, 'integrations': 0},
            'projection_id': page.stream_id if page else 'unavailable',
            'mode': 'committed_simulation', 'source_available': self.enabled,
            'reset_required': reset_reason is not None, 'reset_reason': reset_reason,
        }

    async def status(self) -> dict:
        if self.configured:
            try:
                await self._read(None)
            except Exception as error:
                self._available = False
                logger.warning('Outbox status unavailable: %s', type(error).__name__)
        return {'enabled': self.enabled, **self.state_payload()}

    async def stream(self, last_event_id: str | None = None):
        position: int | None = None
        stream_id: str | None = None
        recovering = False
        while self._running and self.configured:
            try:
                if position is None:
                    page = await self._read(None)
                    requested = parse_cursor(last_event_id)
                    if requested and requested[0] == page.stream_id and page.floor <= requested[1] <= page.head:
                        stream_id, position = requested
                        # Do not send head state before replay: it would advance the browser cursor.
                        if position == page.head:
                            yield self._sse(self.state_payload(page))
                    else:
                        stream_id, position = page.stream_id, page.head
                        reason = 'cursor_unavailable' if last_event_id else None
                        yield self._sse(self.state_payload(page, reset_reason=reason))
                page = await self._read(position)
                if page.stream_id != stream_id or position < page.floor or position > page.head:
                    stream_id, position = page.stream_id, page.head
                    yield self._sse(self.state_payload(page, reset_reason='retention_or_stream_changed'))
                    continue
                if not page.records and position < page.head:
                    raise RuntimeError('Missing retained outbox records')
                for record in page.records:
                    if record['sequence'] != position + 1:
                        raise RuntimeError('Noncontiguous outbox sequence')
                    payload = event_payload(record, stream_id)
                    position = record['sequence']
                    yield self._sse(payload)
                if page.records:
                    recovering = False
                    continue  # Drain the retained backlog in bounded pages, without dropping events.
                if recovering:
                    yield self._sse(self.state_payload(page))
                    recovering = False
                yield ': heartbeat\n\n'
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._available = False
                recovering = True
                logger.warning('Outbox stream unavailable: %s', type(error).__name__)
                # No SSE id: a temporary outage must not destroy the browser resume position.
                yield 'event: source_unavailable\ndata: {}\n\n'
                await asyncio.sleep(max(1.0, self.poll_interval_seconds))

    @staticmethod
    def _sse(payload: dict) -> str:
        return f"id: {payload['id']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_broker = LiveProjectionBroker()


def get_live_projection_broker() -> LiveProjectionBroker:
    return _broker
