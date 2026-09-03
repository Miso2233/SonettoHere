"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import ast
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


def _parse_tool_input(tool_input: str | None) -> dict[str, Any] | None:
    """宽松解析工具入参（langchain 主要传 str(dict)，兼容 JSON 字符串）。"""
    if not tool_input:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(tool_input)
        except (ValueError, SyntaxError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


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

        # @background 工具的 spawn 返回（任务索引信封）优先于按工具注册的
        # 提取器：信封里没有业务数据，若落入 tavily_search 等提取器会把
        # 空信封误解析成一份假业务结果。此处统一转成前端后台卡片数据，
        # 并携带剔除 background 字段后的工具入参（前端展示"提交了什么"）。
        data = parsed.get("data") if isinstance(parsed, dict) else None
        if isinstance(data, dict) and data.get("background"):
            input_dict = _parse_tool_input(tool_input)
            args: dict[str, Any] = (
                {k: v for k, v in input_dict.items() if k != "background"}
                if input_dict
                else {}
            )
            return {
                "background": {
                    "index": data.get("task_index"),
                    "status": "running",
                    "tool_name": tool_name,
                    "args": args,
                }
            }

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

    @staticmethod
    def _enrich_await_tool_data(
        tool_input: str | None, out_str: str, tool_data: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """await_background 完成态：用原工具的提取器解析真实结果。

        完成态的输出是**原工具**的输出信封（无 task_index/tasks 字段），按
        后台任务注册表中记录的原工具名与入参重新分发提取器，前端 await
        气泡据此复用原工具的专属气泡渲染。等待态 / 列表态 / 查不到原任务
        时保持原提取不变（前端回退通用结果展示）。
        """
        try:
            parsed = json.loads(out_str)
        except (json.JSONDecodeError, TypeError):
            return tool_data
        if not isinstance(parsed, dict) or parsed.get("success") is not True:
            return tool_data
        data = parsed.get("data")
        if not isinstance(data, dict) or "task_index" in data:
            return tool_data  # 等待态信封，非真实结果

        input_dict = _parse_tool_input(tool_input)
        raw_index = input_dict.get("index") if input_dict else None
        if not isinstance(raw_index, int) or raw_index <= 0:
            return tool_data

        # 延迟导入：回调模块先于 api.agent 初始化，规避导入环
        from api.agent import background as bg_registry  # noqa: PLC0415
        from api.agent import interaction  # noqa: PLC0415

        session_id = interaction.current_session_id.get()
        registry = bg_registry.find_registry(session_id) if session_id else None
        bt = registry.get(raw_index) if registry else None
        if bt is None:
            return tool_data

        enriched: dict[str, Any] = {"original_tool": bt.tool_name}
        if bt.duration_s is not None:
            enriched["original_elapsed_s"] = round(bt.duration_s, 1)
        inner = _dispatch(bt.tool_name, parsed, bt.args_summary)
        if isinstance(inner, dict):
            enriched.update(inner)
        return enriched

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

        # 提取工具专属结构化数据；await_background 完成态额外用原工具
        # 提取器解析真实结果（供前端镜像渲染原工具气泡）
        tool_data = self._extract_tool_data(tool_name, output, tool_input)
        if tool_name == "await_background":
            tool_data = self._enrich_await_tool_data(tool_input, out_str, tool_data)

        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._sender.tool_end(run_id, tool_name, out_str, round(elapsed, 2), tool_data)

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        self._tool_inputs.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._sender.tool_error(run_id, tool_name, str(error))
