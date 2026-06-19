"""
认证中间件 — 对 API 和 WebSocket 路径校验 X-Sonetto-Token。
非 API 路径（/docs、/openapi.json 等）一律放行。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """拦截 /api/* 和 /ws/* 路径，校验 X-Sonetto-Token 请求头。"""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # 仅保护 API 和 WebSocket 路径
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await call_next(request)

        # 白名单：健康检查
        if path == "/api/health":
            return await call_next(request)

        token = request.headers.get("x-sonetto-token", "")
        expected = request.app.state.auth_token
        if not expected or token != expected:
            return JSONResponse(
                {"detail": "Unauthorized — 请在请求头中提供有效的 X-Sonetto-Token"},
                status_code=401,
            )
        return await call_next(request)
