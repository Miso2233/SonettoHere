"""ChatSender — 路由级事件发送封装。

供 api/routes/chat.py 使用，替代连接建立时的裸推送和 ping/pong 响应。
"""

from __future__ import annotations

from api.events.transport import WsTransport


class ChatSender(WsTransport):
    """路由级事件发送器。

    负责推送连接级事件：pong 心跳响应、初始 context_usage。
    """

    async def pong(self) -> None:
        """推送 pong 心跳响应。"""
        await self._send("pong", {})

    async def context_usage(self, data: dict) -> None:
        """推送上下文窗口用量（连接建立时推送一次）。"""
        await self._send("context_usage", data)
