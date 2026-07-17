"""TurnSender — Agent 轮次事件发送封装。

取代 api/agent/turn_sender.py 中的 WsEventSender。
"""

from __future__ import annotations

from api.events.transport import WsTransport


class TurnSender(WsTransport):
    """Agent 轮次事件发送器。

    负责推送 Agent 执行过程中的上下文用量、最终回答、
    错误/取消事件、工具调用取消通知，以及轮次结束事件。
    """

    async def context_usage(self, data: dict) -> None:
        """推送上下文窗口用量。"""
        await self._send("context_usage", data)

    async def answer(self, content: str) -> None:
        """推送最终文本回答。"""
        await self._send("answer", {"content": content})

    async def error(self, code: str, message: str) -> None:
        """推送错误/取消事件。"""
        await self._send("error", {"code": code, "message": message})

    async def tool_error(self, tool_name: str, error: str) -> None:
        """通知前端某工具调用已进入错误状态。"""
        await self._send("tool_error", {"tool_name": tool_name, "error": error})

    async def done(self, turn_id: str, context_usage: dict) -> None:
        """推送轮次结束事件（含 turn_id 用于关联记忆）。"""
        await self._send("done", {"turn_id": turn_id, "context_usage": context_usage})
