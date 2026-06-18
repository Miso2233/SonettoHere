"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import json
import time
from typing import Any

from fastapi import WebSocket
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .tool_extractors import _dispatch


def _extract_content(output: Any) -> str:
    """从工具输出中提取字符串内容。

    LangChain ToolMessage 的 __str__ 会返回 "content='...' name='...' tool_call_id='...'"
    这种无法解析的格式，需要取其 .content 属性获取真正的 JSON。
    """
    if hasattr(output, 'content'):
        return str(output.content)
    if not isinstance(output, str):
        return str(output)
    return output


class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}

    @staticmethod
    def _extract_tool_data(tool_name: str, output: Any, tool_input: str | None = None) -> dict[str, Any] | None:
        """从工具输出中提取前端专属气泡所需的结构化数据。"""
        out_str = _extract_content(output)
        try:
            parsed = json.loads(out_str)
        except (json.JSONDecodeError, TypeError):
            # MCP Word 工具返回纯文本而非 JSON — 包装为 _raw 让提取器能处理
            if tool_name.startswith("word_"):
                return _dispatch(tool_name, {"_raw": out_str}, tool_input)
            return None
        return _dispatch(tool_name, parsed, tool_input)

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
        self._tool_inputs[run_id] = input_str

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
        tool_input = self._tool_inputs.pop(run_id, None)

        out_str = _extract_content(output)

        # ── 检测 format_error 响应 → 路由到 tool_error ────────────
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                error_msg = parsed.get("error", "操作执行失败")
                await self._ws.send_json({
                    "type": "tool_error",
                    "payload": {
                        "tool_name": tool_name,
                        "error": error_msg,
                    },
                })
                return
        except (json.JSONDecodeError, TypeError):
            pass
        # ──────────────────────────────────────────────────────────

        # 提取工具专属结构化数据
        tool_data = self._extract_tool_data(tool_name, output, tool_input)

        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._ws.send_json({
            "type": "tool_end",
            "payload": {
                "tool_name": tool_name,
                "output": out_str,
                "elapsed": round(elapsed, 2),
                "tool_data": tool_data,
            },
        })

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        self._tool_inputs.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._ws.send_json({
            "type": "tool_error",
            "payload": {
                "tool_name": tool_name,
                "error": str(error),
            },
        })
