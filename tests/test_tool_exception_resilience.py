"""测试：工具异常不再毒化会话。

背景（回归用例针对的线上现象）：工具 ``_arun`` 里抛出的异常（如 Todoist 返回
400 的 ``httpx.HTTPStatusError``）逃出 ``ToolNode`` 后会终止整次图运行，在
checkpoint 留下「带 tool_calls 却没有对应 ToolMessage」的孤儿状态；此后该会话
每条新消息都重跑同一个失败、永不产出回答，上下文用量被单调刷满。

覆盖三层防线：
- 工具层：``ToolBase.arun`` 把异常转成统一错误响应（不吞 ``CancelledError``）
- 图层：``ToolNode(handle_tool_errors=...)`` 兜住非 ToolBase 工具的异常
- 会话层：``_repair_orphan_tool_calls`` 修掉已被中断污染的历史
- 收尾层：``_execute_agent_turn`` 的 finally 一定下发 ``done``
"""

import asyncio
import json
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphBubbleUp
from pydantic import BaseModel, Field, ValidationError

from agent.graph import build_agent
from api.agent import turn as turn_module
from api.agent.turn import (
    _LlmConfig,
    _TurnContext,
    _execute_agent_turn,
    _find_orphan_tool_calls,
    _repair_orphan_tool_calls,
    _strip_tool_calls,
)
from api.session.manager import SessionState
from tools.base import ToolBase, format_success, tool_error_message

# ── 测试替身 ──────────────────────────────────────────────


class _BoomInput(BaseModel):
    """失败工具的入参（与 todo_list 的 ids 字段同形）。"""

    ids: list[str] | None = None


class _BoomTool(ToolBase):
    """受 ``ToolBase`` 兜底的工具：``_arun`` 直接抛出 400。"""

    name: str = "boom"
    description: str = "总是失败的工具"
    args_schema: type[BaseModel] = _BoomInput

    async def _arun(self, ids: list[str] | None = None) -> str:
        raise RuntimeError(
            "Client error '400 Bad Request' for url "
            "'https://api.todoist.com/api/v1/tasks?ids=deadbeef0000'"
        )


@tool
def raw_boom() -> str:
    """非 ToolBase 的普通 langchain 工具（模拟 MCP 工具），总是抛异常。"""
    raise RuntimeError("raw tool exploded")


class _ScriptedLLM(BaseChatModel):
    """按脚本依次吐出 AIMessage 的假模型；``bind_tools`` 返回自身。"""

    script: list[AIMessage] = Field(default_factory=list)
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedLLM":
        return self

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


class _RecordingSender:
    """记录收尾事件顺序的最小发送器替身。"""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.errors: list[tuple[str, str]] = []

    async def error(self, code: str, message: str) -> None:
        self.calls.append("error")
        self.errors.append((code, message))

    async def done(self, turn_id: str, context_usage: dict) -> None:
        self.calls.append("done")

    async def context_usage(self, usage: dict) -> None:
        self.calls.append("context_usage")


def _tool_call_ai(call_id: str, name: str, args: dict) -> AIMessage:
    """构造一条「请求调用工具」的 AIMessage。"""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _build_graph(
    tools: list[BaseTool], script: list[AIMessage]
) -> tuple[Any, dict[str, Any]]:
    """用假模型构建真实 Agent 图，返回 (graph, config)。"""
    graph = build_agent(
        model=_ScriptedLLM(script=script),
        tools=tools,
        system_prompt="sys",
        checkpointer=MemorySaver(),
        ltm=None,
    )
    config = {
        "configurable": {"thread_id": "t-resilience", "private_mode": True, "turn_id": "turn-1"},
        "recursion_limit": 20,
    }
    return graph, config


async def _drain(graph: Any, config: dict[str, Any], text: str) -> None:
    """跑完一轮图（异常会照常抛出，供断言使用）。"""
    async for _ in graph.astream_events(
        {"messages": [HumanMessage(content=text)]}, config=config, version="v2"
    ):
        pass


# ── 工具层：ToolBase.arun 兜底 ─────────────────────────────


def test_tool_error_message_is_unified_error_response() -> None:
    """错误文本是可解析的 format_error 信封，且保留异常类型与原文。"""
    payload = json.loads(tool_error_message(RuntimeError("boom")))
    assert payload["success"] is False
    assert "RuntimeError" in payload["error"]
    assert "boom" in payload["error"]


@pytest.mark.asyncio
async def test_toolbase_arun_converts_exception_to_error_response() -> None:
    """工具异常不再逃出 arun，而是变成 format_error 文本（前端据此亮错误气泡）。"""
    result = await _BoomTool().arun({"ids": ["deadbeef0000"]}, tool_call_id="call-1")
    payload = json.loads(result)
    assert payload["success"] is False
    assert "400 Bad Request" in payload["error"]


@pytest.mark.asyncio
async def test_toolbase_arun_keeps_normal_result_untouched() -> None:
    """兜底不干扰正常返回路径（成功路径由 langchain 包成 ToolMessage）。"""

    class _OkTool(_BoomTool):
        async def _arun(self, ids: list[str] | None = None) -> str:
            return json.dumps({"success": True, "data": {"ids": ids}}, ensure_ascii=False)

    result = await _OkTool().arun({"ids": ["a"]}, tool_call_id="c")
    content = result.content if isinstance(result, ToolMessage) else result
    assert json.loads(content)["success"] is True


@pytest.mark.asyncio
async def test_toolbase_arun_does_not_swallow_cancelled_error() -> None:
    """取消语义不受影响：CancelledError 是 BaseException，必须原样向上抛。"""

    class _CancelTool(_BoomTool):
        async def _arun(self, ids: list[str] | None = None) -> str:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _CancelTool().arun({"ids": []}, tool_call_id="call-cancel")


@pytest.mark.asyncio
async def test_toolbase_arun_does_not_swallow_graph_bubble_up() -> None:
    """LangGraph 控制流异常必须原样冒泡（interrupt / Command 语义）。"""

    class _BubbleTool(_BoomTool):
        async def _arun(self, ids: list[str] | None = None) -> str:
            raise GraphBubbleUp

    with pytest.raises(GraphBubbleUp):
        await _BubbleTool().arun({"ids": []}, tool_call_id="call-bubble")


@pytest.mark.asyncio
async def test_toolbase_arun_lets_validation_error_through() -> None:
    """入参校验错照旧外抛，交给 ToolNode 走框架既有的校验错误处理。"""

    class _IndexInput(BaseModel):
        index: int = Field(default=1, ge=1)

    class _IndexTool(ToolBase):
        name: str = "index_tool"
        description: str = "带约束入参"
        args_schema: type[BaseModel] = _IndexInput

        async def _arun(self, index: int = 1) -> str:
            return format_success({"index": index})

    with pytest.raises(ValidationError):
        await _IndexTool().arun({"index": 0}, tool_call_id="call-index")


# ── 端到端：图不再中止、历史不留孤儿 ────────────────────────


@pytest.mark.asyncio
async def test_toolbase_exception_no_longer_poisons_session() -> None:
    """回归：工具抛 400 时图照常跑完，且历史里没有无应答的 tool_calls。

    修复前这一步会直接抛出 RuntimeError，并让 checkpoint 停在 ``next=('tools',)``。
    """
    graph, config = _build_graph(
        tools=[_BoomTool()],
        script=[_tool_call_ai("call-1", "boom", {"ids": ["deadbeef0000"]}), AIMessage(content="工具失败了，我如实说明。")],
    )

    await _drain(graph, config, "列一下我的任务")

    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])
    assert _find_orphan_tool_calls(messages) == []
    assert state.next == ()

    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert json.loads(tool_messages[0].content)["success"] is False


@pytest.mark.asyncio
async def test_toolnode_handles_non_toolbase_exception() -> None:
    """图层防线：非 ToolBase 工具（如 MCP 工具）的异常被 ToolNode 兜住。"""
    graph, config = _build_graph(
        tools=[raw_boom],
        script=[_tool_call_ai("call-1", "raw_boom", {}), AIMessage(content="换个方式。")],
    )

    await _drain(graph, config, "试一下原始工具")

    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])
    assert _find_orphan_tool_calls(messages) == []
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
    assert json.loads(tool_messages[0].content)["success"] is False


@pytest.mark.asyncio
async def test_schema_validation_error_surfaces_as_error_message() -> None:
    """入参校验失败仍走框架既有处理：status='error' 的 ToolMessage，图不中止。

    对应「数组入参被序列化成字符串」那类问题——容错治得了的交给入参容错，
    治不了的也必须失败可见、不污染会话。
    """
    graph, config = _build_graph(
        tools=[_BoomTool()],
        script=[
            _tool_call_ai("call-1", "boom", {"ids": "deadbeef0000"}),
            AIMessage(content="参数不对，我换个写法。"),
        ],
    )

    await _drain(graph, config, "用字符串 id 调一下")

    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])
    assert _find_orphan_tool_calls(messages) == []
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
    assert json.loads(tool_messages[0].content)["success"] is False


# ── 会话层：孤儿检测与自愈 ─────────────────────────────────


def test_find_orphan_tool_calls_only_returns_unanswered() -> None:
    """只把「缺 ToolMessage 回应」的 AIMessage 判为孤儿。"""
    orphan = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "c1"}])
    answered = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "c2"}])
    messages = [
        HumanMessage(content="u"),
        orphan,
        answered,
        ToolMessage(content="ok", tool_call_id="c2", name="x"),
    ]

    found = _find_orphan_tool_calls(messages)
    assert [m.id for m in found] == [orphan.id]


def test_strip_tool_calls_keeps_id_and_content() -> None:
    """清空 tool_calls 时必须保留 id 与文本：add_messages 靠 id 原地替换。"""
    orphan = AIMessage(
        content="我先试试",
        tool_calls=[{"name": "x", "args": {}, "id": "c1"}],
        additional_kwargs={"tool_calls": [{"id": "c1"}]},
    )

    fixed = _strip_tool_calls(orphan)

    assert fixed.tool_calls == []
    assert fixed.id == orphan.id
    assert fixed.content == "我先试试"
    assert "tool_calls" not in fixed.additional_kwargs


@pytest.mark.asyncio
async def test_repair_orphan_tool_calls_cleans_poisoned_history() -> None:
    """已被中断污染的历史能被修干净，且重复调用是幂等的。"""
    graph, config = _build_graph(tools=[_BoomTool()], script=[AIMessage(content="好")])
    session = SessionState(session_id="t-resilience")
    session.set_graph(graph)

    # 直接写入污染态：两条无应答的 tool_calls（用户连发几次「继续」的累积效果）
    poisoned = [
        HumanMessage(content="继续"),
        _tool_call_ai("c1", "boom", {"ids": ["deadbeef0000"]}),
        HumanMessage(content="继续"),
        _tool_call_ai("c2", "boom", {"ids": ["deadbeef0000"]}),
    ]
    await graph.aupdate_state(config, {"messages": poisoned}, as_node="agent")
    state = await graph.aget_state(config)
    assert len(_find_orphan_tool_calls(state.values.get("messages", []))) == 2

    repaired = await _repair_orphan_tool_calls(session, config)

    assert repaired == 2
    state = await graph.aget_state(config)
    assert _find_orphan_tool_calls(state.values.get("messages", [])) == []
    # 幂等：没有孤儿时不再改动
    assert await _repair_orphan_tool_calls(session, config) == 0


@pytest.mark.asyncio
async def test_repair_orphan_tool_calls_then_turn_completes() -> None:
    """修好之后，原本每条新消息都重复失败的会话能正常产出回答。"""
    graph, config = _build_graph(tools=[_BoomTool()], script=[AIMessage(content="这是恢复后的回答")])
    session = SessionState(session_id="t-resilience")
    session.set_graph(graph)
    await graph.aupdate_state(
        config,
        {"messages": [HumanMessage(content="继续"), _tool_call_ai("c1", "boom", {"ids": []})]},
        as_node="agent",
    )

    await _repair_orphan_tool_calls(session, config)
    await _drain(graph, config, "继续")

    state = await graph.aget_state(config)
    assert _find_orphan_tool_calls(state.values.get("messages", [])) == []
    last = state.values["messages"][-1]
    assert isinstance(last, AIMessage)
    assert last.content == "这是恢复后的回答"


@pytest.mark.asyncio
async def test_repair_without_graph_is_noop() -> None:
    """会话还没有编译图时直接跳过，不抛异常。"""
    assert await _repair_orphan_tool_calls(SessionState(session_id="s"), {}) == 0


# ── 收尾层：done 一定下发 ─────────────────────────────────


@pytest.mark.asyncio
async def test_execute_agent_turn_emits_done_even_if_usage_estimate_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用量估算失败也不能吞掉 done，否则前端永久停在生成中。

    done 是前端唯一的收尾信号（error 只清流式标记、不清 currentTurn）。
    """

    def _boom(*args: Any, **kwargs: Any) -> dict:
        raise RuntimeError("estimator exploded")

    monkeypatch.setattr(
        turn_module, "estimate_context_usage_from_session", _boom
    )

    sender = _RecordingSender()
    session = SessionState(session_id="s-1")
    ctx = _TurnContext(
        system_prompt="sys",
        agent=None,  # type: ignore[arg-type]  估算先失败，走不到图
        inputs={},
        config={"configurable": {"thread_id": "s-1"}},
        turn_id="turn-1",
    )
    llm_conf = _LlmConfig(llm=None, model_name="m", max_tokens=1024)  # type: ignore[arg-type]

    result = await _execute_agent_turn(ctx, sender, session, llm_conf)

    assert result.error is not None and "estimator exploded" in result.error
    assert sender.calls[0] == "error"
    assert "done" in sender.calls
