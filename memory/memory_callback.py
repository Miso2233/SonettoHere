"""记忆消费者专属回调 — 将 CRUD 工具调用事件推到目标会话 WebSocket。"""

import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from api.ws_registry import WebSocketRegistry


class MemoryToolCallback(BaseCallbackHandler):
    """将 CRUD agent 的工具调用以 memory_tool_* 事件推送到前端。"""

    def __init__(
        self,
        ws_registry: WebSocketRegistry,
        session_id: str,
        turn_id: str,
    ) -> None:
        super().__init__()
        self._ws_registry = ws_registry
        self._session_id = session_id
        self._turn_id = turn_id
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}

    async def _send(self, event_type: str, payload: dict) -> None:
        ws = self._ws_registry.get(self._session_id)
        if ws is None:
            print(f"[ltm-cb] _send skipped: no WS for session={self._session_id[:8]}")
            return  # WebSocket 已断开，静默跳过
        try:
            await ws.send_json({"type": event_type, "payload": payload})
            print(f"[ltm-cb] {event_type} sent to session={self._session_id[:8]} tool={payload.get('tool_name','?')}")
        except Exception as e:
            print(f"[ltm-cb] _send error: {e}")

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name

        # 截断过长输入
        truncated = input_str[:300] if len(input_str) > 300 else input_str
        await self._send("memory_tool_start", {
            "turn_id": self._turn_id,
            "tool_name": tool_name,
            "input": truncated,
        })

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")

        # 提取字符串内容
        out_str = str(output.content) if hasattr(output, "content") else str(output)
        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._send("memory_tool_end", {
            "turn_id": self._turn_id,
            "tool_name": tool_name,
            "output": out_str,
            "elapsed": round(elapsed, 2),
        })

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._send("memory_tool_error", {
            "turn_id": self._turn_id,
            "tool_name": tool_name,
            "error": str(error),
        })
