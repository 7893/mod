from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .api import router as router_v2
from .live_projection import get_live_projection_broker
from .live_projection.api import router as live_projection_router

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 模拟器任务（仅在显式启用时才会被赋值）
_simulator_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    安全策略：
    - 默认不启动模拟器，不创建写库连接，不写数据库。
    - 仅当 MOD_SIMULATOR_ENABLED=true 且 MOD_DB_WRITE_URL 已设置时才启动后台循环。
    - 配置错误时 fail-closed：记录错误日志，拒绝启动模拟器，不暴露凭据信息。
    - 代码中不包含任何硬编码数据库 URL、主机地址、用户名或密码。
    """
    global _simulator_task

    from .simulator_config import SimulatorConfigError, load_simulator_config

    try:
        sim_config = load_simulator_config()
    except SimulatorConfigError as exc:
        # 配置错误：fail-closed，不启动模拟器，不泄露凭据
        logger.error("模拟器配置错误，已拒绝启动：%s", exc)
        sim_config = None

    if sim_config is not None and sim_config.enabled:
        from .business_simulator import run_simulator_loop
        _simulator_task = asyncio.create_task(
            run_simulator_loop(sim_config.db_write_url)
        )
        logger.info("业务模拟器后台任务已启动（MOD_SIMULATOR_ENABLED=true）")
    else:
        logger.info(
            "业务模拟器未启用（MOD_SIMULATOR_ENABLED 未设置或不在白名单），"
            "跳过写库连接创建。"
        )

    live_projection = get_live_projection_broker()
    await live_projection.start()
    logger.info("只读实时投影%s", "已启动" if live_projection.enabled else "未启用")

    yield

    # 关闭时：取消模拟器（如果存在）
    if _simulator_task:
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass
        logger.info("业务模拟器已停止")
    await live_projection.stop()


app = FastAPI(
    title="MOD API",
    version="0.3.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
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


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "MOD API", "status": "ok"}
