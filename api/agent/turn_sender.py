"""一轮 Agent 轮次的 WebSocket 事件发送器 (WsEventSender)。

封装一轮 Agent 对话中所有前端消息的格式化与发送。
每种消息类型对应一个命名方法，统一消息结构为 {"type": ..., "payload": ...}。
"""

from fastapi import WebSocket


class WsEventSender:
    """一轮 Agent 轮次的 WebSocket 事件发送器。

    Attributes:
        _ws: 底层 WebSocket 连接
    """

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def context_usage(self, data: dict) -> None:
        """推送上下文窗口用量。"""
        await self._ws.send_json({"type": "context_usage", "payload": data})

    async def answer(self, content: str) -> None:
        """推送最终文本回答。"""
        await self._ws.send_json({"type": "answer", "payload": {"content": content}})

    async def error(self, code: str, message: str) -> None:
        """推送错误/取消事件。"""
        await self._ws.send_json({"type": "error", "payload": {"code": code, "message": message}})

    async def tool_error(self, tool_name: str, error: str) -> None:
        """通知前端某工具调用已进入错误状态。"""
        await self._ws.send_json({
            "type": "tool_error",
            "payload": {"tool_name": tool_name, "error": error},
        })

    async def done(self, turn_id: str, context_usage: dict) -> None:
        """推送轮次结束事件（含 turn_id 用于关联记忆）。"""
        await self._ws.send_json({
            "type": "done",
            "payload": {"turn_id": turn_id, "context_usage": context_usage},
        })
