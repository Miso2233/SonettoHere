"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import time
from typing import Any

from fastapi import WebSocket
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}

    async def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._thinking_started = True
        await self._ws.send_json({
            "type": "thinking_start",
            "payload": {"timestamp": time.time()},
        })

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        await self._ws.send_json({
            "type": "token",
            "payload": {"token": token},
        })

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self._thinking_started:
            self._thinking_started = False
            await self._ws.send_json({
                "type": "thinking_end",
                "payload": {"timestamp": time.time()},
            })

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name

        await self._ws.send_json({
            "type": "tool_start",
            "payload": {
                "tool_name": tool_name,
                "input": input_str[:500] if len(input_str) > 500 else input_str,
            },
        })

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")

        out_str = str(output) if not isinstance(output, str) else output
        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._ws.send_json({
            "type": "tool_end",
            "payload": {
                "tool_name": tool_name,
                "output": out_str,
                "elapsed": round(elapsed, 2),
            },
        })

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._ws.send_json({
            "type": "tool_error",
            "payload": {
                "tool_name": tool_name,
                "error": str(error),
            },
        })
