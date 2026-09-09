"""Authoritative cross-layer business rules exposed by the dashboard snapshot."""

from __future__ import annotations

from typing import Any

DUAL_RUN_CONSISTENCY_RATE_MIN = 98.0
CONSTRUCTION_LAG_RATE = 88.0
OPENING_DATA_LAG_RATE = 88.0
LAST_ACTIVE_BATCH_ID = 7


def public_business_rules() -> dict[str, Any]:
    return {
        "lifecycle": {
            "dualRunConsistencyRateMin": DUAL_RUN_CONSISTENCY_RATE_MIN,
        },
        "risk": {
            "constructionLagRate": CONSTRUCTION_LAG_RATE,
            "openingDataLagRate": OPENING_DATA_LAG_RATE,
            "lastActiveBatchId": LAST_ACTIVE_BATCH_ID,
        },
    }
