from __future__ import annotations

from pydantic import BaseModel


class Page(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
