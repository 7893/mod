from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json

import pytest

from app.live_projection.broker import LiveProjectionBroker, cursor_id, event_payload
from app.live_projection.journal import CommittedEventJournal
from app.live_projection.models import ActivityProfile
from app.live_projection.outbox import OutboxPage


def _record(sequence=1):
    return {
        'event_id': f'document-{sequence}', 'sequence': sequence,
        'committed_at': '2026-09-07T10:00:00+08:00',
        'business_type': 'integration_completed',
        'increments': {'documents': 1, 'vouchers': 1, 'integrations': 1},
        'cumulative': {'documents': sequence, 'vouchers': sequence, 'integrations': sequence},
        'unit_name': '测试单位', 'province': '广东', 'story_title': '费用报销单完成业务入账',
    }


class MemoryReader:
    def __init__(self, count=5, floor=0):
        self.head = count
        self.floor = floor
        self.stream_id = 'stream-a'
        self.failure = False
        self.requests = []

    def read_page(self, after, limit=100):
        if self.failure:
            raise OSError('offline')
        self.requests.append(after)
        start = self.head if after is None else max(after, self.floor)
        return OutboxPage(self.stream_id, self.head, self.floor,
                          {k: self.head for k in ('documents', 'vouchers', 'integrations')},
                          [_record(i) for i in range(start + 1, min(start + limit, self.head) + 1)])


def data(message):
    return json.loads(message.split('data: ', 1)[1])


def test_activity_profile_preserves_business_rhythm():
    morning = datetime(2026, 9, 7, 2, tzinfo=UTC)
    assert ActivityProfile.factor(morning) > ActivityProfile.factor(datetime(2026, 9, 7, 18, tzinfo=UTC))
    assert ActivityProfile.factor(morning) > ActivityProfile.factor(datetime(2026, 9, 6, 2, tzinfo=UTC))


def test_event_conversion_is_pure_and_rejects_invalid_records():
    record = _record()
    first = event_payload(record, 'stream-a')
    assert first == event_payload(record, 'stream-a')
    assert first['cumulative']['documents'] == 1
    assert first['business_event_id'] == 'document-1'
    assert first['id'] == 'outbox:stream-a:1'
    assert first['mode'] == 'committed_simulation'
    with pytest.raises(KeyError):
        event_payload({'event_id': 'bad'}, 'stream-a')


def test_replay_multiple_clients_and_api_restart_do_not_inflate_counts():
    async def exercise():
        reader = MemoryReader()
        broker = LiveProjectionBroker(reader=reader)
        first = broker.stream(cursor_id(reader.stream_id, 2))
        second = broker.stream(cursor_id(reader.stream_id, 2))
        a, b = data(await anext(first)), data(await anext(second))
        assert a == b
        assert a['sequence'] == a['cumulative']['documents'] == 3
        restarted = LiveProjectionBroker(reader=reader).stream(a['id'])
        assert data(await anext(restarted))['sequence'] == 4
        assert (await broker.status())['cumulative']['documents'] == 5
        await first.aclose()
        await second.aclose()
        await restarted.aclose()
    asyncio.run(exercise())


def test_slow_connection_pages_all_events_without_dropping_or_advancing_to_head():
    async def exercise():
        reader = MemoryReader(250)
        stream = LiveProjectionBroker(reader=reader).stream(cursor_id(reader.stream_id, 0))
        received = []
        for _ in range(250):
            received.append(data(await anext(stream))['sequence'])
            await asyncio.sleep(0)
        assert received == list(range(1, 251))
        assert reader.requests == [None, 0, 100, 200]
        await stream.aclose()
    asyncio.run(exercise())


@pytest.mark.parametrize('last_id', ['document-old', 'outbox:other:1', 'outbox:stream-a:1', 'outbox:stream-a:99'])
def test_invalid_expired_and_future_cursors_explicitly_reset(last_id):
    async def exercise():
        reader = MemoryReader(5, floor=2)
        stream = LiveProjectionBroker(reader=reader).stream(last_id)
        state = data(await anext(stream))
        assert state['reset_required'] is True
        assert state['id'] == cursor_id(reader.stream_id, 5)
        # A state message carries a valid resume cursor, never a fabricated state-* id.
        reconnect = LiveProjectionBroker(reader=reader).stream(state['id'])
        reader.head = 6
        assert data(await anext(reconnect))['sequence'] == 6
        await stream.aclose()
        await reconnect.aclose()
    asyncio.run(exercise())


def test_retention_during_pause_resets_instead_of_silently_skipping():
    async def exercise():
        reader = MemoryReader(1)
        stream = LiveProjectionBroker(reader=reader).stream(cursor_id(reader.stream_id, 0))
        assert data(await anext(stream))['sequence'] == 1
        reader.head, reader.floor = 10, 5
        assert data(await anext(stream))['reset_required'] is True
        await stream.aclose()
    asyncio.run(exercise())


def test_db_outage_preserves_resume_position_and_recovers(monkeypatch):
    async def exercise():
        reader = MemoryReader(1)
        stream = LiveProjectionBroker(reader=reader).stream(cursor_id(reader.stream_id, 0))
        assert data(await anext(stream))['sequence'] == 1
        reader.failure = True
        unavailable = await anext(stream)
        assert 'source_unavailable' in unavailable and 'id:' not in unavailable
        reader.failure, reader.head = False, 2
        assert data(await anext(stream))['sequence'] == 2
        await stream.aclose()
    asyncio.run(exercise())


def test_legacy_journal_remains_readable_for_archive(tmp_path):
    journal = CommittedEventJournal(tmp_path / 'committed.jsonl')
    records = [_record(i) for i in range(1, 6)]
    journal.append(records)
    offset, read = journal.read_from(0)
    assert offset == journal.path.stat().st_size
    assert read == records
    assert list(journal.replay_from_id('document-3')) == records[3:]
    assert list(journal.replay_from_id('unknown')) == []
    assert not journal.rotate_if_needed(max_size_mb=100)
    assert journal.rotate_if_needed(max_size_mb=0)
    assert journal.path.with_suffix('.jsonl.old').exists()


def test_db_recovery_without_new_events_restores_source_state():
    async def exercise():
        reader = MemoryReader(1)
        stream = LiveProjectionBroker(reader=reader).stream(cursor_id(reader.stream_id, 0))
        assert data(await anext(stream))['sequence'] == 1
        reader.failure = True
        assert 'source_unavailable' in await anext(stream)
        reader.failure = False
        state = data(await anext(stream))
        assert state['sequence'] == 1
        assert state['source_available'] is True
        assert state['id'] == cursor_id(reader.stream_id, 1)
        await stream.aclose()
    asyncio.run(exercise())
