"""MemorySender — 记忆层事件发送封装。

供 long_term.py 和 MemoryToolCallback 使用。
"""

from __future__ import annotations

from api.events.transport import WsTransport


class MemorySender(WsTransport):
    """记忆层事件发送器。

    负责推送后台记忆 consumer 的生命周期事件：
    memory_start / memory_done / memory_tool_start/end/error。
    """

    async def memory_start(self, turn_id: str) -> None:
        """通知前端记忆 consumer 开始处理本轮对话。"""
        await self._send("memory_start", {"turn_id": turn_id})

    async def memory_tool_start(self, turn_id: str, tool_name: str, input: str) -> None:
        """推送记忆 CRUD 工具开始执行。"""
        await self._send("memory_tool_start", {
            "turn_id": turn_id,
            "tool_name": tool_name,
            "input": input,
        })

    async def memory_tool_end(self, turn_id: str, tool_name: str, output: str, elapsed: float) -> None:
        """推送记忆 CRUD 工具执行完毕。"""
        await self._send("memory_tool_end", {
            "turn_id": turn_id,
            "tool_name": tool_name,
            "output": output,
            "elapsed": elapsed,
        })

    async def memory_tool_error(self, turn_id: str, tool_name: str, error: str) -> None:
        """推送记忆 CRUD 工具执行出错。"""
        await self._send("memory_tool_error", {
            "turn_id": turn_id,
            "tool_name": tool_name,
            "error": error,
        })

    async def memory_done(self, turn_id: str) -> None:
        """通知前端本轮记忆处理完成。"""
        await self._send("memory_done", {"turn_id": turn_id})
