"""Authoritative cross-layer business rules exposed by the dashboard snapshot."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# ── 单位生命周期状态（org_unit.status / rollout_status_snapshot.status 的唯一合法取值）──
# 严格有序、只允许前进；SQL 与拟真层不得再散写这些字面量。
ORG_STATUS_NOT_STARTED = "未启动"
ORG_STATUS_PREPARING = "准备中"
ORG_STATUS_DUAL_READY = "已具备双轨条件"
ORG_STATUS_DUAL_RUNNING = "双轨运行中"
ORG_STATUS_LAUNCHED = "已上线"
ORG_STATUS_STABLE = "稳定运行"

ORG_LIFECYCLE_STAGES: tuple[str, ...] = (
    ORG_STATUS_NOT_STARTED,
    ORG_STATUS_PREPARING,
    ORG_STATUS_DUAL_READY,
    ORG_STATUS_DUAL_RUNNING,
    ORG_STATUS_LAUNCHED,
    ORG_STATUS_STABLE,
)

# 批次生命周期没有「已具备双轨条件」这一中间态。
BATCH_LIFECYCLE_STAGES: tuple[str, ...] = (
    ORG_STATUS_NOT_STARTED,
    ORG_STATUS_PREPARING,
    ORG_STATUS_DUAL_RUNNING,
    ORG_STATUS_LAUNCHED,
    ORG_STATUS_STABLE,
)

# 「已上线」口径：正式上线与稳定运行都算上线。
LAUNCHED_STATUSES: tuple[str, ...] = (ORG_STATUS_LAUNCHED, ORG_STATUS_STABLE)

# 六态数据库状态 → 前端四态展示（frontend RolloutStatus）。
# 「未启动」只由蓄水池（batch 8）分支直接产出；批次 1-7 内的未启动/已具备双轨条件都折叠为「准备中」。
DISPLAY_STATUS_MAPPING: dict[str, str] = {
    ORG_STATUS_DUAL_RUNNING: "双轨运行",
    ORG_STATUS_STABLE: "已上线",
    ORG_STATUS_DUAL_READY: "准备中",
    ORG_STATUS_NOT_STARTED: "准备中",
}
DISPLAY_STATUSES: tuple[str, ...] = ("未启动", "准备中", "双轨运行", "已上线")


def sql_status_list(statuses: Iterable[str]) -> str:
    """Render a constant status tuple as a SQL IN-list, e.g. ``('已上线', '稳定运行')``."""
    return "(" + ", ".join(f"'{s}'" for s in statuses) + ")"


SQL_LAUNCHED_STATUSES = sql_status_list(LAUNCHED_STATUSES)

# 演示口径的「推断批次」：历史存量单位（id<=2005）按状态与 id 区间归入 1-7 批，
# 蓄水池（batch_id=8）与在库批次原样保留。所有大屏批次统计共用此表达式（表别名固定为 o）。
SQL_INFERRED_BATCH_ID = f"""CASE
                    WHEN o.batch_id = 8 THEN 8
                    WHEN o.status = '{ORG_STATUS_DUAL_RUNNING}' THEN 6
                    WHEN o.id <= 2005 AND o.status = '{ORG_STATUS_STABLE}' AND o.id <= 150 THEN 1
                    WHEN o.id <= 2005 AND o.status = '{ORG_STATUS_STABLE}' AND o.id <= 330 THEN 2
                    WHEN o.id <= 2005 AND o.status = '{ORG_STATUS_STABLE}' THEN 3
                    WHEN o.id <= 2005 AND o.status = '{ORG_STATUS_LAUNCHED}' AND o.id <= 580 THEN 4
                    WHEN o.id <= 2005 AND o.status = '{ORG_STATUS_LAUNCHED}' THEN 5
                    WHEN o.id <= 2005 AND o.id > 1600 AND o.id <= 2000 THEN 7
                    WHEN o.batch_id BETWEEN 1 AND 7 THEN o.batch_id
                    ELSE 8
                END"""

DUAL_RUN_CONSISTENCY_RATE_MIN = 98.0
CONSTRUCTION_LAG_RATE = 88.0
# 建设滞后单位再按此线分为「高危」(<) 与「重点关注」(>=)。
CONSTRUCTION_CRITICAL_RATE = 80.0
OPENING_DATA_LAG_RATE = 88.0
LAST_ACTIVE_BATCH_ID = 7


def public_business_rules() -> dict[str, Any]:
    return {
        "lifecycle": {
            "dualRunConsistencyRateMin": DUAL_RUN_CONSISTENCY_RATE_MIN,
            "orgStages": list(ORG_LIFECYCLE_STAGES),
            "launchedStatuses": list(LAUNCHED_STATUSES),
            "displayStatuses": list(DISPLAY_STATUSES),
        },
        "risk": {
            "constructionLagRate": CONSTRUCTION_LAG_RATE,
            "constructionCriticalRate": CONSTRUCTION_CRITICAL_RATE,
            "openingDataLagRate": OPENING_DATA_LAG_RATE,
            "lastActiveBatchId": LAST_ACTIVE_BATCH_ID,
        },
    }
