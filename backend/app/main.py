from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


from .api import router as router_v2
from .config import get_settings
from .live_projection import get_live_projection_broker
from .live_projection.api import router as live_projection_router

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理（API 默认严格只读）
    """
    live_projection = get_live_projection_broker()
    await live_projection.start()
    logger.info("只读实时投影%s", "已启动" if live_projection.enabled else "未启用")

    # HeatWave 内存加速状态开机只读观测 (KI-049/KI-050: 遵循只读账号边界，自愈由系统看门狗服务托管)
    try:
        from .db import get_engine
        from .heatwave_watchdog import get_heatwave_status
        with get_engine().connect() as conn:
            hw_info = get_heatwave_status(conn)
            if hw_info.get("status") == "HEALTHY":
                logger.info(
                    "HeatWave 内存加速启动自检就绪: status=HEALTHY, loaded=%s/%s",
                    hw_info.get("loaded_count", 0),
                    hw_info.get("total_target", 9),
                )
            else:
                logger.warning(
                    "HeatWave 内存加速状态非 HEALTHY: status=%s, loaded=%s/%s, 缺失表=%s (自愈由 mod-heatwave-watchdog.timer 托管)",
                    hw_info.get("status"),
                    hw_info.get("loaded_count", 0),
                    hw_info.get("total_target", 9),
                    hw_info.get("missing_tables", []),
                )
    except Exception as e:
        logger.warning("HeatWave 状态开机自检跳过或异常: %s", e)

    # KI-059: 全场景秒级响应 SLA 保证 —— 开机快照后台异步预热
    try:
        from .api import prewarm_snapshot
        prewarm_snapshot(sync=False)
        logger.info("开机快照异步预热已触发")
    except Exception as e:
        logger.warning("开机快照预热触发异常: %s", e)

    yield

    await live_projection.stop()


def should_enable_docs() -> bool:
    """生产环境默认关闭交互式文档与 OpenAPI 架构模式暴露 (KI-078)"""
    env_flag = os.getenv("MOD_ENABLE_DOCS")
    if env_flag is not None:
        return env_flag.lower() in ("1", "true", "yes", "on")
    return get_settings().environment != "production"


enable_docs = should_enable_docs()

app = FastAPI(
    title="MOD API",
    version="0.3.0",
    docs_url="/api/docs" if enable_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if enable_docs else None,
    lifespan=lifespan,
)
app.include_router(router_v2)
app.include_router(live_projection_router)


class NoIndexMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex"
        return response


app.add_middleware(NoIndexMiddleware)


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled server error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务错误，请联系系统管理员"},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "MOD API", "status": "ok"}
