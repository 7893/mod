"""Shared daily-stat cascade for simulation writers."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import date
from typing import Any

DailyDelta = dict[str, int]
DailyDeltas = MutableMapping[date, DailyDelta]

_DELTA_KEYS = (
    "docs",
    "doc_lines",
    "vouchers",
    "voucher_lines",
    "links",
    "integrations",
    "success",
)


def add_daily_delta(deltas: DailyDeltas, stat_date: date, **increments: int) -> None:
    """Add sparse increments to one business date."""
    delta = deltas.setdefault(stat_date, {key: 0 for key in _DELTA_KEYS})
    for key, value in increments.items():
        if key not in delta:
            raise ValueError(f"Unknown daily_stats delta: {key}")
        delta[key] += value


def apply_daily_deltas(cursor: Any, deltas: DailyDeltas) -> int:
    """Apply daily increments while preserving cumulative-counter semantics."""
    rows_touched = 0
    for stat_date in sorted(deltas):
        delta = deltas[stat_date]
        cursor.execute(
            "SELECT stat_date FROM daily_stats WHERE stat_date = %s FOR UPDATE;",
            (stat_date,),
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE daily_stats SET "
                "doc_count = doc_count + %s, doc_today = doc_today + %s, "
                "voucher_count = voucher_count + %s, voucher_today = voucher_today + %s, "
                "integration_count = integration_count + %s, integration_success = integration_success + %s, "
                "doc_line_count = doc_line_count + %s, voucher_line_count = voucher_line_count + %s, "
                "link_count = link_count + %s WHERE stat_date = %s;",
                (
                    delta["docs"], delta["docs"],
                    delta["vouchers"], delta["vouchers"],
                    delta["integrations"], delta["success"],
                    delta["doc_lines"], delta["voucher_lines"],
                    delta["links"], stat_date,
                ),
            )
        else:
            cursor.execute(
                "SELECT org_count, user_count, doc_count, voucher_count, "
                "integration_count, integration_success, doc_line_count, "
                "voucher_line_count, link_count, dual_run_count, snapshot_count "
                "FROM daily_stats WHERE stat_date < %s ORDER BY stat_date DESC LIMIT 1;",
                (stat_date,),
            )
            previous = cursor.fetchone()
            if previous:
                (orgs, users, docs, vouchers, integrations, successes,
                 doc_lines, voucher_lines, links, dual_runs, snapshots) = previous
            else:
                cursor.execute("SELECT COUNT(*) FROM org_unit")
                orgs = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM sys_user")
                users = cursor.fetchone()[0] or 0
                docs = vouchers = integrations = successes = 0
                doc_lines = voucher_lines = links = dual_runs = snapshots = 0

            cursor.execute(
                "INSERT INTO daily_stats ("
                "stat_date, org_count, user_count, doc_count, doc_today, "
                "voucher_count, voucher_today, integration_count, integration_success, "
                "doc_line_count, voucher_line_count, link_count, dual_run_count, snapshot_count"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                (
                    stat_date, orgs, users,
                    docs + delta["docs"], delta["docs"],
                    vouchers + delta["vouchers"], delta["vouchers"],
                    integrations + delta["integrations"], successes + delta["success"],
                    doc_lines + delta["doc_lines"], voucher_lines + delta["voucher_lines"],
                    links + delta["links"], dual_runs, snapshots,
                ),
            )
        rows_touched += 1
    return rows_touched
