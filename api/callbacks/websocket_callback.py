"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import json
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from langchain_core.outputs import LLMResult

from api.events import CallbackSender
from api.utils.logger import get_logger
from .tool_extractors import _dispatch

_log = get_logger("websocket_callback")


def _extract_block_token(token: Any) -> tuple[str, str]:
    """从块式 token 中提取 (text, thinking) 纯文本。

    部分 Anthropic 适配模型（如 Kimi K3）把流式 content blocks 原样透传为
    ``on_llm_new_token`` 的 token：可能是 JSON 字符串（``[{"type":"thinking",...}]``）
    或 Python list。这里统一解析并拆出 text 块与 thinking 块的正文。

    Returns:
        ``(text, thinking)``。两者都为空表示 token 不是块式结构（普通文本 token），
        调用方应走原有逻辑。
    """
    blocks: list | None = None
    if isinstance(token, list):
        blocks = token
    elif isinstance(token, str) and token.lstrip().startswith("["):
        try:
            parsed = json.loads(token)
        except (json.JSONDecodeError, TypeError):
            return "", ""
        if isinstance(parsed, list):
            blocks = parsed
        elif isinstance(parsed, str):
            # JSON 字符串字面量（如 `"hello"`）当作普通文本
            return parsed, ""
        else:
            return "", ""

    if blocks is None:
        return "", ""

    text_parts: list[str] = []
    thinking_parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and isinstance(block.get("text"), str):
            text_parts.append(block["text"])
        elif btype == "thinking" and isinstance(block.get("thinking"), str):
            thinking_parts.append(block["thinking"])
    return "".join(text_parts), "".join(thinking_parts)


def _extract_content(output: Any) -> str:
    """从工具输出中提取字符串内容。

    LangChain ToolMessage 的 __str__ 会返回 "content='...' name='...' tool_call_id='...'"
    这种无法解析的格式，需要取其 .content 属性获取真正的 JSON。
    """
    if hasattr(output, "content"):
        return str(output.content)
    if not isinstance(output, str):
        return str(output)
    return output


class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, sender: CallbackSender):
        super().__init__()
        self._sender = sender
        self._thinking_started = False
        self._thinking_count = 0
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}

    @staticmethod
    def _extract_tool_data(
        tool_name: str, output: Any, tool_input: str | None = None
    ) -> dict[str, Any] | None:
        """从工具输出中提取前端专属气泡所需的结构化数据。

        支持两种输出格式：
        1. Command 对象 — 从 update.messages 中提取首条 ToolMessage 的 JSON content。
        2. 普通字符串 — 直接 JSON 解析。
        """
        # Command 路径：提取 update.messages 中的 ToolMessage 内容
        if type(output).__name__ == "Command" and hasattr(output, "update"):
            msgs = (output.update or {}).get("messages", [])
            for msg in msgs:
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    try:
                        parsed = json.loads(msg.content)
                        return _dispatch(tool_name, parsed, tool_input)
                    except (json.JSONDecodeError, TypeError):
                        continue

        # 普通字符串路径
        out_str = _extract_content(output)
        try:
            parsed = json.loads(out_str)
        except (json.JSONDecodeError, TypeError):
            return None
        return _dispatch(tool_name, parsed, tool_input)

    async def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._thinking_started = True
        self._thinking_count = 0
        await self._sender.thinking_start(time.time())

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        # 归一化块式 token：部分 Anthropic 适配模型（如 Kimi K3）把 content blocks
        # （thinking/text）原样透传为 token（JSON 字符串或 list）。这里解析并提取：
        #   - text 块    → 正常 token 事件（流式正文）
        #   - thinking 块 → thinking_token 计数（进度，不展示思考明文，与既有策略一致）
        # 普通字符串 token 原样转发。
        text, thinking = _extract_block_token(token)
        if thinking:
            self._thinking_count += 1
            await self._sender.thinking_token(self._thinking_count)
        if text:
            await self._sender.token(text)
            return
        if thinking:
            return
        # 非块式 token：维持原有逻辑（空 chunk 计思考进度，非空发正文）
        if not token:
            self._thinking_count += 1
            await self._sender.thinking_token(self._thinking_count)
        else:
            await self._sender.token(token)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self._thinking_started:
            self._thinking_started = False
            await self._sender.thinking_end(time.time())

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name
        self._tool_inputs[run_id] = input_str

        truncated_input = input_str[:500] if len(input_str) > 500 else input_str
        await self._sender.tool_start(run_id, tool_name, truncated_input)

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")
        tool_input = self._tool_inputs.pop(run_id, None)

        # Command 对象：提取首条 ToolMessage 的 content 作为可读输出
        if type(output).__name__ == "Command" and hasattr(output, "update"):
            msgs = (output.update or {}).get("messages", [])
            for msg in msgs:
                if isinstance(msg, ToolMessage):
                    output = msg.content
                    break

        out_str = _extract_content(output)

        # ── 检测 format_error 响应 → 路由到 tool_error ────────────
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                error_msg = parsed.get("error", "操作执行失败")
                await self._sender.tool_error(run_id, tool_name, error_msg)
                return
        except (json.JSONDecodeError, TypeError):
            pass
        # ──────────────────────────────────────────────────────────

        # 提取工具专属结构化数据
        tool_data = self._extract_tool_data(tool_name, output, tool_input)

        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._sender.tool_end(run_id, tool_name, out_str, round(elapsed, 2), tool_data)

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        self._tool_inputs.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._sender.tool_error(run_id, tool_name, str(error))
