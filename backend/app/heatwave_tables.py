"""Single source of truth for MOD tables expected in HeatWave RAPID."""

from __future__ import annotations

# Large facts plus the small dimensions/aggregates required to keep dashboard
# analytical joins fully eligible for RAPID. Production loading remains an
# explicitly authorized database operation; this tuple only defines the target.
TARGET_MOD_TABLES: tuple[str, ...] = (
    "business_document_line",
    "accounting_voucher_line",
    "business_document",
    "accounting_voucher",
    "integration_result",
    "rollout_status_snapshot",
    "construction_task",
    "dual_run_result",
    "org_unit",
    "sys_user",
    "data_readiness",
    "daily_stats",
)
