"""日志链路中间件 — 为每个 HTTP 请求注入 trace_id。

通过 :func:`api.utils.logger.set_trace_id` 设置，使该请求
生命期内所有日志自动携带 trace_id 字段。
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from api.utils.logger import set_trace_id, get_logger

_log = get_logger("middleware")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 trace_id。

    优先级：
    1. 请求头 ``X-Trace-Id``（外部系统传入）
    2. 自动生成 UUID hex
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 从请求头获取或生成 trace_id
        trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:16])
        set_trace_id(trace_id)

        _log.debug("request %s %s [trace=%s]", request.method, request.url.path, trace_id)

        try:
            response = await call_next(request)
        finally:
            # 清理 trace_id，避免泄漏到下一个请求
            set_trace_id(None)

        return response
