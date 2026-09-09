from contextlib import suppress
import logging
import threading
from datetime import datetime
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .db import connection, get_engine
from .heatwave_watchdog import get_heatwave_status
from .ml_adapter import HeatWaveMLAdapter, CloudflareAIAdapter
from .schemas import Page
from .services.dashboard import (
    build_dashboard_snapshot,
    load_fallback_snapshot as load_fallback_snapshot,
    normalize_operations_dict,
    normalize_region,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

try:
    _snapshot_cache: dict | None = load_fallback_snapshot()
    _snapshot_source: str = "fallback"
except Exception:
    _snapshot_cache = None
    _snapshot_source = "none"

_snapshot_cached_at = 0.0
_snapshot_lock = Lock()
_snapshot_refreshing = False
_snapshot_refresh_started_at = 0.0
_snapshot_last_refreshed_at: str | None = None
_snapshot_last_refresh_duration_ms: float | None = None
_snapshot_last_error: str | None = None
_snapshot_last_failed_at = 0.0
_snapshot_consecutive_failures = 0
_SNAPSHOT_TTL_SECONDS = 60
_REFRESH_TIMEOUT_SECONDS = 20.0
_REFRESH_BACKOFF_SECONDS = 15.0

_meta_cache: dict | None = None
_meta_cached_at = 0.0
_meta_lock = Lock()
_META_TTL_SECONDS = 60


def _get_snapshot_health_info() -> dict:
    now = monotonic()
    is_stale = (_snapshot_source == "live") and (now - _snapshot_cached_at > _SNAPSHOT_TTL_SECONDS * 3)
    if _snapshot_source == "live":
        status_val = "stale" if is_stale else "ok"
    elif _snapshot_source == "fallback":
        status_val = "fallback"
    else:
        status_val = "none"

    refresh_status = "idle"
    if _snapshot_refreshing:
        refresh_status = "refreshing"
    elif _snapshot_last_error is not None:
        refresh_status = "error"

    return {
        "source": _snapshot_source,
        "status": status_val,
        "refresh_status": refresh_status,
        "last_refreshed_at": _snapshot_last_refreshed_at,
        "last_refresh_duration_ms": _snapshot_last_refresh_duration_ms,
        "last_error": _snapshot_last_error,
        "is_stale": is_stale,
        "consecutive_failures": _snapshot_consecutive_failures,
    }


@router.get(
    "/health",
    responses={
        200: {"description": "服务与数据库连接健康"},
        503: {"description": "数据库不可达或处于降级状态"},
    },
)
def health(response: Response, conn: Connection | None = Depends(connection)) -> dict:
    snap_info = _get_snapshot_health_info()
    if conn is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "degraded",
            "notice": "Database not reachable; operating in verified fallback snapshot mode",
            "snapshot": snap_info,
        }
    try:
        row = conn.execute(text("SELECT DATABASE() db, @@session.time_zone tz, NOW() now_cst")).mappings().one()
        hw = get_heatwave_status(conn)
        return {
            "status": "ok",
            "database": row["db"],
            "session_timezone": row["tz"],
            "now_cst": str(row["now_cst"]),
            "heatwave": hw,
            "snapshot": snap_info,
        }
    except Exception as e:
        logger.error("Health probe query failed: %s", e)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "degraded",
            "error": "Database health check failed",
            "snapshot": snap_info,
        }


@router.get("/dashboard/refresh-meta")
def refresh_meta(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    meta = snap.get("meta", {})

    now = monotonic()
    is_stale = (_snapshot_source == "live") and (now - _snapshot_cached_at > _SNAPSHOT_TTL_SECONDS * 3)

    if _snapshot_source == "live":
        meta_status = "stale" if is_stale else "ok"
        data_version = "live"
    else:
        meta_status = "fallback"
        data_version = "frozen"

    return {
        "data_version": data_version,
        "as_of_date": meta.get("asOfDate"),
        "last_updated_at": meta.get("generatedAt"),
        "total_rows": meta.get("fullRows"),
        "status": meta_status,
        "seed": meta.get("seed"),
    }


def _get_dedicated_connection() -> Connection | None:
    """为后台快照异步刷新创建独立连接，保证 CST 时区与 HeatWave 路由配置生效，并设置严格会话超时。"""
    try:
        conn = get_engine().connect()
        conn.execute(text("SET time_zone = '+08:00'"))
        conn.execute(text("SET use_secondary_engine = ON"))
        conn.execute(text("SET SESSION max_execution_time = 15000"))
        return conn
    except Exception as e:
        logger.warning("后台快照获取独立数据库连接失败: %s", e)
        return None


def _background_refresh_snapshot() -> None:
    """后台异步更新快照缓存工作线程，杜绝请求线程阻塞，具有严格超时与异常熔断保护。"""
    global _snapshot_cache, _snapshot_cached_at, _snapshot_refreshing, _snapshot_source
    global _snapshot_last_refreshed_at, _snapshot_last_refresh_duration_ms, _snapshot_last_error
    global _snapshot_last_failed_at, _snapshot_consecutive_failures
    t0 = monotonic()
    conn = None
    try:
        conn = _get_dedicated_connection()
        if conn is None:
            raise RuntimeError("Unable to acquire dedicated DB connection")
        snap = build_dashboard_snapshot(conn)
        duration_ms = round((monotonic() - t0) * 1000, 2)
        with _snapshot_lock:
            _snapshot_cache = snap
            _snapshot_cached_at = monotonic()
            _snapshot_source = "live"
            _snapshot_last_refreshed_at = datetime.now().isoformat()
            _snapshot_last_refresh_duration_ms = duration_ms
            _snapshot_last_error = None
            _snapshot_consecutive_failures = 0
        logger.info(
            "后台快照异步刷新就绪 (耗时: %.1fms, TTL: %ds, 纳管单位: %d)",
            duration_ms,
            _SNAPSHOT_TTL_SECONDS,
            len(snap.get("entities", [])),
        )
    except Exception as e:
        duration_ms = round((monotonic() - t0) * 1000, 2)
        err_msg = str(e)
        if "3024" in err_msg or "execution time exceeded" in err_msg.lower():
            err_category = "QueryTimeout"
        elif "connection" in err_msg.lower() or "2003" in err_msg:
            err_category = "ConnectionFailed"
        else:
            err_category = type(e).__name__
        with _snapshot_lock:
            _snapshot_last_failed_at = monotonic()
            _snapshot_consecutive_failures += 1
            _snapshot_last_error = f"{err_category}: 快照刷新超时或执行异常"
            _snapshot_last_refresh_duration_ms = duration_ms
        logger.error(
            "后台快照异步刷新异常 (耗时: %.1fms, 连续失败: %d): %s",
            duration_ms,
            _snapshot_consecutive_failures,
            err_category,
        )
    finally:
        if conn is not None:
            with suppress(Exception):
                conn.close()
        with _snapshot_lock:
            _snapshot_refreshing = False


def prewarm_snapshot(sync: bool = False) -> None:
    """快照预热入口，可在开机或需要时触发。"""
    global _snapshot_refreshing, _snapshot_refresh_started_at
    with _snapshot_lock:
        now = monotonic()
        if _snapshot_refreshing:
            if now - _snapshot_refresh_started_at < _REFRESH_TIMEOUT_SECONDS:
                return
            logger.warning("前次快照刷新已超过 %.1fs 未完成，强制重置刷新状态", _REFRESH_TIMEOUT_SECONDS)
        if _snapshot_consecutive_failures > 0 and (now - _snapshot_last_failed_at < _REFRESH_BACKOFF_SECONDS):
            return
        _snapshot_refreshing = True
        _snapshot_refresh_started_at = now
    if sync:
        _background_refresh_snapshot()
    else:
        threading.Thread(target=_background_refresh_snapshot, name="snapshot-prewarm", daemon=True).start()


@router.get("/dashboard/snapshot")
def dashboard_snapshot_endpoint(conn: Connection | None = Depends(connection)) -> dict:
    """
    获取数据大屏全景快照数据 (SWR Stale-While-Revalidate 保障全场景 < 1.0s SLA)。

    `meta.source` 如实标注本次返回的是真库快照（live）还是内置兜底（fallback），
    前端据此决定数据源徽标，而不是把任何 200 响应都当作真库数据。
    """
    snap = dashboard_snapshot(conn)
    return {**snap, "meta": {**snap.get("meta", {}), "source": _snapshot_source}}


def dashboard_snapshot(conn: Connection | None) -> dict:
    """SWR 缓存的快照读取：热缓存直接返回，过期则后台刷新，冷启动同步构建。"""
    global _snapshot_cache, _snapshot_cached_at, _snapshot_refreshing, _snapshot_refresh_started_at
    global _snapshot_source
    now = monotonic()

    # 1. 命中热缓存且未过期：极速微秒级返回 (~0.05ms)
    if _snapshot_cache is not None and (now - _snapshot_cached_at < _SNAPSHOT_TTL_SECONDS) and (_snapshot_source == "live"):
        return _snapshot_cache

    # 2. SWR 过期刷新或 fallback 升级：已有缓存立即返回，后台异步刷新，消除阻塞
    if _snapshot_cache is not None:
        with _snapshot_lock:
            should_refresh = False
            if not _snapshot_refreshing:
                if _snapshot_consecutive_failures == 0 or (now - _snapshot_last_failed_at >= _REFRESH_BACKOFF_SECONDS):
                    should_refresh = True
            elif now - _snapshot_refresh_started_at >= _REFRESH_TIMEOUT_SECONDS:
                logger.warning("SWR 发现前次刷新超时 (%.1fs)，重置并重新触发异步刷新", now - _snapshot_refresh_started_at)
                should_refresh = True

            if should_refresh:
                _snapshot_refreshing = True
                _snapshot_refresh_started_at = now
                threading.Thread(target=_background_refresh_snapshot, name="snapshot-swr", daemon=True).start()
        return _snapshot_cache

    # 3. 极冷冷启动（未预热且首次访问）：同步加锁计算并装载
    with _snapshot_lock:
        if _snapshot_cache is not None:
            return _snapshot_cache
        snap = build_dashboard_snapshot(conn)
        _snapshot_cache = snap
        _snapshot_cached_at = monotonic()
        _snapshot_source = "live" if conn is not None else "fallback"
        return _snapshot_cache


@router.get("/dashboard/overview")
def overview(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("overview", {})


@router.get("/dashboard/rollout")
def rollout(conn: Connection | None = Depends(connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    return snap.get("rollout", [])


@router.get("/dashboard/trend")
def trend(days: int = Query(7, ge=7, le=180), conn: Connection | None = Depends(connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    trend_data = snap.get("trend", [])
    if days and len(trend_data) > days:
        return trend_data[-days:]
    return trend_data


@router.get("/dashboard/regions")
def regions(conn: Connection | None = Depends(connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    return snap.get("provinces", [])


@router.get("/organizations", response_model=Page)
def organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    region: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    conn: Connection | None = Depends(connection),
) -> Page:
    snap = dashboard_snapshot(conn)
    entities = snap.get("entities", [])

    filtered = entities
    if region and region != "全部":
        norm_r = normalize_region(region)
        filtered = [e for e in filtered if e["province"] == norm_r or e["region"] == region]
    if status and status != "全部":
        filtered = [e for e in filtered if e["status"] == status]
    if keyword:
        kw = keyword.lower()
        filtered = [
            e for e in filtered
            if kw in e["name"].lower() or kw in e["owner"].lower() or kw in e["province"].lower()
        ]

    total = len(filtered)
    start = (page - 1) * page_size
    items = filtered[start:start + page_size]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/issues/summary")
def issues_summary(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("issuesSummary", {})


@router.get("/construction/summary")
def construction_summary(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("construction", {})



@router.get("/insights/status")
def insights_status(conn: Connection | None = Depends(connection)) -> dict:
    """
    返回 HeatWave 状态、Cloudflare AI 配置状态、基础研判元数据及预测状态。

    此端点绝不调用任何外部模型，也不触发 Cloudflare AI 请求。
    仅汇报各子系统的配置与运行状态，供前端轮询或监控使用。
    """
    try:
        hw_ml = HeatWaveMLAdapter(conn)
        cf_ai = CloudflareAIAdapter()

        hw_status = hw_ml.get_status()   # 只读 HeatWave 元数据，无外部调用
        predictions = hw_ml.get_predictions()
        cf_status = cf_ai.get_status() if hasattr(cf_ai, "get_status") else {"status": "unavailable"}

        snap = dashboard_snapshot(conn)
        base_insights = dict(snap.get("insights", {}))

        base_insights["hw_ml"] = hw_status
        base_insights["predictions"] = predictions
        base_insights["cf_ai"] = cf_status

        # 为 useAiInsights.ts 设置顶层状态与额度
        top_cf_status = cf_status.get("status", "unavailable")
        base_insights["status"] = "ok" if top_cf_status == "ready" else top_cf_status
        base_insights["quota_remaining"] = cf_status.get("quota", {}).get("remaining_today", 20)
        base_insights["quota_reset_at"] = "UTC 00:00"

        # 动态更新 AutoML 运行与就绪状态
        if hw_status.get("status") == "ready":
            models_info = hw_status.get("models", {})
            reg_info = models_info.get("regression", {})
            cls_info = models_info.get("classifier", {})

            # 真实性判定（两层）：
            # 1) 有无真实评估分（quality is not None）——无则"训练/评分未完成"。
            # 2) 真实分是否达到"有意义"阈值——回归 R² 须 > 0（至少优于用均值瞎猜），
            #    分类 accuracy 须在 (0, 1) 且非退化；否则视为"验证未达标"，不得对外称"可提供预测"。
            reg_quality = reg_info.get("quality")
            cls_quality = cls_info.get("quality")

            def _model_effective(task: str, q) -> bool:
                if q is None:
                    return False
                if task == "regression":
                    return q > 0.0  # 负或零 R² 说明无预测能力
                # classification: 退化的 1.0（数据过度可分）与 <=0.5 均不作为可信预测对外展示
                return 0.5 < q < 1.0

            reg_ok = _model_effective("regression", reg_quality)
            cls_ok = _model_effective("classification", cls_quality)
            has_real_quality = reg_quality is not None or cls_quality is not None
            any_effective = reg_ok or cls_ok

            if any_effective:
                base_insights["automlStatus"] = "READY"
                base_insights["automlStatusDisplay"] = "已就绪"
                base_insights["trainingAuthorized"] = True
                base_insights["notice"] = "Oracle HeatWave AutoML 库内模型已完成训练与独立测试集验证，提供通过验证的预测。"
                base_insights["summary"] = "Oracle MySQL HeatWave AutoML 库内预测已激活（仅展示通过验证的模型）。"
            elif has_real_quality:
                base_insights["automlStatus"] = "VALIDATION_FAILED"
                base_insights["automlStatusDisplay"] = "已训练，验证未达标"
                base_insights["trainingAuthorized"] = False
                base_insights["notice"] = "模型已在独立测试集上评估，但真实泛化指标未达可信阈值（回归 R²≤0 或分类退化），暂不作为可信预测对外提供。"
                base_insights["summary"] = "模型已训练并经测试集验证，但泛化能力未达标，暂不展示为可信预测。"
            else:
                base_insights["automlStatus"] = "NOT_EVALUATED"
                base_insights["automlStatusDisplay"] = "训练/评分未完成"
                base_insights["trainingAuthorized"] = False
                base_insights["notice"] = "HeatWave AutoML 特征表已就绪，模型训练与评估尚未完成；暂不提供可信预测质量。"
                base_insights["summary"] = "AutoML 特征已建立，训练/评分未完成，暂无可信模型质量。"

        return base_insights
    except Exception as e:
        logger.error("Failed to load insights status: %s", e, exc_info=True)
        snap = dashboard_snapshot(conn)
        base_insights = dict(snap.get("insights", {}))
        base_insights["hw_ml"] = {"status": "unavailable", "message": "服务端错误，状态不可用"}
        base_insights["cf_ai"] = {"status": "unavailable", "message": "服务端错误，状态不可用"}
        base_insights["summary"] = "研判引擎暂时不可用"
        return base_insights


@router.get("/insights/risk-explanation/{org_id}")
def insights_risk_explanation(org_id: int, conn: Connection | None = Depends(connection)) -> dict:
    """
    返回指定单位的可用风险解释，并通过 explanationSource 明确区分
    HeatWave 原生 SHAP、真实特征规则降级或不可用；只读查询，零外部调用。
    """
    adapter = HeatWaveMLAdapter(conn)
    return adapter.explain_risk(org_id)


@router.get("/insights/briefing")
def insights_briefing(conn: Connection | None = Depends(connection)) -> dict:
    """
    返回最新一条每日指挥部决策简报（只读，零外部请求）。
    由后台定时任务生成入库，大屏直接展示；无简报时返回 status=no_briefing。
    """
    try:
        from .services.daily_briefing import get_latest
        return get_latest(conn)
    except Exception as e:
        logger.error("Failed to fetch briefing: %s", e, exc_info=True)
        return {"status": "no_briefing", "message": "服务端错误，暂无可用简报"}



@router.get("/operations/summary")
def operations_summary(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return normalize_operations_dict(snap.get("operations", {}))


# ===== Business Simulator APIs =====

@router.get("/simulator/status")
async def simulator_status() -> dict:
    """
    获取独立常驻拟真引擎运行状态与健康心跳（只读）。

    安全说明：
    - 读取独立常驻进程（mod-simulator.service）输出的结构化心跳文件。
    - 不导入 simulation 包，不导入 business_simulator，不创建任何写库连接或引擎。
    - 不执行任何子进程或外部命令。
    - 字段白名单过滤，不泄露系统绝对路径或凭据。
    """
    from .services.simulator_status import read_simulator_status

    try:
        return read_simulator_status()
    except PermissionError:
        raise HTTPException(
            status_code=503,
            detail="Simulator status temporarily unavailable",
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Simulator status temporarily unavailable",
        )


# ===== Governance Issues & Lifecycle APIs =====

@router.get("/governance/issues")
def governance_issues_list(
    status: str | None = None,
    batch_id: int | None = None,
    issue_type: str | None = None,
    unit_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    conn: Connection | None = Depends(connection),
) -> dict:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import list_governance_issues
    return list_governance_issues(
        conn,
        status=status,
        batch_id=batch_id,
        issue_type=issue_type,
        unit_id=unit_id,
        page=page,
        page_size=page_size,
    )


@router.get("/governance/issues/{issue_id}")
def governance_issue_detail(
    issue_id: str,
    conn: Connection | None = Depends(connection),
) -> dict:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import get_governance_issue
    issue = get_governance_issue(conn, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.get("/governance/issues/{issue_id}/timeline")
def governance_issue_timeline(
    issue_id: str,
    conn: Connection | None = Depends(connection),
) -> list[dict]:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import get_issue_timeline
    return get_issue_timeline(conn, issue_id)


@router.post("/governance/issues/{issue_id}/dispatch")
def governance_issue_dispatch(
    issue_id: str,
    conn: Connection | None = Depends(connection),
) -> dict:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import dispatch_issue
    updated = dispatch_issue(conn, issue_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found")
    return updated


@router.get("/governance/ai-quota")
def governance_ai_quota(
    conn: Connection | None = Depends(connection),
) -> dict:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import get_ai_quota_status
    return get_ai_quota_status(conn)


@router.post("/governance/issues/{issue_id}/enrich")
def governance_issue_enrich(
    issue_id: str,
    conn: Connection | None = Depends(connection),
) -> dict:
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import enrich_governance_issue
    updated = enrich_governance_issue(conn, issue_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found")
    return updated


@router.get("/governance/recent-activities")
def governance_recent_activities(
    limit: int = 10,
    conn: Connection | None = Depends(connection),
) -> list[dict]:
    """Retrieve recent governance timeline activities for live broadcast ticker."""
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    from .services.governance import get_recent_governance_activities
    return get_recent_governance_activities(conn, limit=min(max(1, limit), 50))
