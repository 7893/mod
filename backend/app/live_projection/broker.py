"""SSE broker that projects only events committed by the resident simulator."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .journal import CommittedEventJournal
from .models import ProjectionEvent, ProjectionIncrements


def _enabled_from_environment() -> bool:
    return os.getenv("MOD_LIVE_PROJECTION_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


class LiveProjectionBroker:
    """Tail the committed-event journal and fan out one shared factual stream."""

    def __init__(self, *, journal_path: Path | None = None, poll_interval_seconds: float = 0.5, **_: Any) -> None:
        self.configured = _enabled_from_environment()
        self.journal = CommittedEventJournal(journal_path)
        self.poll_interval_seconds = poll_interval_seconds
        self._projection_id = "committed-simulator"
        self._sequence = 0
        self._offset = 0
        self._cumulative = ProjectionIncrements()
        self._subscribers: set[asyncio.Queue[ProjectionEvent]] = set()
        self._task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return self.configured and self.journal.path.exists()

    @property
    def cumulative(self) -> ProjectionIncrements:
        return self._cumulative

    def ingest_record(self, record: dict[str, Any]) -> ProjectionEvent | None:
        increments = record.get("increments")
        if not isinstance(increments, dict) or not record.get("event_id") or not record.get("committed_at"):
            return None
        try:
            occurred_at = datetime.fromisoformat(str(record["committed_at"]))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            inc = ProjectionIncrements(
                documents=max(0, int(increments.get("documents", 0))),
                vouchers=max(0, int(increments.get("vouchers", 0))),
                integrations=max(0, int(increments.get("integrations", 0))),
            )
        except (TypeError, ValueError):
            return None
        self._sequence += 1
        self._cumulative = ProjectionIncrements(
            documents=self._cumulative.documents + inc.documents,
            vouchers=self._cumulative.vouchers + inc.vouchers,
            integrations=self._cumulative.integrations + inc.integrations,
        )
        return ProjectionEvent(
            id=str(record["event_id"]),
            sequence=self._sequence,
            occurred_at=occurred_at,
            business_type=str(record.get("business_type") or "integration_completed"),
            increments=inc,
            cumulative=self._cumulative,
            projection_id=self._projection_id,
            unit_name=record.get("unit_name"),
            province=record.get("province"),
            story_title=record.get("story_title"),
            story_desc=record.get("story_desc"),
            amount=record.get("amount"),
            badge_tone=record.get("badge_tone"),
            batch_name=record.get("batch_name"),
        )

    async def start(self) -> None:
        if self.configured and self._task is None:
            # Existing records are already represented in the authoritative snapshot.
            self._offset = self.journal.path.stat().st_size if self.journal.path.exists() else 0
            self._task = asyncio.create_task(self._run(), name="committed-live-projection")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def subscribe(self) -> asyncio.Queue[ProjectionEvent]:
        queue: asyncio.Queue[ProjectionEvent] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ProjectionEvent]) -> None:
        self._subscribers.discard(queue)

    def state_payload(self) -> dict[str, Any]:
        return {
            "id": f"{self._projection_id}-state-{self._sequence}",
            "sequence": self._sequence,
            "occurred_at": datetime.now(UTC).isoformat(),
            "business_type": "projection_state",
            "increments": {"documents": 0, "vouchers": 0, "integrations": 0},
            "cumulative": {
                "documents": self._cumulative.documents,
                "vouchers": self._cumulative.vouchers,
                "integrations": self._cumulative.integrations,
            },
            "projection_id": self._projection_id,
            "unit_name": None,
            "province": None,
            "mode": "committed_simulation",
            "source_available": self.journal.path.exists(),
        }

    async def stream(self, last_event_id: str | None = None):
        """Stream events, optionally replaying from last_event_id for reconnection (KI-073)."""
        queue = self.subscribe()
        try:
            # Replay missed events if reconnecting
            if last_event_id:
                for record in self.journal.replay_from_id(last_event_id):
                    event = self.ingest_record(record)
                    if event is not None:
                        yield self._sse(event.as_payload())

            yield self._sse(self.state_payload())
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield self._sse(event.as_payload())
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(queue)

    async def _run(self) -> None:
        while True:
            self._offset, records = self.journal.read_from(self._offset)
            for record in records:
                event = self.ingest_record(record)
                if event is not None:
                    self._publish(event)
            await asyncio.sleep(self.poll_interval_seconds)

    def _publish(self, event: ProjectionEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        return f"id: {payload['id']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_broker = LiveProjectionBroker()


def get_live_projection_broker() -> LiveProjectionBroker:
    return _broker
