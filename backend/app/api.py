from __future__ import annotations

from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .config import get_settings
from .db import connection
from .schemas import Page

router = APIRouter(prefix="/api/v1")
_snapshot_cache: dict | None = None
_snapshot_cached_at = 0.0
_snapshot_lock = Lock()
_SNAPSHOT_TTL_SECONDS = 300


def numeric(value):
    """Return JSON numbers instead of Decimal strings from MySQL aggregates."""
    if value is None or isinstance(value, (int, float)):
        return value
    number = float(value)
    return int(number) if number.is_integer() else number


def mappings(conn: Connection, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(row) for row in conn.execute(text(sql), params or {}).mappings()]


@router.get("/health")
def health(conn: Connection = Depends(connection)) -> dict:
    row = conn.execute(text("SELECT DATABASE() db, @@session.time_zone tz, UTC_TIMESTAMP() now_utc")).mappings().one()
    return {"status": "ok", "database": row["db"], "session_timezone": row["tz"], "now_utc": row["now_utc"]}


@router.get("/dashboard/overview")
def overview(conn: Connection = Depends(connection)) -> dict:
    sql = """
    SELECT
      (SELECT COUNT(*) FROM org_unit) org_total,
      (SELECT COUNT(*) FROM rollout_unit_status WHERE status IN ('已上线','稳定运行')) launched,
      (SELECT COUNT(*) FROM rollout_unit_status WHERE status='双轨运行中') dual_run,
      (SELECT ROUND(100 * SUM(status='已完成') / COUNT(*), 1) FROM construction_task) construction_pct,
      (SELECT ROUND(100 * SUM(status IN ('生成成功','已集成')) / COUNT(*), 2) FROM accounting_voucher) voucher_success_pct,
      ((SELECT COUNT(*) FROM project_issue WHERE leadership_attention=1 AND status<>'已关闭') +
       (SELECT COUNT(*) FROM project_risk WHERE leadership_attention=1 AND status<>'已关闭')) leadership_attention,
      (SELECT COUNT(DISTINCT region_code) FROM org_unit) regions
    """
    result = dict(conn.execute(text(sql)).mappings().one())
    result["construction_pct"] = numeric(result["construction_pct"])
    result["voucher_success_pct"] = numeric(result["voucher_success_pct"])
    result["launched_pct"] = round(result["launched"] * 100 / result["org_total"], 1)
    return result


def build_dashboard_snapshot(conn: Connection) -> dict:
    overview_row = dict(conn.execute(text("""
      SELECT
        (SELECT COUNT(*) FROM org_unit) org_total,
        (SELECT COUNT(*) FROM rollout_unit_status WHERE status IN ('已上线','稳定运行')) launched,
        (SELECT COUNT(*) FROM rollout_unit_status WHERE status='双轨运行中') dual_run,
        (SELECT ROUND(100 * SUM(status='已完成') / COUNT(*), 1) FROM construction_task) construction_pct,
        (SELECT COUNT(*) FROM accounting_voucher) voucher_total,
        (SELECT ROUND(100 * SUM(status IN ('生成成功','已集成')) / COUNT(*), 2)
           FROM accounting_voucher) voucher_success_pct,
        ((SELECT COUNT(*) FROM project_issue WHERE leadership_attention=1 AND status<>'已关闭') +
         (SELECT COUNT(*) FROM project_risk WHERE leadership_attention=1 AND status<>'已关闭'))
           leadership_attention,
        (SELECT COUNT(DISTINCT region_code) FROM org_unit) regions
    """)).mappings().one())
    overview_row["launched_pct"] = round(
        overview_row["launched"] * 100 / overview_row["org_total"], 1
    )
    overview_row["construction_pct"] = numeric(overview_row["construction_pct"])
    overview_row["voucher_success_pct"] = numeric(overview_row["voucher_success_pct"])

    rollout_rows = mappings(conn, """
      SELECT b.name name, COUNT(*) total,
             ROUND(100 * SUM(s.status IN ('已上线','稳定运行')) / COUNT(*), 1) launched_pct,
             ROUND(AVG(t.progress_pct), 1) construction_pct
      FROM rollout_batch b
      JOIN org_unit o ON o.batch_id=b.batch_id
      JOIN rollout_unit_status s ON s.org_id=o.org_id
      LEFT JOIN (
        SELECT org_id, AVG(progress_pct) progress_pct FROM construction_task GROUP BY org_id
      ) t ON t.org_id=o.org_id
      GROUP BY b.batch_id,b.name ORDER BY b.batch_id
    """)

    trend_rows = mappings(conn, """
      SELECT DATE_FORMAT(date, '%m-%d') date,
             SUM(status IN ('已上线','稳定运行')) launched
      FROM rollout_status_snapshot
      GROUP BY date ORDER BY date DESC LIMIT 7
    """)
    trend_rows.reverse()

    entity_rows = mappings(conn, """
      SELECT o.org_id id,o.area province,o.org_name name,b.name batch,
             u.display_name owner,
             CASE
               WHEN s.status IN ('已上线','稳定运行') THEN '已上线'
               WHEN s.status IN ('双轨运行中','具备双轨条件') THEN '双轨运行'
               WHEN s.status IN ('未启动','准备中','暂缓','不具备条件') THEN '准备中'
               ELSE '建设中'
             END status,
             ROUND(COALESCE(t.construction,0),1) construction,
             ROUND(COALESCE(d.opening_data,0),1) opening_data,
             ROUND(COALESCE(v.voucher_rate,0),2) voucher_rate,
             DATE_FORMAT(s.updated_at_utc,'%Y-%m-%d %H:%i') updated_at
      FROM org_unit o
      JOIN rollout_batch b ON b.batch_id=o.batch_id
      JOIN sys_user u ON u.user_id=o.owner_id
      JOIN rollout_unit_status s ON s.org_id=o.org_id
      LEFT JOIN (
        SELECT org_id,AVG(progress_pct) construction FROM construction_task GROUP BY org_id
      ) t ON t.org_id=o.org_id
      LEFT JOIN (
        SELECT org_id,AVG(completeness_pct) opening_data
        FROM data_readiness WHERE data_class='期初数据' GROUP BY org_id
      ) d ON d.org_id=o.org_id
      LEFT JOIN (
        SELECT org_id,100 * AVG(status IN ('生成成功','已集成')) voucher_rate
        FROM accounting_voucher GROUP BY org_id
      ) v ON v.org_id=o.org_id
      ORDER BY o.org_id
    """)
    entities = [{
        "id": row["id"], "province": row["province"], "name": row["name"],
        "batch": row["batch"], "owner": row["owner"], "status": row["status"],
        "construction": numeric(row["construction"]),
        "openingData": numeric(row["opening_data"]),
        "voucherRate": numeric(row["voucher_rate"]), "updatedAt": row["updated_at"],
    } for row in entity_rows]

    issue_rows = mappings(conn, """
      SELECT * FROM (
        SELECT '问题' type,i.level,i.title,o.area area,u.display_name owner,
               DATE_FORMAT(i.due,'%Y-%m-%d') due,i.status,i.leadership_attention,
               o.org_name
        FROM project_issue i JOIN org_unit o USING(org_id)
        LEFT JOIN sys_user u ON u.user_id=i.owner_id
        UNION ALL
        SELECT '风险',r.level,r.title,o.area,u.display_name,
               DATE_FORMAT(r.due,'%Y-%m-%d'),r.status,r.leadership_attention,o.org_name
        FROM project_risk r JOIN org_unit o USING(org_id)
        LEFT JOIN sys_user u ON u.user_id=r.owner_id
      ) x
      ORDER BY status='已关闭',leadership_attention DESC,FIELD(level,'高','中','低'),due
    """)
    issues = [{
        "type": row["type"], "level": row["level"], "title": row["title"],
        "area": row["area"], "owner": row["owner"], "due": row["due"],
        "status": row["status"], "leadershipAttention": bool(row["leadership_attention"]),
        "orgName": row["org_name"],
    } for row in issue_rows]

    operation_tables = [
        "business_document", "business_document_line", "accounting_voucher",
        "accounting_voucher_line", "document_voucher_link", "integration_result",
        "dual_run_result",
    ]
    operations = {
        table: conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one()
        for table in operation_tables
    }
    all_tables = [
        "region", "rollout_batch", "calendar_date", "sys_user", "org_unit",
        "rollout_unit_status", "construction_task", "rollout_status_snapshot",
        "data_readiness", "opening_data_result", "business_document",
        "business_document_line", "accounting_voucher", "accounting_voucher_line",
        "document_voucher_link", "integration_result", "dual_run_result", "project_issue",
        "project_risk", "metric_snapshot", "source_record", "import_job", "import_error",
        "change_log",
    ]
    full_rows = sum(
        conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one()
        for table in all_tables
    )
    quality = dict(conn.execute(text("""
      SELECT
        (SELECT COUNT(*) FROM (
          SELECT voucher_id FROM accounting_voucher_line GROUP BY voucher_id
          HAVING ROUND(SUM(debit_amount-credit_amount),2)<>0
        ) balance_errors) voucher_balance_errors,
        (SELECT COUNT(*) FROM document_voucher_link l
          JOIN business_document d ON d.document_id=l.document_id
          JOIN accounting_voucher v ON v.voucher_id=l.voucher_id
          JOIN integration_result i ON i.voucher_id=v.voucher_id
          WHERE l.relation_type='主关联' AND (
            d.submitted_at_utc > d.approved_at_utc OR
            d.approved_at_utc > v.generated_at_utc OR
            v.generated_at_utc > i.completed_at_utc
          )) time_order_errors,
        (SELECT COUNT(*) FROM document_voucher_link l
          LEFT JOIN business_document d ON d.document_id=l.document_id
          LEFT JOIN accounting_voucher v ON v.voucher_id=l.voucher_id
          WHERE d.document_id IS NULL OR v.voucher_id IS NULL) orphan_link_errors,
        (SELECT COUNT(*) FROM (
          SELECT org_id FROM rollout_status_snapshot GROUP BY org_id HAVING COUNT(DISTINCT status)>=2
        ) progressing) organizations_with_status_progression
    """)).mappings().one())
    period = conn.execute(text(
        "SELECT DATE_FORMAT(MIN(full_date),'%Y-%m-%d'),"
        "DATE_FORMAT(MAX(full_date),'%Y-%m-%d') FROM calendar_date"
    )).one()

    return {
        "meta": {
            "mode": "S", "notice": "全部为虚构模拟数据", "seed": 20260830,
            "fullRows": full_rows, "sampleRows": full_rows,
            "period": [period[0], period[1]], "sourceTimezone": "UTC",
            "displayTimezone": get_settings().display_timezone,
        },
        "overview": {
            "orgTotal": overview_row["org_total"], "launched": overview_row["launched"],
            "launchedPct": overview_row["launched_pct"], "dual": overview_row["dual_run"],
            "constructionPct": overview_row["construction_pct"],
            "voucherTotal": overview_row["voucher_total"],
            "voucherSuccessPct": overview_row["voucher_success_pct"],
            "leadershipAttention": overview_row["leadership_attention"],
            "regions": overview_row["regions"],
        },
        "rollout": [{**row,
                     "launchedPct": numeric(row["launched_pct"]),
                     "constructionPct": numeric(row["construction_pct"])}
                    for row in rollout_rows],
        "trend": trend_rows,
        "entities": entities,
        "issues": issues,
        "operations": operations,
        "quality": quality,
    }


@router.get("/dashboard/snapshot")
def dashboard_snapshot(conn: Connection = Depends(connection)) -> dict:
    global _snapshot_cache, _snapshot_cached_at
    now = monotonic()
    with _snapshot_lock:
        if _snapshot_cache is not None and now - _snapshot_cached_at < _SNAPSHOT_TTL_SECONDS:
            return _snapshot_cache
        _snapshot_cache = build_dashboard_snapshot(conn)
        _snapshot_cached_at = monotonic()
        return _snapshot_cache


@router.get("/dashboard/rollout")
def rollout(conn: Connection = Depends(connection)) -> list[dict]:
    return mappings(conn, """
      SELECT b.batch_id, b.name, COUNT(*) total,
             SUM(s.status IN ('已上线','稳定运行')) launched,
             ROUND(100 * SUM(s.status IN ('已上线','稳定运行')) / COUNT(*), 1) launched_pct,
             ROUND(AVG(t.progress_pct), 1) construction_pct
      FROM rollout_batch b
      JOIN org_unit o ON o.batch_id=b.batch_id
      JOIN rollout_unit_status s ON s.org_id=o.org_id
      LEFT JOIN (SELECT org_id, AVG(progress_pct) progress_pct FROM construction_task GROUP BY org_id) t
        ON t.org_id=o.org_id
      GROUP BY b.batch_id, b.name ORDER BY b.batch_id
    """)


@router.get("/dashboard/trend")
def trend(days: int = Query(30, ge=7, le=180), conn: Connection = Depends(connection)) -> list[dict]:
    return mappings(conn, """
      SELECT date, SUM(status IN ('已上线','稳定运行')) launched,
             SUM(status='双轨运行中') dual_run
      FROM rollout_status_snapshot
      WHERE date >= (SELECT DATE_SUB(MAX(date), INTERVAL :days DAY) FROM rollout_status_snapshot)
      GROUP BY date ORDER BY date
    """, {"days": days - 1})


@router.get("/dashboard/regions")
def regions(conn: Connection = Depends(connection)) -> list[dict]:
    return mappings(conn, """
      SELECT o.region_code, o.area, COUNT(*) total,
             SUM(s.status IN ('已上线','稳定运行')) launched,
             SUM(s.status='双轨运行中') dual_run,
             ROUND(AVG(t.progress_pct),1) construction_pct
      FROM org_unit o JOIN rollout_unit_status s ON s.org_id=o.org_id
      LEFT JOIN (SELECT org_id, AVG(progress_pct) progress_pct FROM construction_task GROUP BY org_id) t
        ON t.org_id=o.org_id
      GROUP BY o.region_code, o.area ORDER BY o.region_code
    """)


@router.get("/organizations", response_model=Page)
def organizations(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    region_code: str | None = None, status: str | None = None, keyword: str | None = None,
    conn: Connection = Depends(connection),
) -> Page:
    where, params = ["1=1"], {}
    if region_code:
        where.append("o.region_code=:region_code")
        params["region_code"] = region_code
    if status:
        where.append("s.status=:status")
        params["status"] = status
    if keyword:
        where.append("(o.org_name LIKE :keyword OR o.org_code LIKE :keyword OR u.display_name LIKE :keyword)")
        params["keyword"] = f"%{keyword}%"
    clause = " AND ".join(where)
    total = conn.execute(text(f"SELECT COUNT(*) FROM org_unit o JOIN rollout_unit_status s USING(org_id) LEFT JOIN sys_user u ON u.user_id=o.owner_id WHERE {clause}"), params).scalar_one()
    params.update(limit=page_size, offset=(page - 1) * page_size)
    items = mappings(conn, f"""
      SELECT o.org_id, o.org_code, o.org_name, o.region_code, o.area, b.name,
             u.display_name owner, s.status, s.plan_date, s.actual_date, s.updated_at_utc,
             ROUND(AVG(t.progress_pct),1) construction_pct
      FROM org_unit o JOIN rollout_unit_status s USING(org_id)
      JOIN rollout_batch b USING(batch_id) LEFT JOIN sys_user u ON u.user_id=o.owner_id
      LEFT JOIN construction_task t ON t.org_id=o.org_id
      WHERE {clause}
      GROUP BY o.org_id, o.org_code, o.org_name, o.region_code, o.area, b.name,
               u.display_name, s.status, s.plan_date, s.actual_date, s.updated_at_utc
      ORDER BY o.org_id LIMIT :limit OFFSET :offset
    """, params)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/issues")
def issues(limit: int = Query(50, ge=1, le=500), conn: Connection = Depends(connection)) -> list[dict]:
    return mappings(conn, """
      SELECT * FROM (
        SELECT '问题' type, i.issue_id item_id, i.org_id, o.org_name, o.area,
               i.title, i.level, i.status, u.display_name owner, i.due, i.leadership_attention
        FROM project_issue i JOIN org_unit o USING(org_id) LEFT JOIN sys_user u ON u.user_id=i.owner_id
        UNION ALL
        SELECT '风险', r.risk_id, r.org_id, o.org_name, o.area,
               r.title, r.level, r.status, u.display_name, r.due, r.leadership_attention
        FROM project_risk r JOIN org_unit o USING(org_id) LEFT JOIN sys_user u ON u.user_id=r.owner_id
      ) x ORDER BY status='已关闭', leadership_attention DESC, FIELD(level,'高','中','低'), due LIMIT :limit
    """, {"limit": limit})


@router.get("/operations/summary")
def operations(conn: Connection = Depends(connection)) -> dict:
    names = ["business_document", "business_document_line", "accounting_voucher", "accounting_voucher_line", "document_voucher_link", "integration_result", "dual_run_result"]
    return {name: conn.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one() for name in names}


@router.get("/audit")
def audit(limit: int = Query(50, ge=1, le=500), conn: Connection = Depends(connection)) -> list[dict]:
    return mappings(conn, """
      SELECT c.change_id, c.changed_at_utc, o.org_name, u.display_name operator,
             c.table_name, c.field_name, c.before_value, c.after_value
      FROM change_log c JOIN org_unit o USING(org_id) LEFT JOIN sys_user u ON u.user_id=c.operator_id
      ORDER BY c.changed_at_utc DESC, c.change_id DESC LIMIT :limit
    """, {"limit": limit})
