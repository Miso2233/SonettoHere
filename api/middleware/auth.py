"""
认证中间件 — 对 API 和 WebSocket 路径校验 Token。

Token 来源（按优先级）：
1. X-Sonetto-Token 请求头（REST API 使用）
2. ?token= 查询参数（WebSocket 使用，因其无法设置自定义头）
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """拦截 /api/* 和 /ws/* 路径，校验认证 Token。"""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # 仅保护 API 和 WebSocket 路径
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await call_next(request)

        # 白名单：健康检查
        if path == "/api/health":
            return await call_next(request)

        # 尝试从请求头或查询参数获取 Token
        token = request.headers.get("x-sonetto-token", "")
        if not token:
            token = request.url.query.split("token=")[-1].split("&")[0] if "token=" in request.url.query else ""

        expected = request.app.state.auth_token
        if not expected or token != expected:
            return JSONResponse(
                {"detail": "Unauthorized — X-Sonetto-Token 缺失或不匹配"},
                status_code=401,
            )
        return await call_next(request)
