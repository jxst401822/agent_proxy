"""FastAPI 应用入口:挂载转发路由、CORS、共享 httpx 客户端生命周期。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .proxy import do_proxy

# 允许的 HTTP 方法(覆盖百炼常用的 GET/POST 及 CORS 预检)
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建共享 httpx 客户端,关闭时释放。"""
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout),
        follow_redirects=True,
    )
    logging.getLogger("app").info("Gateway upstream: %s", settings.upstream_base)
    yield
    await app.state.http_client.aclose()


settings = get_settings()
app = FastAPI(
    title="DashScope Compatible Gateway",
    description=(
        "对内网呈现与阿里云百炼(DashScope)一致的 API 形态,"
        "将请求透明转发到真实上游服务(支持流式 SSE)。"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS(仅当设置了白名单)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=["*"],
    )


@app.api_route("/compatible-mode/v1/{path:path}", methods=ALLOWED_METHODS)
@app.api_route("/api/v1/{path:path}", methods=ALLOWED_METHODS)
async def proxy_route(request: Request, path: str) -> Response:
    """两条百炼路径线的 catch-all 转发,path 为前缀之后的剩余路径。

    上游转发使用完整请求路径(request.url.path),这样两条前缀都能正确拼接。
    """
    full_path = request.url.path.lstrip("/")
    return await do_proxy(
        request,
        full_path,
        app.state.http_client,
        get_settings(),
    )


@app.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


if __name__ == "__main__":
    # 让 .env 中的 HOST / PORT 生效:uvicorn 监听地址与端口取自配置。
    # 启动方式: uv run python -m app.main
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)