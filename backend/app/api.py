from __future__ import annotations

from datetime import datetime
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .auth import get_current_action_token, verify_internal_auth
from .db import connection
from .ml_adapter import HeatWaveMLAdapter, CloudflareAIAdapter
from .schemas import PageV2
from .services.dashboard import (
    build_dashboard_snapshot_v2,
    load_fallback_snapshot as load_fallback_snapshot,
    normalize_operations_dict,
    normalize_region,
)

router = APIRouter(prefix="/api")

_snapshot_cache: dict | None = None
_snapshot_cached_at = 0.0
_snapshot_lock = Lock()
_SNAPSHOT_TTL_SECONDS = 60

_meta_cache: dict | None = None
_meta_cached_at = 0.0
_meta_lock = Lock()
_META_TTL_SECONDS = 60

@router.get("/health")
def health(conn: Connection | None = Depends(connection)) -> dict:
    if conn is None:
        return {
            "status": "degraded",
            "notice": "Database not reachable; operating in verified fallback snapshot mode",
        }
    try:
        row = conn.execute(text("SELECT DATABASE() db, @@session.time_zone tz, NOW() now_cst")).mappings().one()
        return {
            "status": "ok",
            "database": row["db"],
            "session_timezone": row["tz"],
            "now_cst": str(row["now_cst"]),
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}



@router.get("/dashboard/refresh-meta")
def refresh_meta(conn: Connection | None = Depends(connection)) -> dict:
    snap = dashboard_snapshot(conn)
    meta = snap.get("meta", {})
    
    # In fallback mode, conn will be None or dashboard_snapshot handles fallback internally.
    # To determine status correctly, we can rely on conn.
    status = "ok" if conn is not None else "fallback"
    data_version = "live" if conn is not None else "frozen"

    if conn is not None:
        try:
            # Just a quick check to see if DB is really alive
            conn.execute(text("SELECT 1")).scalar()
        except Exception:
            status = "fallback"
            data_version = "frozen"

    return {
        "data_version": data_version,
        "as_of_date": meta.get("asOfDate", "2026-08-30"),
        "last_updated_at": meta.get("generatedAt", datetime.now().isoformat()),
        "total_rows": meta.get("fullRows", 1685923),
        "status": status,
        "seed": meta.get("seed", 42),
    }


@router.get("/dashboard/snapshot")
def dashboard_snapshot(conn: Connection | None = Depends(connection)) -> dict:
    global _snapshot_cache, _snapshot_cached_at
    now = monotonic()
    with _snapshot_lock:
        if _snapshot_cache is not None and now - _snapshot_cached_at < _SNAPSHOT_TTL_SECONDS:
            return _snapshot_cache
        _snapshot_cache = build_dashboard_snapshot_v2(conn)
        _snapshot_cached_at = monotonic()
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


@router.get("/organizations", response_model=PageV2)
def organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    region: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    conn: Connection | None = Depends(connection),
) -> PageV2:
    snap = dashboard_snapshot(conn)
    entities = snap.get("entities", [])

    filtered = entities
    if region and region != "全部":
        norm_r = normalize_region(region)
        filtered = [e for e in filtered if e["province"] == norm_r or e["region"] == region]
    if status and status != "全部":
        filtered = [e for e in filtered if e["status"] == status or e.get("rawStatus") == status]
    if keyword:
        kw = keyword.lower()
        filtered = [
            e for e in filtered
            if kw in e["name"].lower() or kw in e["owner"].lower() or kw in e["province"].lower()
        ]

    total = len(filtered)
    start = (page - 1) * page_size
    items = filtered[start:start + page_size]
    return PageV2(items=items, total=total, page=page, page_size=page_size)


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

            target_models = base_insights.get("targetModels", [])
            for tm in target_models:
                if tm.get("type") == "REGRESSION":
                    tm["status"] = "READY" if reg_ok else ("VALIDATION_FAILED" if reg_quality is not None else "NOT_EVALUATED")
                    tm["algorithm"] = reg_info.get("algorithm", "HeatWave AutoML LinearRegression")
                    tm["quality"] = reg_quality  # 真实值或 None（前端显示"—"），不再硬编码
                elif tm.get("type") == "CLASSIFICATION":
                    tm["status"] = "READY" if cls_ok else ("VALIDATION_FAILED" if cls_quality is not None else "NOT_EVALUATED")
                    tm["algorithm"] = cls_info.get("algorithm", "HeatWave AutoML DecisionTreeClassifier")
                    tm["quality"] = cls_quality  # 真实值或 None，不再硬编码

        base_insights["action_token"] = get_current_action_token()
        return base_insights
    except Exception as e:
        snap = dashboard_snapshot(conn)
        base_insights = dict(snap.get("insights", {}))
        base_insights["hw_ml"] = {"status": "unavailable", "message": f"服务端错误：{e}"}
        base_insights["cf_ai"] = {"status": "unavailable", "message": "服务端错误，状态不可用"}
        base_insights["summary"] = f"研判引擎暂时不可用：{e}"
        base_insights["action_token"] = get_current_action_token()
        return base_insights


@router.get("/insights/risk-explanation/{org_id}")
def insights_risk_explanation(org_id: int, conn: Connection | None = Depends(connection)) -> dict:
    """
    返回指定单位的 HeatWave AutoML SHAP 风险归因与贡献分解。
    只读查询，零外部调用，物理数据不出库。
    """
    adapter = HeatWaveMLAdapter(conn)
    return adapter.explain_risk(org_id)


@router.post(
    "/insights/generate",
    dependencies=[Depends(verify_internal_auth)],
    responses={
        401: {"description": "未授权访问：高危外部调用接口需要有效的内部访问凭据"},
    },
)
def insights_generate(conn: Connection | None = Depends(connection)) -> dict:
    """
    主动触发 Cloudflare Workers AI 洞察生成。

    触发规则（按优先级）：
    - 缓存命中（相同指标指纹 + TTL 内）→ 直接返回缓存，status="cache_hit"
    - 每日限额已耗尽 → 返回 status="rate_limited"
    - 未启用 / 凭据缺失 / 过滤后无字段 → 安全降级
    - 以上均通过 → 发起真实 HTTP 请求，成功后更新缓存

    只有本接口会触发外部模型调用；GET /insights/status 和
    GET /insights/latest 均不产生外部请求。
    """
    try:
        cf_ai = CloudflareAIAdapter()
        snap = dashboard_snapshot(conn)
        overview_data: dict = snap.get("overview", {})
        return cf_ai.generate_insights(overview_data)
    except Exception as e:
        return {
            "status": "unavailable",
            "message": f"服务端错误，CF AI 未调用：{e}",
        }


@router.get("/insights/latest")
def insights_latest() -> dict:
    """
    返回最近一次成功调用的缓存洞察结果。

    此端点绝不触发任何外部请求。
    缓存为空时返回 {"status": "no_cache"}。
    缓存有效（TTL 内）或已过期均照常返回，前端可根据 generated_at 判断新鲜度。
    """
    try:
        cf_ai = CloudflareAIAdapter()
        return cf_ai.get_latest_cached_insights()
    except Exception as e:
        return {
            "status": "unavailable",
            "message": f"服务端错误：{e}",
        }


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
        return {"status": "no_briefing", "message": f"服务端错误：{e}"}


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

