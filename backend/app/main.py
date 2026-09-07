from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


from .api import router as router_v2
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

    yield

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


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="MOD API",
        version="0.3.0",
        description="MOD 内部业务看板 API 系统（默认只读，高危/外部调用受权保护）",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-MOD-Auth-Token",
            "description": "内部系统访问授权令牌 (Header 鉴权)",
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Token",
            "description": "内部系统 Bearer 令牌鉴权",
        },
        "ActionTokenAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Action-Token",
            "description": "受信任会话临时操作凭据 (Action Token)",
        },
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


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

