from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.live_projection.broker import LiveProjectionBroker
from app.live_projection.journal import CommittedEventJournal
from app.live_projection.models import ActivityProfile


def _record(event_id: str = "document-1") -> dict:
    return {
        "event_id": event_id,
        "committed_at": "2026-09-07T10:00:00+08:00",
        "business_type": "integration_completed",
        "increments": {"documents": 1, "vouchers": 1, "integrations": 1},
        "unit_name": "沿海装备制造集团",
        "province": "广东",
        "story_title": "费用报销单完成业务入账",
    }


def test_activity_profile_preserves_business_rhythm() -> None:
    monday_morning = datetime(2026, 9, 7, 2, 0, tzinfo=UTC)
    monday_night = datetime(2026, 9, 7, 18, 0, tzinfo=UTC)
    sunday_morning = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)
    assert ActivityProfile.factor(monday_morning) > ActivityProfile.factor(monday_night)
    assert ActivityProfile.factor(monday_morning) > ActivityProfile.factor(sunday_morning)


def test_journal_round_trip_and_committed_mode(tmp_path) -> None:
    path = tmp_path / "committed.jsonl"
    journal = CommittedEventJournal(path)
    journal.append([_record()])
    offset, records = journal.read_from(0)
    assert offset == path.stat().st_size
    assert records == [_record()]

    broker = LiveProjectionBroker(journal_path=path)
    event = broker.ingest_record(records[0])
    assert event is not None
    assert event.id == "document-1"
    assert event.mode == "committed_simulation"
    assert event.cumulative.documents == 1
    assert broker.state_payload()["source_available"] is True


def test_malformed_journal_record_is_not_projected(tmp_path) -> None:
    broker = LiveProjectionBroker(journal_path=tmp_path / "missing.jsonl")
    assert broker.ingest_record({"event_id": "bad"}) is None
    assert broker.enabled is False
    assert broker.state_payload()["source_available"] is False


def test_subscribers_receive_the_same_committed_event(tmp_path) -> None:
    async def exercise() -> None:
        broker = LiveProjectionBroker(journal_path=tmp_path / "committed.jsonl")
        event = broker.ingest_record(_record())
        assert event is not None
        first = broker.subscribe()
        second = broker.subscribe()
        broker._publish(event)
        assert await first.get() is event
        assert await second.get() is event
        broker.unsubscribe(first)
        broker.unsubscribe(second)

    asyncio.run(exercise())


def test_journal_replay_from_id_and_rotation(tmp_path) -> None:
    journal = CommittedEventJournal(tmp_path / "committed.jsonl")
    records = [
        {"event_id": f"evt-{i}", "committed_at": "2026-09-12T10:00:00+00:00", "increments": {"documents": 1, "vouchers": 1, "integrations": 1}}
        for i in range(5)
    ]
    journal.append(records)

    # Replay after evt-2: should yield evt-3 and evt-4
    replayed = list(journal.replay_from_id("evt-2"))
    assert [r["event_id"] for r in replayed] == ["evt-3", "evt-4"]

    # Replay with None or non-existent ID yields nothing
    assert list(journal.replay_from_id(None)) == []
    assert list(journal.replay_from_id("evt-999")) == []

    # Rotation test
    assert journal.rotate_if_needed(max_size_mb=100) is False
    assert journal.rotate_if_needed(max_size_mb=0) is True
    assert (tmp_path / "committed.jsonl.old").exists()

