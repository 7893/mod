"""HTTP transport for the read-only live projection."""

from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from .broker import get_live_projection_broker

router = APIRouter(prefix="/api/live-projection", tags=["live-projection"])


@router.get("/events")
async def projection_events(
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Stream live projection events. Supports reconnection via Last-Event-ID header (KI-073)."""
    broker = get_live_projection_broker()
    return StreamingResponse(
        broker.stream(last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def projection_status() -> dict:
    broker = get_live_projection_broker()
    return {"enabled": broker.enabled, **broker.state_payload()}
