"""Domain models and bounded activity rules for live presentation events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..config import get_display_timezone

DISPLAY_TIMEZONE = get_display_timezone()


@dataclass(frozen=True)
class ProjectionIncrements:
    documents: int = 0
    vouchers: int = 0
    integrations: int = 0


@dataclass(frozen=True)
class ProjectionEvent:
    id: str
    sequence: int
    occurred_at: datetime
    business_type: str
    increments: ProjectionIncrements
    cumulative: ProjectionIncrements
    projection_id: str
    unit_name: str | None = None
    province: str | None = None
    story_title: str | None = None
    story_desc: str | None = None
    amount: str | None = None
    badge_tone: str | None = None
    batch_name: str | None = None
    mode: str = field(default="display_projection", init=False)

    def as_payload(self) -> dict:
        payload = asdict(self)
        payload["occurred_at"] = self.occurred_at.isoformat()
        return payload


class ActivityProfile:
    """Return a stable business activity multiplier for China Standard Time."""

    HOUR_FACTORS = {
        0: 0.02, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01, 5: 0.02,
        6: 0.10, 7: 0.25, 8: 0.50, 9: 1.00, 10: 1.20, 11: 1.10,
        12: 0.40, 13: 0.50, 14: 1.10, 15: 1.30, 16: 1.20, 17: 0.80,
        18: 0.30, 19: 0.15, 20: 0.10, 21: 0.05, 22: 0.03, 23: 0.02,
    }
    WEEKDAY_FACTORS = {0: 1.0, 1: 1.05, 2: 1.05, 3: 1.0, 4: 0.95, 5: 0.15, 6: 0.10}

    @classmethod
    def factor(cls, value: datetime) -> float:
        local = value.astimezone(DISPLAY_TIMEZONE)
        if local.day <= 5:
            day_factor = 0.9
        elif local.day <= 20:
            day_factor = 1.0
        elif local.day <= 25:
            day_factor = 1.4
        else:
            day_factor = 1.6
        factor = cls.HOUR_FACTORS[local.hour] * cls.WEEKDAY_FACTORS[local.weekday()] * day_factor
        return max(0.01, min(2.0, factor))
