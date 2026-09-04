from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RolloutUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=20)
    actual_date: date | None = None
    operator_id: int = Field(default=1, ge=1)


class Page(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int

