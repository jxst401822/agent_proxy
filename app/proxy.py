"""核心转发逻辑:认证检查 + httpx 转发 + SSE 流式透传。

网关对百炼 DashScope 做透明代理:内网客户端以标准百炼路径调用,
本模块把请求原样转发到上游,并把响应(含流式 SSE)逐块返回。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from .config import Settings

logger = logging.getLogger(__name__)

# 需要剔除的逐跳(Hop-by-hop)请求头,不应转发到上游。
HOP_BY_HOP_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

# 上游 SSE 响应内容类型
EVENT_STREAM_CT = "text/event-stream"


def _resolve_base(settings: Settings, path: str) -> str:
    """按路径前缀选择上游 base。

    - ``api/v1/...``(原生 DashScope)优先使用 ``native_upstream_base``,
      未配置时回退到 ``upstream_base``;
    - 其余(``compatible-mode/v1/...``)使用 ``upstream_base``。
    """
    if path.startswith("api/v1") and settings.native_upstream_base:
        return settings.native_upstream_base
    return settings.upstream_base


def _build_upstream_url(settings: Settings, path: str) -> str:
    """拼接上游完整 URL。

    path 形如 ``compatible-mode/v1/chat/completions`` 或 ``api/v1/...``,
    直接拼接在解析出的 base 之后。查询串由 FastAPI 通过 request 保留。
    """
    base = _resolve_base(settings, path).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _forward_headers(request: Request) -> dict[str, str]:
    """复制请求头,剔除 hop-by-hop 头,保留认证与业务头。"""
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS
    }
    return headers


def _check_auth(request: Request) -> None:
    """校验认证头:必须携带 ``Authorization: Bearer <key>``,否则 401。"""
    auth = request.headers.get("authorization", "")
    if not auth.strip().lower().startswith("bearer"):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": (
                        "Missing or invalid Authorization header. "
                        "Provide your DashScope API key as "
                        "`Authorization: Bearer sk-...`."
                    ),
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )


async def do_proxy(
    request: Request,
    path: str,
    client: httpx.AsyncClient,
    settings: Settings,
) -> Response:
    """转发单个请求到上游并返回适配后的响应。

    - 认证失败 -> 401
    - 上游为 SSE(content-type=text/event-stream) -> StreamingResponse 流式透传
    - 其它 -> 原样返回 body + 状态码 + 内容类型
    """
    _check_auth(request)

    url = _build_upstream_url(settings, path)
    body: Any = await request.body()
    headers = _forward_headers(request)

    req = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=body or None,
    )
    try:
        upstream = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        logger.warning("Upstream request failed: %s %s -> %r", request.method, url, exc)
        raise HTTPException(status_code=502, detail="Upstream request failed") from exc

    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}
    content_type = upstream.headers.get("content-type", "").lower()

    if content_type.startswith(EVENT_STREAM_CT):

        async def event_stream():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()

        return StreamingResponse(
            event_stream(),
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=EVENT_STREAM_CT,
        )

    # 非流式:读取完整 body 后返回。即使上游返回错误状态码也原样透传。
    try:
        data = await upstream.aread()
    finally:
        await upstream.aclose()

    return Response(
        content=data,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=content_type or None,
    )