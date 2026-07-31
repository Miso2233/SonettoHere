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

    async def message_queued(self, pending_id: str, text: str, position: int) -> None:
        """推送消息入队确认（Agent 输出期间发送的消息被挂起）。"""
        await self._send("message_queued", {
            "pending_id": pending_id,
            "text": text,
            "position": position,
        })

    async def pending_consumed(
        self,
        pending: list[dict],
        mode: str,
        text: str | None = None,
    ) -> None:
        """推送排队消息已被注入上下文。

        ``pending`` 为 ``[{"pending_id": str, "text": str}, ...]``，按消费顺序排列。

        mode='mid_turn'：注入到当前轮次（前端在工具之间渲染为用户气泡）；
        mode='new_turn'：合并为新的一轮（前端创建 currentTurn，text 为合并文本）。
        """
        payload: dict = {"pending": pending, "mode": mode}
        if text is not None:
            payload["text"] = text
        await self._send("pending_consumed", payload)

    async def pending_sync(self, pending: list[dict]) -> None:
        """推送当前挂起队列状态（WebSocket 重连时重建前端排队气泡）。"""
        await self._send("pending_sync", {"pending": pending})

    async def pending_cancelled(self, pending_ids: list[str]) -> None:
        """推送排队消息被取消（用户点击停止，队列被丢弃）。"""
        await self._send("pending_cancelled", {"pending_ids": pending_ids})
