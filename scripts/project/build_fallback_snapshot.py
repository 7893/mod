#!/usr/bin/env python3
"""Build the slim fallback snapshot shared by backend and frontend.

The fallback snapshot is what the API serves when the database is unreachable and
what the frontend bundles as its initial state. It must keep the *shape* of the
live payload (so types and views stay honest) while carrying only a small,
stratified sample of units so it stays reviewable and does not bloat the bundle.

Usage:
    python3 scripts/project/build_fallback_snapshot.py --from-url https://mod.fuming.name/api/dashboard/snapshot
    python3 scripts/project/build_fallback_snapshot.py --from-file /tmp/snap.json

Only read access to the source is needed; nothing is written except the output file.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "frontend" / "src" / "data" / "fallback-snapshot.json"

# Per (batch, status) cell. Enough for every filter option in the ledgers to be non-empty.
SAMPLE_PER_CELL = 4
# Keys the backend no longer emits; strip defensively so stale sources cannot resurrect them.
DEAD_ENTITY_KEYS = {"rawOwner", "rawStatus", "leadershipAttention"}
DEAD_OVERVIEW_KEYS = {"leadershipAttention"}
# The live snapshot's insights section only carries rule alerts; everything else comes from /api/insights/status.
INSIGHTS_KEYS = ("ruleBasedAlerts",)


def _load(args: argparse.Namespace) -> dict:
    if args.from_file:
        return json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    with urllib.request.urlopen(args.from_url, timeout=30) as resp:  # noqa: S310 - explicit https URL from CLI
        return json.load(resp)


def sample_entities(entities: list[dict]) -> list[dict]:
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in sorted(entities, key=lambda r: int(r.get("id") or 0)):
        cells[(str(row.get("batch")), str(row.get("status")))].append(row)
    picked: list[dict] = []
    for key in sorted(cells):
        picked.extend(cells[key][:SAMPLE_PER_CELL])
    # Guarantee at least one unit for the capital so province filters in tests/demos have a stable target.
    if not any(r.get("province") == "北京" for r in picked):
        picked.extend(r for r in entities if r.get("province") == "北京")[:1]
    return [{k: v for k, v in row.items() if k not in DEAD_ENTITY_KEYS} for row in picked]


def build(snapshot: dict) -> dict:
    slim = dict(snapshot)
    slim.pop("businessRules", None)  # always injected by the backend from business_rules.py
    slim["meta"] = {k: v for k, v in snapshot.get("meta", {}).items() if k != "source"}
    slim["overview"] = {k: v for k, v in snapshot.get("overview", {}).items() if k not in DEAD_OVERVIEW_KEYS}
    slim["entities"] = sample_entities(snapshot.get("entities", []))
    slim["insights"] = {k: snapshot.get("insights", {}).get(k, []) for k in INSIGHTS_KEYS}
    return slim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-url")
    source.add_argument("--from-file")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args(argv)

    snapshot = _load(args)
    slim = build(snapshot)
    out = Path(args.output)
    out.write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"[fallback-snapshot] wrote {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}: "
        f"{len(slim['entities'])} sampled units of {len(snapshot.get('entities', []))}, "
        f"{out.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
