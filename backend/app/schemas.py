from __future__ import annotations

from pydantic import BaseModel, Field


class Page(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class EntityPatch(BaseModel):
    """单位状态调整请求体。"""
    status: str | None = None
    owner: str | None = None
    construction: float | None = Field(None, ge=0, le=100)
    opening_data: float | None = Field(None, ge=0, le=100)
