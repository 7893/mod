"""Governance issues and timeline services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.engine import Connection


def list_governance_issues(
    conn: Connection,
    status: Optional[str] = None,
    batch_id: Optional[int] = None,
    issue_type: Optional[str] = None,
    unit_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    conditions = []
    params: Dict[str, Any] = {"limit": page_size, "offset": offset}

    if status:
        conditions.append("status = :status")
        params["status"] = status
    if batch_id is not None:
        conditions.append("batch_id = :batch_id")
        params["batch_id"] = batch_id
    if issue_type:
        conditions.append("issue_type = :issue_type")
        params["issue_type"] = issue_type
    if unit_id is not None:
        conditions.append("unit_id = :unit_id")
        params["unit_id"] = unit_id

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # 1. Total count
    count_sql = f"SELECT COUNT(*) FROM governance_issue {where_clause}"
    total = conn.execute(text(count_sql), params).scalar() or 0

    # 2. Items
    items_sql = f"""
        SELECT id, unit_id AS unitId, unit_name AS unitName, province, batch_id AS batchId,
               issue_type AS issueType, severity, status, owner, title, description,
               ai_enriched AS aiEnriched, rework_count AS reworkCount,
               DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') AS createdAt,
               DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i:%s') AS updatedAt,
               DATE_FORMAT(resolved_at, '%Y-%m-%d %H:%i:%s') AS resolvedAt
        FROM governance_issue
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """
    rows = [dict(r) for r in conn.execute(text(items_sql), params).mappings()]

    # 3. Aggregations by status
    status_summary_sql = """
        SELECT status, COUNT(*) AS count
        FROM governance_issue
        GROUP BY status
    """
    status_summary = {
        r["status"]: r["count"]
        for r in conn.execute(text(status_summary_sql)).mappings()
    }

    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "statusSummary": status_summary,
        "items": rows,
    }


def get_governance_issue(conn: Connection, issue_id: str) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT id, unit_id AS unitId, unit_name AS unitName, province, batch_id AS batchId,
               issue_type AS issueType, severity, status, owner, title, description,
               ai_enriched AS aiEnriched, rework_count AS reworkCount,
               DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') AS createdAt,
               DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i:%s') AS updatedAt,
               DATE_FORMAT(resolved_at, '%Y-%m-%d %H:%i:%s') AS resolvedAt
        FROM governance_issue
        WHERE id = :issue_id
    """
    row = conn.execute(text(sql), {"issue_id": issue_id}).mappings().first()
    return dict(row) if row else None


def get_issue_timeline(conn: Connection, issue_id: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, issue_id AS issueId, action, actor, detail,
               DATE_FORMAT(occurred_at, '%Y-%m-%d %H:%i:%s') AS occurredAt
        FROM issue_timeline
        WHERE issue_id = :issue_id
        ORDER BY occurred_at ASC, id ASC
    """
    return [dict(r) for r in conn.execute(text(sql), {"issue_id": issue_id}).mappings()]


def get_ai_quota_status(conn: Connection) -> Dict[str, Any]:
    """Retrieve today's AI quota ledger and status."""
    today = datetime.now(timezone.utc).date()
    sql = """
        SELECT stat_date, call_count, neurons_used, status, updated_at
        FROM sim_ai_quota_ledger
        WHERE stat_date = :today
    """
    row = conn.execute(text(sql), {"today": today}).mappings().first()
    daily_limit = 3000.0
    if not row:
        return {
            "statDate": today.isoformat(),
            "callCount": 0,
            "neuronsUsed": 0.0,
            "dailyLimit": daily_limit,
            "remainingNeurons": daily_limit,
            "usagePct": 0.0,
            "status": "ACTIVE",
        }

    used = float(row["neurons_used"])
    return {
        "statDate": str(row["stat_date"]),
        "callCount": int(row["call_count"]),
        "neuronsUsed": round(used, 2),
        "dailyLimit": daily_limit,
        "remainingNeurons": max(0.0, round(daily_limit - used, 2)),
        "usagePct": min(100.0, round((used / daily_limit) * 100, 2)),
        "status": str(row["status"]),
    }


def get_recent_governance_activities(conn: Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent issue timeline activities across all issues for live broadcast ticker."""
    sql = """
        SELECT t.id, t.issue_id AS issueId, t.action, t.actor, t.detail,
               DATE_FORMAT(t.occurred_at, '%H:%i:%s') AS timeStr,
               DATE_FORMAT(t.occurred_at, '%Y-%m-%d %H:%i:%s') AS occurredAt,
               i.unit_name AS unitName, i.province, i.issue_type AS issueType, i.status
        FROM issue_timeline t
        JOIN governance_issue i ON t.issue_id = i.id
        ORDER BY t.occurred_at DESC, t.id DESC
        LIMIT :limit
    """
    return [dict(r) for r in conn.execute(text(sql), {"limit": limit}).mappings()]

