"""
认证中间件 — ASGI 中间件，统一拦截 HTTP API 和 WebSocket 请求进行 Token 鉴权。

Token 来源：
- HTTP / WebSocket 通用: X-Sonetto-Token 请求头
- WebSocket (浏览器子协议): Sec-WebSocket-Protocol（前端通过 WebSocket sub-protocol 传入）

鉴权失败的响应：
- HTTP: 401 JSONResponse
- WebSocket: 4001 关闭码
"""

from starlette.responses import JSONResponse


class AuthMiddleware:
    """ASGI 中间件 — 在请求到达路由前完成鉴权，HTTP 和 WebSocket 统一处理。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        # 仅保护 API 和 WebSocket 路径
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await self.app(scope, receive, send)

        # 白名单：健康检查
        if path == "/api/health":
            return await self.app(scope, receive, send)

        # 从 scope 提取 Token
        token = self._extract_token(scope)

        # 从 app state 获取期望的 Token
        app = scope.get("app")
        expected = app.state.auth_token if app is not None else None

        if not expected or token != expected:
            return await self._reject(scope, receive, send)

        return await self.app(scope, receive, send)

    def _extract_token(self, scope) -> str:
        """从请求头提取 Token。

        优先 X-Sonetto-Token 自定义头，WebSocket 场景回退到
        Sec-WebSocket-Protocol（浏览器 WebSocket API 无法设置自定义头，
        前端通过 sub-protocol 传入）。
        """
        headers = dict(scope.get("headers", []))

        # 通用：X-Sonetto-Token 自定义头
        token_bytes = headers.get(b"x-sonetto-token", b"")
        if token_bytes:
            return token_bytes.decode()

        # WebSocket 专用：从 Sec-WebSocket-Protocol 提取
        # 前端传参格式: new WebSocket(url, [token])
        # 此时 token 作为唯一 sub-protocol 出现在该头部
        if scope["type"] == "websocket":
            protocols = headers.get(b"sec-websocket-protocol", b"").decode()
            if protocols:
                # 取第一个非空协议作为 token（前端只传了一个）
                return protocols.split(", ")[0].strip()

        return ""

    async def _reject(self, scope, receive, send):
        """根据 scope 类型返回 HTTP 401 或 WebSocket 4001 关闭。"""
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4001})
        else:
            response = JSONResponse(
                {"detail": "Unauthorized — X-Sonetto-Token 缺失或不匹配"},
                status_code=401,
            )
            await response(scope, receive, send)
