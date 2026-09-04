"""Read-only builders for dashboard sections that must share the live snapshot date."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _rows(conn: Connection, sql: str, params: dict | None = None) -> list[dict]:
    return [_numbers(dict(row)) for row in conn.execute(text(sql), params or {}).mappings()]


def _numbers(value):
    """Convert database decimals to JSON-native numbers throughout a payload."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_numbers(item) for item in value]
    return value


def build_construction_summary(conn: Connection) -> dict:
    totals = _numbers(dict(conn.execute(text("""
        SELECT
            COUNT(*) AS totalTasks,
            SUM(status = '已完成') AS completedTasks,
            SUM(status = '进行中') AS inProgressTasks,
            SUM(status = '未开始') AS notStartedTasks,
            ROUND(AVG(progress), 1) AS avgProgress
        FROM construction_task
    """)).mappings().one()))
    stages = _rows(conn, """
        SELECT
            type AS name,
            COUNT(*) AS total,
            SUM(status = '已完成') AS completed,
            SUM(status = '进行中') AS inProgress,
            SUM(status = '未开始') AS notStarted,
            ROUND(AVG(progress), 1) AS avgProgress
        FROM construction_task
        GROUP BY type
        ORDER BY MIN(id)
    """)
    training_totals = _numbers(dict(conn.execute(text("""
        SELECT COUNT(*) AS totalSessions, COALESCE(SUM(expected), 0) AS totalExpected,
               COALESCE(SUM(actual), 0) AS totalActual, COALESCE(SUM(passed), 0) AS totalPassed,
               COALESCE(SUM(cert_count), 0) AS totalCert
        FROM training
    """)).mappings().one()))
    training_totals["byType"] = _rows(conn, """
        SELECT type, COUNT(*) AS count, SUM(expected) AS expected, SUM(actual) AS actual,
               SUM(passed) AS passed, SUM(cert_count) AS cert
        FROM training
        GROUP BY type
        ORDER BY COUNT(*) DESC, type
    """)
    readiness = _numbers(dict(conn.execute(text("""
        SELECT COUNT(*) AS total,
               SUM(overall_status = '已导入') AS imported,
               SUM(overall_status = '校验通过') AS verified,
               SUM(overall_status = '收集中') AS collecting,
               SUM(overall_status = '未收集') AS notCollected
        FROM data_readiness
    """)).mappings().one()))
    return {
        **totals,
        "taskStages": stages,
        "trainingSummary": training_totals,
        "dataReadinessSummary": readiness,
    }


def build_issue_sections(conn: Connection, anchor_date: str | None = None) -> tuple[dict, list[dict]]:
    params = {"anchor_date": anchor_date} if anchor_date else {}
    max_issue_date = (
        "(SELECT MAX(date) FROM issue_metric_snapshot WHERE date <= :anchor_date)"
        if anchor_date else "(SELECT MAX(date) FROM issue_metric_snapshot)"
    )
    max_risk_date = (
        "(SELECT MAX(date) FROM risk_metric_snapshot WHERE date <= :anchor_date)"
        if anchor_date else "(SELECT MAX(date) FROM risk_metric_snapshot)"
    )
    totals = _numbers(dict(conn.execute(text(f"""
        SELECT DATE_FORMAT(MAX(date), '%Y-%m-%d') AS latestDate,
               SUM(total) AS totalIssues, SUM(resolved) AS totalResolved,
               SUM(unresolved) AS totalUnresolved
        FROM issue_metric_snapshot
        WHERE date = {max_issue_date}
    """), params).mappings().one()))
    risks = _numbers(dict(conn.execute(text(f"""
        SELECT SUM(high) AS highRisk, SUM(medium) AS mediumRisk, SUM(low) AS lowRisk
        FROM risk_metric_snapshot
        WHERE date = {max_risk_date}
    """), params).mappings().one()))
    by_stage = _rows(conn, f"""
        SELECT stage, SUM(bug) AS bug, SUM(req) AS req, SUM(conf) AS conf,
               SUM(data) AS data, SUM(integ) AS integ, SUM(op) AS op,
               SUM(total) AS total, SUM(resolved) AS resolved, SUM(unresolved) AS unresolved
        FROM issue_metric_snapshot
        WHERE date = {max_issue_date}
        GROUP BY stage
        ORDER BY stage
    """, params)
    issue_batches = _rows(conn, f"""
        SELECT bn.id AS batchId, bn.name, COALESCE(SUM(i.unresolved), 0) AS unresolved
        FROM (
            SELECT 1 AS id, '第一批' AS name UNION ALL
            SELECT 2, '第二批' UNION ALL
            SELECT 3, '第三批' UNION ALL
            SELECT 4, '第四批' UNION ALL
            SELECT 5, '第五批' UNION ALL
            SELECT 6, '第六批' UNION ALL
            SELECT 7, '第七批' UNION ALL
            SELECT 8, '第八批'
        ) bn
        LEFT JOIN issue_metric_snapshot i ON i.batch_id = bn.id AND i.date = {max_issue_date}
        GROUP BY bn.id, bn.name
        ORDER BY bn.id
    """, params)
    risk_batches = {
        row["batchId"]: row
        for row in _rows(conn, f"""
            SELECT bn.id AS batchId, COALESCE(SUM(r.high), 0) AS high,
                   COALESCE(SUM(r.medium), 0) AS medium, COALESCE(SUM(r.low), 0) AS low
            FROM (
                SELECT 1 AS id, '第一批' AS name UNION ALL
                SELECT 2, '第二批' UNION ALL
                SELECT 3, '第三批' UNION ALL
                SELECT 4, '第四批' UNION ALL
                SELECT 5, '第五批' UNION ALL
                SELECT 6, '第六批' UNION ALL
                SELECT 7, '第七批' UNION ALL
                SELECT 8, '第八批'
            ) bn
            LEFT JOIN risk_metric_snapshot r ON r.batch_id = bn.id AND r.date = {max_risk_date}
            GROUP BY bn.id, bn.name
            ORDER BY bn.id
        """, params)
    }
    return compose_issue_sections(totals, risks, by_stage, issue_batches, risk_batches)


def compose_issue_sections(
    totals: dict,
    risks: dict,
    by_stage: list[dict],
    issue_batches: list[dict],
    risk_batches: dict,
) -> tuple[dict, list[dict]]:
    """Compose issue payloads from same-date aggregates without invented records."""
    by_batch = []
    issues = []
    for batch in issue_batches:
        risk = risk_batches.get(batch["batchId"], {})
        item = {
            **batch,
            "high": risk.get("high", 0),
            "medium": risk.get("medium", 0),
            "low": risk.get("low", 0),
        }
        by_batch.append(item)
        status = "待处置" if item["high"] else ("跟踪中" if item["unresolved"] else "正常")
        title = (
            f"{item['name']}·风险预警（高风险 {item['high']} 项）"
            if item["high"]
            else (
                f"{item['name']}·问题跟踪（未解决 {item['unresolved']} 项）"
                if item["unresolved"]
                else f"{item['name']}·筹备期平稳（无阻断性风险）"
            )
        )
        issues.append({
            "type": "风险预警" if item["high"] else "业务质量",
            "level": "高" if item["high"] else ("中" if item["medium"] else "低"),
            "title": title,
            "area": "全国跨省",
            "owner": "项目质量组",
            "due": "",
            "status": status,
            "leadershipAttention": bool(item["high"]),
            "orgName": item["name"],
        })
    total_issues = totals.get("totalIssues") or 0
    totals["closeRate"] = round((totals.get("totalResolved") or 0) * 100 / total_issues, 2) if total_issues else 0
    summary = {**totals, **risks, "byStage": by_stage, "byBatch": by_batch}
    return _numbers(summary), issues


def build_entities(conn: Connection, updated_at: str, anchor_date: str | None = None) -> list[dict]:
    rows = _rows(conn, """
        WITH batch_mapped AS (
            SELECT 
                o.id,
                o.name,
                o.region,
                o.status,
                CASE
                    WHEN o.status = '稳定运行' AND o.id <= 150 THEN 1
                    WHEN o.status = '稳定运行' AND o.id <= 330 THEN 2
                    WHEN o.status = '稳定运行' THEN 3
                    WHEN o.status = '已上线' AND o.id <= 580 THEN 4
                    WHEN o.status = '已上线' THEN 5
                    WHEN o.status = '双轨运行中' THEN 6
                    WHEN o.id > 1600 THEN 7
                    ELSE 8
                END AS batchId
            FROM org_unit o
        ),
        batch_names AS (
            SELECT 1 AS id, '第一批' AS name UNION ALL
            SELECT 2, '第二批' UNION ALL
            SELECT 3, '第三批' UNION ALL
            SELECT 4, '第四批' UNION ALL
            SELECT 5, '第五批' UNION ALL
            SELECT 6, '第六批' UNION ALL
            SELECT 7, '第七批' UNION ALL
            SELECT 8, '第八批'
        ),
        task_agg AS (
            SELECT org_id, ROUND(AVG(progress), 1) AS construction
            FROM construction_task GROUP BY org_id
        ),
        owners AS (
            SELECT org_id, name,
                   ROW_NUMBER() OVER (PARTITION BY org_id ORDER BY
                       CASE WHEN job = '财务总监' THEN 1 WHEN role = '项目经理' THEN 2 ELSE 3 END, id) AS rn
            FROM sys_user
        )
        SELECT o.id, o.name, o.region, bm.batchId, bn.name AS batch,
               COALESCE(ow.name, '未配置') AS owner, o.status AS rawStatus,
               COALESCE(t.construction, 0) AS construction,
               CAST(REPLACE(COALESCE(d.opening_rate, '0'), '%', '') AS DECIMAL(5,1)) AS openingData
        FROM org_unit o
        JOIN batch_mapped bm ON bm.id = o.id
        JOIN batch_names bn ON bn.id = bm.batchId
        LEFT JOIN task_agg t ON t.org_id = o.id
        LEFT JOIN data_readiness d ON d.org_id = o.id
        LEFT JOIN owners ow ON ow.org_id = o.id AND ow.rn = 1
        ORDER BY o.id
    """)
    status_mapping = {
        "双轨运行中": "双轨运行",
        "稳定运行": "已上线",
        "已具备双轨条件": "准备中",
        "未启动": "准备中",
    }
    for row in rows:
        row["province"] = _normalize_region(row.pop("region"))
        raw_status = row.pop("rawStatus")
        if row["batchId"] == 8:
            row["status"] = "未启动"
            row["construction"] = 0.0
            row["openingData"] = 0.0
        else:
            row["status"] = status_mapping.get(raw_status, raw_status)
        row["voucherRate"] = None
        row["updatedAt"] = updated_at
    return rows


def _normalize_region(value: str) -> str:
    for suffix in ('特别行政区', '壮族自治区', '回族自治区', '维吾尔自治区', '自治区', '省', '市'):
        if value.endswith(suffix):
            return value[:-len(suffix)]
    return value
