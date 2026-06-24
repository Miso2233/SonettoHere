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

        # 提取并校验 Token
        token = self._extract_token(scope)
        app = scope.get("app")
        expected = app.state.auth_token if app is not None else None

        if not expected or token != expected:
            return await self._reject(scope, receive, send)

        # WebSocket 鉴权通过后：拦截 handler 的 websocket.accept 消息，
        # 自动注入 subprotocol（前端通过 new WebSocket(url, [token]) 请求的协议），
        # 业务 handler 无需感知 sub-protocol 协商细节。
        if scope["type"] == "websocket":
            protocols = scope.get("subprotocols", [])
            if protocols:
                original_send = send

                async def _accept_with_subprotocol(message):
                    if message.get("type") == "websocket.accept" and not message.get("subprotocol"):
                        message = {**message, "subprotocol": protocols[0]}
                    await original_send(message)

                return await self.app(scope, receive, _accept_with_subprotocol)

        return await self.app(scope, receive, send)

    def _extract_token(self, scope) -> str:
        """从请求头提取 Token。

        HTTP / WebSocket 通用路径: X-Sonetto-Token 自定义头
        WebSocket 专用路径: scope.subprotocols（由 ASGI server/uvicorn 从
        Sec-WebSocket-Protocol 握手头部解析，前端通过 new WebSocket(url, [token])
        传入）。优先使用 subprotocols 字段，比手动解析 raw header 更可靠。
        """
        headers = dict(scope.get("headers", []))

        # 通用：X-Sonetto-Token 自定义头
        token_bytes = headers.get(b"x-sonetto-token", b"")
        if token_bytes:
            return token_bytes.decode()

        # WebSocket 专用：从 ASGI scope 的 subprotocols 字段提取
        # ASGI server 在握手时自动解析 Sec-WebSocket-Protocol 头部，
        # 存入 scope["subprotocols"] = [token]
        if scope["type"] == "websocket":
            protocols = scope.get("subprotocols", [])
            if protocols:
                return protocols[0]

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
