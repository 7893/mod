from __future__ import annotations

from datetime import datetime
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .db import v2_connection
from .ml_adapter import HeatWaveMLAdapter, CloudflareAIAdapter
from .schemas_v2 import PageV2
from .services.dashboard_v2 import (
    build_dashboard_snapshot_v2,
    load_fallback_snapshot as load_fallback_snapshot,
    normalize_operations_dict,
    normalize_region,
)

router = APIRouter(prefix="/api/v2")

_snapshot_cache: dict | None = None
_snapshot_cached_at = 0.0
_snapshot_lock = Lock()
_SNAPSHOT_TTL_SECONDS = 60

_meta_cache: dict | None = None
_meta_cached_at = 0.0
_meta_lock = Lock()
_META_TTL_SECONDS = 60

@router.get("/health")
def health(conn: Connection | None = Depends(v2_connection)) -> dict:
    if conn is None:
        return {
            "status": "degraded",
            "version": "v2",
            "notice": "Database not reachable; operating in verified fallback snapshot mode",
        }
    try:
        row = conn.execute(text("SELECT DATABASE() db, @@session.time_zone tz, NOW() now_cst")).mappings().one()
        return {
            "status": "ok",
            "version": "v2",
            "database": row["db"],
            "session_timezone": row["tz"],
            "now_cst": str(row["now_cst"]),
        }
    except Exception as e:
        return {"status": "degraded", "version": "v2", "error": str(e)}



@router.get("/dashboard/refresh-meta")
def refresh_meta(conn: Connection | None = Depends(v2_connection)) -> dict:
    snap = dashboard_snapshot(conn)
    meta = snap.get("meta", {})
    
    # In fallback mode, conn will be None or dashboard_snapshot handles fallback internally.
    # To determine status correctly, we can rely on conn.
    status = "ok" if conn is not None else "fallback"
    data_version = "v2.0-live" if conn is not None else "v2.0-frozen"

    if conn is not None:
        try:
            # Just a quick check to see if DB is really alive
            conn.execute(text("SELECT 1")).scalar()
        except Exception:
            status = "fallback"
            data_version = "v2.0-frozen"

    return {
        "data_version": data_version,
        "as_of_date": meta.get("asOfDate", "2026-08-30"),
        "last_updated_at": meta.get("generatedAt", datetime.now().isoformat()),
        "total_rows": meta.get("fullRows", 1685923),
        "status": status,
        "seed": meta.get("seed", 42),
    }


@router.get("/dashboard/snapshot")
def dashboard_snapshot(conn: Connection | None = Depends(v2_connection)) -> dict:
    global _snapshot_cache, _snapshot_cached_at
    now = monotonic()
    with _snapshot_lock:
        if _snapshot_cache is not None and now - _snapshot_cached_at < _SNAPSHOT_TTL_SECONDS:
            return _snapshot_cache
        _snapshot_cache = build_dashboard_snapshot_v2(conn)
        _snapshot_cached_at = monotonic()
        return _snapshot_cache


@router.get("/dashboard/overview")
def overview(conn: Connection | None = Depends(v2_connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("overview", {})


@router.get("/dashboard/rollout")
def rollout(conn: Connection | None = Depends(v2_connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    return snap.get("rollout", [])


@router.get("/dashboard/trend")
def trend(days: int = Query(7, ge=7, le=180), conn: Connection | None = Depends(v2_connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    trend_data = snap.get("trend", [])
    if days and len(trend_data) > days:
        return trend_data[-days:]
    return trend_data


@router.get("/dashboard/regions")
def regions(conn: Connection | None = Depends(v2_connection)) -> list[dict]:
    snap = dashboard_snapshot(conn)
    return snap.get("provinces", [])


@router.get("/organizations", response_model=PageV2)
def organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    region: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    conn: Connection | None = Depends(v2_connection),
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
def issues_summary(conn: Connection | None = Depends(v2_connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("issuesSummary", {})


@router.get("/construction/summary")
def construction_summary(conn: Connection | None = Depends(v2_connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return snap.get("construction", {})



@router.get("/insights/status")
def insights_status(conn: Connection | None = Depends(v2_connection)) -> dict:
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

            # 真实性判定：只有当模型返回了真实评估质量分时，才视为"已就绪、可展示预测能力"。
            # 无真实质量分（quality=None）说明训练/评分未真正完成，不得谎报"已就绪/实时预测"。
            reg_quality = reg_info.get("quality")
            cls_quality = cls_info.get("quality")
            has_real_quality = reg_quality is not None or cls_quality is not None

            if has_real_quality:
                base_insights["automlStatus"] = "READY"
                base_insights["automlStatusDisplay"] = "已就绪"
                base_insights["trainingAuthorized"] = True
                base_insights["notice"] = "Oracle HeatWave AutoML 库内模型已完成训练与评估，提供日增单据与批次延期风险预测。"
                base_insights["summary"] = "Oracle MySQL HeatWave AutoML 库内预测已激活。"
            else:
                base_insights["automlStatus"] = "NOT_EVALUATED"
                base_insights["automlStatusDisplay"] = "训练/评分未完成"
                base_insights["trainingAuthorized"] = False
                base_insights["notice"] = "HeatWave AutoML 特征表已就绪，模型训练与评估尚未完成；暂不提供可信预测质量。"
                base_insights["summary"] = "AutoML 特征已建立，训练/评分未完成，暂无可信模型质量。"

            target_models = base_insights.get("targetModels", [])
            for tm in target_models:
                if tm.get("type") == "REGRESSION":
                    tm["status"] = "READY" if reg_quality is not None else "NOT_EVALUATED"
                    tm["algorithm"] = reg_info.get("algorithm", "HeatWave AutoML LinearRegression")
                    tm["quality"] = reg_quality  # 真实值或 None（前端显示"—"），不再硬编码
                elif tm.get("type") == "CLASSIFICATION":
                    tm["status"] = "READY" if cls_quality is not None else "NOT_EVALUATED"
                    tm["algorithm"] = cls_info.get("algorithm", "HeatWave AutoML DecisionTreeClassifier")
                    tm["quality"] = cls_quality  # 真实值或 None，不再硬编码

        return base_insights
    except Exception as e:
        snap = dashboard_snapshot(conn)
        base_insights = dict(snap.get("insights", {}))
        base_insights["hw_ml"] = {"status": "unavailable", "message": f"服务端错误：{e}"}
        base_insights["cf_ai"] = {"status": "unavailable", "message": "服务端错误，状态不可用"}
        base_insights["summary"] = f"研判引擎暂时不可用：{e}"
        return base_insights


@router.post("/insights/generate")
def insights_generate(conn: Connection | None = Depends(v2_connection)) -> dict:
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


@router.get("/operations/summary")
def operations_summary(conn: Connection | None = Depends(v2_connection)) -> dict:
    snap = dashboard_snapshot(conn)
    return normalize_operations_dict(snap.get("operations", {}))


# ===== Business Simulator APIs =====

@router.get("/simulator/status")
async def simulator_status() -> dict:
    """
    获取业务模拟器内存状态（只读）。

    安全说明：
    - 仅读取已有内存状态，不创建写库引擎，不初始化模拟器。
    - 模拟器未启用时（MOD_SIMULATOR_ENABLED 未设置），返回 enabled=false。
    - 不接受任何参数，不写库，不泄露凭据。
    """
    from .business_simulator import get_simulator_instance

    instance = get_simulator_instance()
    if instance is None:
        return {
            "enabled": False,
            "notice": "模拟器未启用（MOD_SIMULATOR_ENABLED 未设置或不在白名单）",
        }
    return {
        "enabled": True,
        **instance.get_status(),
    }





# ===== AI Narrator APIs (解释和表达，不控制数据) =====

@router.get("/narrator/summary")
async def narrator_summary(conn: Connection | None = Depends(v2_connection)) -> dict:
    """
    获取 AI 生成的驾驶舱摘要
    
    AI 只读取数据生成解释，不参与增长计算。
    AI 不可用时返回模板生成的摘要。
    """
    from .ai_narrator import get_narrator

    narrator = get_narrator()

    stats = {
        "today_docs": 0,
        "yesterday_docs": 0,
        "top_provinces": [],
        "integration_success_rate": 1.0,
        "active_scenarios": [],
    }
    
    if conn:
        # 今日单据
        stats["today_docs"] = conn.execute(text(
            "SELECT COUNT(*) FROM business_document WHERE DATE(submit_time) = CURDATE()"
        )).scalar() or 0
        
        # 昨日单据
        stats["yesterday_docs"] = conn.execute(text(
            "SELECT COUNT(*) FROM business_document WHERE DATE(submit_time) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
        )).scalar() or 0
        
        # 今日按省份统计（取前5）
        rows = conn.execute(text("""
            SELECT o.region, COUNT(*) as cnt 
            FROM business_document d 
            JOIN org_unit o ON d.org_id = o.id 
            WHERE DATE(d.submit_time) = CURDATE()
            GROUP BY o.region 
            ORDER BY cnt DESC 
            LIMIT 5
        """)).fetchall()
        stats["top_provinces"] = [(r[0], r[1]) for r in rows]
        
        # 接口成功率
        total = conn.execute(text(
            "SELECT COUNT(*) FROM integration_result WHERE DATE(integration_time) = CURDATE()"
        )).scalar() or 0
        success = conn.execute(text(
            "SELECT COUNT(*) FROM integration_result WHERE DATE(integration_time) = CURDATE() AND status = '成功'"
        )).scalar() or 0
        if total > 0:
            stats["integration_success_rate"] = success / total
    
    # 获取活跃情景
    try:
        from .business_simulator import get_simulator_instance
        instance = get_simulator_instance()
        if instance is not None:
            sim_status = instance.get_status()
            stats["active_scenarios"] = [s["type"] for s in sim_status.get("active_scenarios", [])]
    except Exception:
        pass
    
    # 生成摘要
    result = narrator.generate_dashboard_summary(stats)
    
    return {
        "summary": result.content,
        "generated_at": result.generated_at,
        "source": result.source,
        "stats": stats,
    }


@router.post("/narrator/explain")
async def narrator_explain(anomaly: dict) -> dict:
    """
    让 AI 解释异常
    
    请求体示例：
    {
        "type": "integration_failure_spike",
        "time": "14:20",
        "value": 0.85,
        "baseline": 0.98
    }
    """
    from .ai_narrator import get_narrator
    
    narrator = get_narrator()
    result = narrator.explain_anomaly(anomaly)
    
    return {
        "explanation": result.content,
        "generated_at": result.generated_at,
        "source": result.source,
    }


@router.post("/narrator/parse-scenario")
async def narrator_parse_scenario(request: dict) -> dict:
    """
    把自然语言转换为模拟参数（只返回建议，不直接执行）
    
    请求体示例：
    {"input": "把国庆期间业务量降到平时的30%"}
    
    返回的 suggestion 需要人工确认后才能应用到模拟器。
    """
    from .ai_narrator import get_narrator
    
    user_input = request.get("input", "")
    if not user_input:
        return {"error": "请提供 input 参数"}
    
    narrator = get_narrator()
    result = narrator.parse_scenario_request(user_input)
    
    return result
