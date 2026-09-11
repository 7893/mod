"""Read-only builders for dashboard sections that must share the live snapshot date."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..business_rules import (
    DISPLAY_STATUS_MAPPING,
    LAST_ACTIVE_BATCH_ID,
    ORG_STATUS_NOT_STARTED,
    SQL_INFERRED_BATCH_ID,
)


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
    rows = _rows(conn, f"""
        WITH batch_mapped AS (
            SELECT 
                o.id,
                o.name,
                o.region,
                o.status,
                {SQL_INFERRED_BATCH_ID} AS batchId
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
        ),
        dual_agg AS (
            SELECT org_id,
                   ROUND(100.0 * SUM(CASE WHEN result = '一致' THEN 1 ELSE 0 END) / COUNT(*), 1) AS dual_rate
            FROM dual_run_result
            WHERE check_date <= CURRENT_DATE()
            GROUP BY org_id
        )
        SELECT o.id, o.name, o.region, bm.batchId, bn.name AS batch,
               COALESCE(ow.name, '未配置') AS owner, o.status AS rawStatus,
               COALESCE(t.construction, 0) AS construction,
               CAST(REPLACE(COALESCE(d.opening_rate, '0'), '%', '') AS DECIMAL(5,1)) AS openingData,
               d.overall_status AS readinessStatus,
               dr.dual_rate AS voucherRate
        FROM org_unit o
        JOIN batch_mapped bm ON bm.id = o.id
        JOIN batch_names bn ON bn.id = bm.batchId
        LEFT JOIN task_agg t ON t.org_id = o.id
        LEFT JOIN data_readiness d ON d.org_id = o.id
        LEFT JOIN owners ow ON ow.org_id = o.id AND ow.rn = 1
        LEFT JOIN dual_agg dr ON dr.org_id = o.id
        ORDER BY o.id
    """)
    for row in rows:
        row["province"] = _normalize_region(row.pop("region"))
        raw_status = row.pop("rawStatus")
        vr = row.get("voucherRate")
        if row.get("readinessStatus") == "校验通过":
            row["readinessStatus"] = "已校验"
        if row["batchId"] == 8:
            row["status"] = ORG_STATUS_NOT_STARTED
            row["construction"] = 0.0
            row["openingData"] = 0.0
            row["voucherRate"] = None
        else:
            row["status"] = DISPLAY_STATUS_MAPPING.get(raw_status, raw_status)
            row["voucherRate"] = float(vr) if vr is not None else None
        row["updatedAt"] = updated_at
    return rows


def _normalize_region(value: str) -> str:
    for suffix in ('特别行政区', '壮族自治区', '回族自治区', '维吾尔自治区', '自治区', '省', '市'):
        if value.endswith(suffix):
            return value[:-len(suffix)]
    return value


def compose_rule_based_alerts(rollout_rows: list[dict], voucher_success_pct: float | None) -> list[dict]:
    """由批次推进事实派生 A 屏规则告警，所有数字都来自 rollout_rows，不写死。

    - 双轨批次：dual > 0 且 launched == 0 的批次；
    - 已推进批次：batchId <= LAST_ACTIVE_BATCH_ID 且 launched > 0；
    - 在建批次：batchId <= LAST_ACTIVE_BATCH_ID 且 launched == 0 且 dual == 0；
    - 储备批次：batchId > LAST_ACTIVE_BATCH_ID。
    """
    def _n(row: dict, key: str) -> float:
        value = row.get(key)
        return float(value) if isinstance(value, (int, float, Decimal)) else 0.0

    def _names(rows: list[dict]) -> str:
        return "、".join(str(r.get("name") or f"第{r.get('batchId')}批") for r in rows)

    rows = sorted((r for r in rollout_rows if r.get("batchId") is not None), key=lambda r: int(r["batchId"]))
    dual_rows = [r for r in rows if _n(r, "dual") > 0 and _n(r, "launched") == 0]
    launched_rows = [r for r in rows if int(r["batchId"]) <= LAST_ACTIVE_BATCH_ID and _n(r, "launched") > 0]
    building_rows = [
        r for r in rows
        if int(r["batchId"]) <= LAST_ACTIVE_BATCH_ID and _n(r, "launched") == 0 and _n(r, "dual") == 0
    ]
    reserve_rows = [r for r in rows if int(r["batchId"]) > LAST_ACTIVE_BATCH_ID]

    alerts: list[dict] = []
    if dual_rows:
        dual_total = int(sum(_n(r, "dual") for r in dual_rows))
        dual_pct = round(
            sum(_n(r, "constructionPct") * _n(r, "total") for r in dual_rows)
            / max(sum(_n(r, "total") for r in dual_rows), 1.0),
            1,
        )
        alerts.append({
            "level": "INFO",
            "title": f"{_names(dual_rows)} {dual_total} 家单位处于双轨运行期",
            "detail": f"{_names(dual_rows)}共 {dual_total} 家单位并行双轨核对，建设完成度 {dual_pct}%，达标后转入正式上线。",
        })
    if launched_rows:
        total = int(sum(_n(r, "total") for r in launched_rows))
        launched = int(sum(_n(r, "launched") for r in launched_rows))
        pct = round(launched * 100.0 / total, 1) if total else 0.0
        voucher_text = f"，财务凭证入账率 {voucher_success_pct}%" if voucher_success_pct is not None else ""
        alerts.append({
            "level": "SUCCESS" if pct >= 50 else "WARNING",
            "title": f"{_names(launched_rows[:1])}至{_names(launched_rows[-1:])} {launched} 家单位已上线",
            "detail": f"已推进批次共 {total} 家单位，其中 {launched} 家已上线（{pct}%）{voucher_text}。",
        })
    if building_rows or reserve_rows:
        parts = []
        for r in building_rows:
            parts.append(f"{r.get('name')} {int(_n(r, 'total'))} 家在建单位平均进度 {_n(r, 'constructionPct'):.1f}%")
        for r in reserve_rows:
            parts.append(f"{r.get('name')} {int(_n(r, 'total'))} 家储备单位处于期初数据准备期")
        alerts.append({
            "level": "WARNING",
            "title": "在建与储备批次接口联调与数据准备督导",
            "detail": "，".join(parts) + "，需重点防范接口联调堵点。",
        })
    return alerts

