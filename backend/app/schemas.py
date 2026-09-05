from __future__ import annotations

from pydantic import BaseModel


class PageV2(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class RefreshMeta(BaseModel):
    data_version: str = "v2.0-frozen"
    as_of_date: str = "2026-08-30"
    last_updated_at: str
    total_rows: int = 1685923
    status: str = "ok"
    seed: int = 42


class OverviewV2(BaseModel):
    org_total: int
    org_today_added: int = 0
    org_added_as_of_date: str = "2026-08-30"
    org_added_note: str = "当前封版无可追溯新增单位"
    contacts_total: int
    contacts_today_added: int = 0
    contacts_added_as_of_date: str = "无可追溯"
    contacts_added_note: str = "当前封版无可追溯新增人员"
    docs_total: int
    docs_today_added: int = 0
    docs_added_as_of_date: str = "2026-08-29"
    vouchers_total: int
    vouchers_today_added: int = 0
    vouchers_added_as_of_date: str = "2026-08-30"
    launched: int
    launched_pct: float
    dual: int
    construction_pct: float
    voucher_total: int
    voucher_success_pct: float
    integration_success_pct: float
    unresolved_issues: int
    high_risk: int
    regions: int = 34
    as_of_date: str = "2026-08-30"
