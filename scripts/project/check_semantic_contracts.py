#!/usr/bin/env python3
"""Guard high-risk facts that must stay aligned across code and living docs.

This is intentionally a small set of explicit contracts, not a claim that prose can
be fully verified by a linter. Add a contract when a cross-layer invariant has caused
or could cause a user-visible fact split.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def validate_contracts(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    lifecycle = _read(root, "backend/app/business_rules.py")
    for expected in (
        "DUAL_RUN_CONSISTENCY_RATE_MIN = 98.0",
        "CONSTRUCTION_LAG_RATE = 88.0",
        "OPENING_DATA_LAG_RATE = 88.0",
        "LAST_ACTIVE_BATCH_ID = 7",
    ):
        if expected not in lifecycle:
            errors.append(f"lifecycle policy drift: missing `{expected}`")

    for relative in (
        "frontend/src/views/OperationsView.vue",
        "frontend/src/views/IssuesView.vue",
        "frontend/src/views/InsightsView.vue",
    ):
        if "snapshot.businessRules" not in _read(root, relative):
            errors.append(f"dashboard rule source drift: {relative} bypasses businessRules")

    theme = _read(root, "frontend/src/styles/theme.css")
    scale = _read(root, "frontend/src/composables/useScaleScreen.ts")
    app = _read(root, "frontend/src/App.vue")
    if "--spacing-canvas-h: 980px" not in theme:
        errors.append("canvas contract drift: theme height is not 980px")
    if "baseHeight = 980" not in scale or "baseHeight: 980" not in app:
        errors.append("canvas contract drift: scale implementation is not 1920x980")

    broker = _read(root, "backend/app/live_projection/broker.py")
    live_doc = _read(root, "docs/development/LIVE-PROJECTION.md")
    if "OutboxReader" not in broker or "CommittedEventJournal" in broker:
        errors.append("live projection drift: broker must consume the transactional outbox only")
    for forbidden in ("RealisticSimulationEngine", "_load_units_pool"):
        if forbidden in broker:
            errors.append(f"live projection drift: broker contains `{forbidden}`")
    if "sim_event_outbox" not in live_doc:
        errors.append("live projection documentation drift: transactional outbox is not documented")

    runtime = _read(root, "simulation/runtime_service.py")
    for expected in (
        "EvolutionCoordinator",
        "auto_commit=False",
        "self.projection_writer(conn,",
    ):
        if expected not in runtime:
            errors.append(f"simulator orchestration drift: missing `{expected}`")

    writer = _read(root, "backend/app/live_projection/outbox_writer.py")
    for expected in ("FOR UPDATE", "pruned_through", "get_autocommit", "MAX_RETAINED_EVENTS"):
        if expected not in writer:
            errors.append(f"transactional outbox safety drift: missing `{expected}`")
    if "projection_journal.append" in runtime or "conn.commit(" in writer:
        errors.append("outbox transaction drift: independent journal write or writer-owned commit")

    heatwave = _read(root, "backend/app/integrations/heatwave_ml.py")
    risk_table = _read(root, "frontend/src/components/AtRiskUnitTable.vue")
    for source in ("HEATWAVE_SHAP", "RULE_BASED", "UNAVAILABLE"):
        if source not in heatwave or source not in risk_table:
            errors.append(f"model explanation provenance drift: `{source}` is not end-to-end")

    return errors


def main() -> int:
    errors = validate_contracts()
    if errors:
        for error in errors:
            print(f"  SEMANTIC CONTRACT  {error}")
        return 1
    print("[semantic-contracts] OK: high-risk cross-layer facts remain aligned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
