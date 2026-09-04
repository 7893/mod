from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta

from app.live_projection.broker import LiveProjectionBroker
from app.live_projection.models import ActivityProfile


def test_activity_profile_preserves_business_rhythm() -> None:
    monday_morning = datetime(2026, 9, 7, 2, 0, tzinfo=UTC)  # 10:00 CST
    monday_night = datetime(2026, 9, 7, 18, 0, tzinfo=UTC)  # 02:00 CST next day
    sunday_morning = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)

    assert ActivityProfile.factor(monday_morning) > ActivityProfile.factor(monday_night)
    assert ActivityProfile.factor(monday_morning) > ActivityProfile.factor(sunday_morning)


def _deterministic_units_pool() -> list[dict]:
    """A fixed, DB-independent unit pool covering every lifecycle stage so the
    causal simulation engine can emit each business_type deterministically."""
    launched = [
        {"name": f"沿海装备制造集团{i}", "province": "广东", "status": "已上线", "batch_id": 1}
        for i in range(6)
    ]
    stable = [
        {"name": f"能源化工联合体{i}", "province": "山东", "status": "稳定运行", "batch_id": 3}
        for i in range(4)
    ]
    dual = [
        {"name": f"双轨试点院{i}", "province": "江苏", "status": "双轨运行中", "batch_id": 6}
        for i in range(3)
    ]
    construction = [{"name": "在建联调所", "province": "四川", "status": "在建中", "batch_id": 7}]
    reserve = [{"name": "储备池单位", "province": "西藏", "status": "未启动", "batch_id": 8}]
    return launched + stable + dual + construction + reserve


def test_event_chain_is_bounded_and_causal() -> None:
    broker = LiveProjectionBroker(
        rng=random.Random(42),
        daily_document_cap=30,
        units_pool=_deterministic_units_pool(),
    )
    # Keep the clock within a single day so the daily document cap semantics hold
    # (the cap resets across days; cumulative across days would legitimately exceed it).
    now = datetime(2026, 9, 7, 2, 0, tzinfo=UTC)
    seen_types: set[str] = set()

    for _ in range(2000):
        event = broker.create_event(now)
        if event is None:
            continue
        seen_types.add(event.business_type)
        assert event.increments.documents <= 3
        assert event.increments.vouchers <= 2
        assert event.increments.integrations <= 2
        assert event.cumulative.vouchers <= event.cumulative.documents
        assert event.cumulative.integrations <= event.cumulative.vouchers

    # Daily document budget is a soft cap: once reached, no further events are
    # emitted, but the final event may overshoot by at most one max increment (3).
    assert broker.cumulative.documents <= 30 + 3
    # Over many iterations, each production business_type should appear.
    assert {"document_created", "voucher_created", "integration_completed"} <= seen_types


def test_interval_is_irregular_and_bounded() -> None:
    broker = LiveProjectionBroker(
        rng=random.Random(7),
        units_pool=_deterministic_units_pool(),
    )
    now = datetime(2026, 9, 7, 2, 0, tzinfo=UTC)
    intervals = [broker.next_interval(now) for _ in range(20)]

    # The realistic engine bounds intervals within [2.5, 90] seconds.
    assert all(2.5 <= interval <= 90.0 for interval in intervals)
    assert len({round(interval, 3) for interval in intervals}) > 5


def test_subscribers_receive_the_same_event() -> None:
    async def exercise() -> None:
        broker = LiveProjectionBroker(
            rng=random.Random(1),
            units_pool=_deterministic_units_pool(),
        )
        first = broker.subscribe()
        second = broker.subscribe()
        # Advance until the engine emits an event (causal sampling may skip ticks).
        event = None
        now = datetime(2026, 9, 7, 2, 0, tzinfo=UTC)
        for _ in range(100):
            event = broker.create_event(now)
            now += timedelta(seconds=30)
            if event is not None:
                break
        assert event is not None

        broker._publish(event)

        assert await first.get() is event
        assert await second.get() is event
        broker.unsubscribe(first)
        broker.unsubscribe(second)

    asyncio.run(exercise())
