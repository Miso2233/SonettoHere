"""测试：流式输出期间消息排队并注入 Agent 上下文。

覆盖：
- SessionState 挂起队列（入队/FIFO/清空/断连存活）
- clear_active_task owner 守卫
- merge_pending_batch 合并逻辑
- _handle_chat 忙碌路径入队 + ack + 重查补启动
- _handle_cancel 清队列 + pending_cancelled
- _start_turn_from_ws FIFO 合并
- InjectPendingNode 独立节点注入（LangGraph 状态持久化 + 工具循环接线）
- CheckPendingNode 图内多轮循环（队列非空注入并跳回 retrieve_memory）
- run_agent_turn 单次图调用（不再 drain 队列）
"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.graph import (
    AgentState,
    CallAgentNode,
    CheckPendingNode,
    InjectPendingNode,
    route_after_agent,
    route_after_check,
)
from api.agent import interaction
from api.agent.turn import (
    _TurnResult,
    merge_pending_batch,
    run_agent_turn,
)
from api.routes.chat import (
    _handle_cancel,
    _handle_chat,
    _handle_clear_pending,
    _handle_remove_pending,
    _start_turn_from_ws,
)
from api.session.manager import PendingMessage, SessionState, session_manager


# ── 测试替身 ──────────────────────────────────────────────────


class FakeToolManager:
    """最小工具管理器，get_all 返回空列表。"""

    def get_all(self, multimodal: bool = False) -> list:
        return []


class FakeAppState:
    """最小 app.state，提供 run_agent_turn 所需的 tool_manager / ltm。"""

    tool_manager = FakeToolManager()
    ltm = None


class FakeApp:
    state = FakeAppState()


class FakeWs:
    """最小 WebSocket 替身，捕获 send_json 事件。"""

    def __init__(self) -> None:
        self.app = FakeApp()
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class CompletingWs(FakeWs):
    """send_json 时完成给定的 Future（用于测试 ack 后重查补启动）。"""

    def __init__(self, future: asyncio.Future) -> None:
        super().__init__()
        self._future = future

    async def send_json(self, data: dict) -> None:
        await asyncio.sleep(0)
        if not self._future.done():
            self._future.set_result(None)
        self.sent.append(data)


def _ws_events(ws: FakeWs, event_type: str) -> list[dict]:
    return [e for e in ws.sent if e.get("type") == event_type]


def _make_session(sid: str = "test-sid") -> SessionState:
    return SessionState(session_id=sid)


# ── SessionState 队列 ─────────────────────────────────────────


def test_pending_queue_basic():
    s = _make_session()
    assert s.pending_count() == 0
    assert s.has_pending() is False

    pos1 = s.enqueue_pending(PendingMessage(pending_id="a", text="A"))
    pos2 = s.enqueue_pending(PendingMessage(pending_id="b", text="B"))
    assert pos1 == 1
    assert pos2 == 2
    assert s.pending_count() == 2
    assert s.has_pending() is True

    drained = s.drain_pending()
    assert [p.pending_id for p in drained] == ["a", "b"]  # FIFO
    assert s.has_pending() is False
    assert s.drain_pending() == []  # drain 幂等


def test_pending_queue_clear_and_peek():
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="c", text="C"))
    # peek 非破坏
    assert [p.pending_id for p in s.peek_pending()] == ["c"]
    assert s.pending_count() == 1
    cleared = s.clear_pending()
    assert [p.pending_id for p in cleared] == ["c"]
    assert s.pending_count() == 0


def test_pending_queue_survives_disconnect():
    """队列与 ws 解耦，断连/重连后仍在（服务端挂置语义）。"""
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="a", text="A"))
    s.ws = None  # 模拟断连
    assert s.has_pending() is True
    assert [p.pending_id for p in s.peek_pending()] == ["a"]


# ── clear_active_task owner 守卫 ──────────────────────────────


@pytest.mark.asyncio
async def test_clear_active_task_owner_guard():
    s = _make_session()
    t1 = asyncio.Future()
    t2 = asyncio.Future()
    s.set_active_task(t1)
    # task=None 时无条件清除（兼容旧调用点）
    s.clear_active_task()
    assert s.has_active_task() is False

    s.set_active_task(t2)
    s.clear_active_task(t1)  # 非 owner，不应清除
    assert s.has_active_task() is True
    s.clear_active_task(t2)  # owner，清除
    assert s.has_active_task() is False


# ── merge_pending_batch ───────────────────────────────────────


def test_merge_pending_batch():
    batch = [
        PendingMessage(pending_id="1", text="你好（2026-07-30 Wed 14:30）"),
        PendingMessage(pending_id="2", text="第二条"),
        PendingMessage(
            pending_id="3",
            text="带图",
            image_recognition=True,
            image_refs=["/a.jpg", "/b.jpg"],
        ),
    ]
    text, img_recog, img_refs = merge_pending_batch(batch)
    assert text == "你好\n\n第二条\n\n带图"  # 空行分隔 + 时间后缀剥离
    assert img_recog is True
    assert img_refs == ["/a.jpg", "/b.jpg"]


def test_merge_pending_batch_images_or():
    batch = [
        PendingMessage(pending_id="1", text="纯文本"),
        PendingMessage(pending_id="2", text="有图", image_recognition=True, image_refs=["/x.png"]),
    ]
    text, img_recog, img_refs = merge_pending_batch(batch)
    assert text == "纯文本\n\n有图"
    assert img_recog is True  # OR 累积
    assert img_refs == ["/x.png"]


# ── _handle_chat 忙碌路径 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_chat_busy_enqueues():
    s = _make_session()
    ws = FakeWs()
    agent_task: asyncio.Future = asyncio.Future()  # 永不完成 → 忙碌路径
    msg = {"type": "chat", "payload": {"message": "hello", "client_msg_id": "cid-1"}}

    ret = await _handle_chat(ws, "test-sid", s, agent_task, msg)
    assert ret is agent_task  # 返回原任务
    assert s.pending_count() == 1
    pending = s.peek_pending()[0]
    assert pending.pending_id == "cid-1"
    assert pending.text == "hello"

    acks = _ws_events(ws, "message_queued")
    assert len(acks) == 1
    assert acks[0]["payload"]["pending_id"] == "cid-1"
    assert acks[0]["payload"]["position"] == 1


@pytest.mark.asyncio
async def test_handle_chat_busy_recheck_starts_drain(monkeypatch):
    """ack 等待期间旧任务收尾 → 重查后补启动 drain。"""
    agent_task: asyncio.Future = asyncio.Future()
    s = _make_session()
    ws = CompletingWs(agent_task)

    calls: list[str] = []
    monkeypatch.setattr(
        "api.routes.chat._start_turn_from_ws",
        lambda w, sid, sess: (calls.append(sid), "NEW_TASK")[1],
    )
    msg = {"type": "chat", "payload": {"message": "hello"}}

    ret = await _handle_chat(ws, "test-sid", s, agent_task, msg)
    assert calls == ["test-sid"]  # 重查触发了补启动
    assert ret == "NEW_TASK"
    assert s.pending_count() == 1  # 队列仍保留，由 drain 消费


@pytest.mark.asyncio
async def test_handle_chat_subagent_no_queue():
    s = _make_session()
    s.sub_agent.is_subagent = True
    ws = FakeWs()
    agent_task: asyncio.Future = asyncio.Future()
    msg = {"type": "chat", "payload": {"message": "hello", "client_msg_id": "cid-1"}}

    ret = await _handle_chat(ws, "test-sid", s, agent_task, msg)
    assert ret is agent_task
    assert s.pending_count() == 0  # 子 Agent 会话不排队


# ── _handle_cancel ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_cancel_clears_queue():
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="p1", text="A"))
    s.enqueue_pending(PendingMessage(pending_id="p2", text="B"))
    ws = FakeWs()

    ret = await _handle_cancel(ws, "test-sid", s, None, {})
    assert ret is None
    assert s.pending_count() == 0

    events = _ws_events(ws, "pending_cancelled")
    assert len(events) == 1
    assert events[0]["payload"]["pending_ids"] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_handle_cancel_empty_queue_no_event():
    s = _make_session()
    ws = FakeWs()
    await _handle_cancel(ws, "test-sid", s, None, {})
    assert _ws_events(ws, "pending_cancelled") == []


# ── _handle_remove_pending / _handle_clear_pending ───────────


@pytest.mark.asyncio
async def test_handle_remove_pending():
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="p1", text="A"))
    s.enqueue_pending(PendingMessage(pending_id="p2", text="B"))
    ws = FakeWs()

    ret = await _handle_remove_pending(ws, "test-sid", s, None, {
        "type": "remove_pending", "payload": {"pending_id": "p1"}
    })
    assert ret is None
    assert [p.pending_id for p in s.peek_pending()] == ["p2"]

    events = _ws_events(ws, "pending_cancelled")
    assert len(events) == 1
    assert events[0]["payload"]["pending_ids"] == ["p1"]


@pytest.mark.asyncio
async def test_handle_remove_pending_unknown_id_no_event():
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="p1", text="A"))
    ws = FakeWs()

    await _handle_remove_pending(ws, "test-sid", s, None, {
        "type": "remove_pending", "payload": {"pending_id": "nope"}
    })
    assert s.pending_count() == 1
    assert _ws_events(ws, "pending_cancelled") == []


@pytest.mark.asyncio
async def test_handle_clear_pending():
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="p1", text="A"))
    s.enqueue_pending(PendingMessage(pending_id="p2", text="B"))
    ws = FakeWs()

    ret = await _handle_clear_pending(ws, "test-sid", s, None, {
        "type": "clear_pending", "payload": {}
    })
    assert ret is None
    assert s.pending_count() == 0

    events = _ws_events(ws, "pending_cancelled")
    assert len(events) == 1
    assert events[0]["payload"]["pending_ids"] == ["p1", "p2"]


# ── _start_turn_from_ws FIFO 合并 ─────────────────────────────


@pytest.mark.asyncio
async def test_start_turn_from_ws_merges_fifo(monkeypatch):
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="q1", text="排队一"))
    s.enqueue_pending(PendingMessage(pending_id="q2", text="排队二"))

    captured: list[tuple[str, dict]] = []

    async def fake_run(session, text, **kw):
        captured.append((text, kw))
        return None

    monkeypatch.setattr("api.routes.chat.run_agent_turn", fake_run)
    ws = FakeWs()
    interaction.current_ws.set(ws)

    task = _start_turn_from_ws(
        ws, "test-sid", s, PendingMessage(pending_id="c1", text="新消息")
    )
    assert task is not None
    await asyncio.wait_for(task, timeout=1)
    assert len(captured) == 1
    text, kw = captured[0]
    assert text == "排队一\n\n排队二\n\n新消息"  # 旧在前，新在后
    assert [p.pending_id for p in kw["queued_pending"]] == ["q1", "q2"]  # 仅排队消息（不含 incoming）
    assert s.pending_count() == 0


@pytest.mark.asyncio
async def test_start_turn_from_ws_no_messages_returns_none(monkeypatch):
    s = _make_session()
    monkeypatch.setattr("api.routes.chat.run_agent_turn", lambda *a, **k: None)
    ws = FakeWs()
    assert _start_turn_from_ws(ws, "test-sid", s) is None


# ── InjectPendingNode 工具间隙注入 ─────────────────────────────


@pytest.mark.asyncio
async def test_inject_pending_node_drains_and_persists():
    """独立节点单元测试：排空队列、持久化注入消息、发 mid_turn 事件。"""
    node = InjectPendingNode()

    builder = StateGraph(AgentState)
    builder.add_node("inject", node)
    builder.add_edge(START, "inject")
    builder.add_edge("inject", END)
    graph = builder.compile(checkpointer=MemorySaver())

    sid = "inject-sid"
    session = _make_session(sid)
    session.ws = FakeWs()
    session.enqueue_pending(PendingMessage(pending_id="p1", text="排队问题"))
    session_manager.put(sid, session)
    try:
        config = {"configurable": {"thread_id": sid}}
        await graph.ainvoke(
            {"messages": [HumanMessage(content="第一个问题")]}, config
        )

        # 注入消息持久化到 checkpoint，且时间戳由后端追加进入 LLM 上下文
        state = await graph.aget_state(config)
        contents = [str(m.content) for m in state.values["messages"]]
        assert any("第一个问题" in c for c in contents)
        assert any("排队问题" in c for c in contents)
        assert any("（20" in c for c in contents)  # 后端时间戳尾缀

        # 队列已排空，且前端收到 mid_turn 注入事件（干净文本供前端渲染气泡）
        assert session.has_pending() is False
        events = _ws_events(session.ws, "pending_consumed")
        assert len(events) == 1
        assert events[0]["payload"]["pending"] == [{"pending_id": "p1", "text": "排队问题"}]
        assert events[0]["payload"]["mode"] == "mid_turn"
    finally:
        session_manager._sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_inject_pending_node_tool_gap_graph():
    """完整工具循环接线：agent → tools → inject_pending → agent。

    首次 agent 调用（无工具）不注入；工具执行后的 inject_pending 才注入。
    """
    @tool
    def fake_tool(x: str) -> str:
        """A fake tool for tests."""
        return f"tool-result:{x}"

    captured: list = []

    def fake_model(messages: list) -> AIMessage:
        captured.append(messages)
        has_prior_tool_call = any(
            isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            for m in messages
        )
        if not has_prior_tool_call:
            return AIMessage(content="", tool_calls=[
                {"name": "fake_tool", "args": {"x": "hi"}, "id": "call_1"}
            ])
        return AIMessage(content="final answer")

    model_with_tools = RunnableLambda(fake_model)

    async def ltm_write_noop(state: AgentState, config) -> dict:
        return {}

    builder = StateGraph(AgentState)
    builder.add_node("agent", CallAgentNode(SystemMessage(content="sys"), model_with_tools))
    builder.add_node("tools", ToolNode([fake_tool]))
    builder.add_node("inject_pending", InjectPendingNode())
    builder.add_node("ltm_write", ltm_write_noop)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("tools", "inject_pending")
    builder.add_edge("inject_pending", "agent")
    builder.add_edge("ltm_write", END)
    graph = builder.compile(checkpointer=MemorySaver())

    sid = "inject-tool-sid"
    session = _make_session(sid)
    session.ws = FakeWs()
    session.enqueue_pending(PendingMessage(pending_id="p1", text="排队问题"))
    session_manager.put(sid, session)
    try:
        config = {"configurable": {"thread_id": sid}}
        await graph.ainvoke(
            {"messages": [HumanMessage(content="第一个问题")]}, config
        )

        # 两次 agent 调用：首次不注入，工具间隙后注入
        assert len(captured) == 2
        assert not any(
            isinstance(m, HumanMessage) and m.content == "排队问题"
            for m in captured[0]
        )
        assert any(
            isinstance(m, HumanMessage) and "排队问题" in m.content
            for m in captured[1]
        )
        # 工具结果也进入第二次思考
        assert any(getattr(m, "content", None) == "tool-result:hi" for m in captured[1])

        # 队列已排空 + checkpoint 含注入消息（带后端时间戳）+ 最终回答
        assert session.has_pending() is False
        state = await graph.aget_state(config)
        contents = [str(m.content) for m in state.values["messages"]]
        assert any("排队问题" in c for c in contents)
        assert any("（20" in c for c in contents)  # 后端时间戳尾缀
        assert contents[-1] == "final answer"

        # 前端收到 mid_turn 注入事件
        events = _ws_events(session.ws, "pending_consumed")
        assert len(events) == 1
        assert [p["pending_id"] for p in events[0]["payload"]["pending"]] == ["p1"]
        assert events[0]["payload"]["mode"] == "mid_turn"
    finally:
        session_manager._sessions.pop(sid, None)


# ── run_agent_turn drain 循环 ─────────────────────────────────


@pytest.mark.asyncio
async def test_run_agent_turn_single_invocation(monkeypatch):
    """run_agent_turn 为单次图调用：不再 drain 队列（留给图内 check_pending）。"""
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="q1", text="排队"))
    ws = FakeWs()
    interaction.current_ws.set(ws)

    exec_calls: list[int] = []

    async def fake_build(tools, session, llm_conf, **kw):
        return SimpleNamespace(user_message=kw["user_message"])

    async def fake_execute(ctx, sender, session, llm_conf):
        exec_calls.append(1)
        return _TurnResult(final_answer="ok", error=None)

    class FakeLlmConf:
        llm = None
        model_name = "test"
        max_tokens = 100
        multimodal = False

    monkeypatch.setattr("api.agent.turn._resolve_llm", lambda **kw: FakeLlmConf())
    monkeypatch.setattr("api.agent.turn._build_turn_context", fake_build)
    monkeypatch.setattr("api.agent.turn._execute_agent_turn", fake_execute)

    await run_agent_turn(s, "hi")

    assert len(exec_calls) == 1  # 单次调用
    assert s.has_pending() is True  # 队列留给图内 check_pending 消费
    assert s.has_active_task() is False  # finally 清空 active task
    assert _ws_events(ws, "pending_consumed") == []  # run_agent_turn 不再消费队列


@pytest.mark.asyncio
async def test_run_agent_turn_cancelled_preserves_queue(monkeypatch):
    """取消后 run_agent_turn 不再消费队列（队列保留）。"""
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="q1", text="排队"))
    ws = FakeWs()
    interaction.current_ws.set(ws)

    exec_calls: list[int] = []

    async def fake_build(tools, session, llm_conf, **kw):
        return SimpleNamespace(user_message=kw["user_message"])

    async def fake_execute(ctx, sender, session, llm_conf):
        exec_calls.append(1)
        return _TurnResult(final_answer="", error="CANCELLED")

    class FakeLlmConf:
        llm = None
        model_name = "test"
        max_tokens = 100
        multimodal = False

    monkeypatch.setattr("api.agent.turn._resolve_llm", lambda **kw: FakeLlmConf())
    monkeypatch.setattr("api.agent.turn._build_turn_context", fake_build)
    monkeypatch.setattr("api.agent.turn._execute_agent_turn", fake_execute)

    await run_agent_turn(s, "hi")

    assert len(exec_calls) == 1
    assert s.has_pending() is True  # 队列保留
    assert s.has_active_task() is False


# ── CheckPendingNode 图内多轮循环 ─────────────────────────────


@pytest.mark.asyncio
async def test_check_pending_node_loops_turns():
    """轮末查询点：队列非空时合并注入并跳回 retrieve_memory，形成图内多轮。"""
    captured: list = []

    def fake_model(messages: list) -> AIMessage:
        captured.append(messages)
        return AIMessage(content=f"answer-{len(captured)}")

    model_with_tools = RunnableLambda(fake_model)

    async def retrieve_noop(state: AgentState, config) -> dict:
        return {}

    async def ltm_noop(state: AgentState, config) -> dict:
        return {}

    async def tools_noop(state: AgentState, config) -> dict:
        return {}

    builder = StateGraph(AgentState)
    builder.add_node("retrieve_memory", retrieve_noop)
    builder.add_node("agent", CallAgentNode(SystemMessage(content="sys"), model_with_tools))
    builder.add_node("tools", tools_noop)  # route_after_agent 编译期要求该目标存在
    builder.add_node("ltm_write", ltm_noop)
    builder.add_node("check_pending", CheckPendingNode())
    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("ltm_write", "check_pending")
    builder.add_conditional_edges("check_pending", route_after_check)
    graph = builder.compile(checkpointer=MemorySaver())

    sid = "check-sid"
    session = _make_session(sid)
    session.ws = FakeWs()
    session.enqueue_pending(PendingMessage(pending_id="p1", text="排队问题"))
    session_manager.put(sid, session)
    try:
        config = {"configurable": {"thread_id": sid}}
        await graph.ainvoke(
            {"messages": [HumanMessage(content="第一个问题")]}, config
        )

        # 两次 agent 调用：第二次（跳回后）输入包含排队消息（含后端时间戳）
        assert len(captured) == 2
        assert any(
            isinstance(m, HumanMessage) and "排队问题" in m.content
            for m in captured[1]
        )

        # 队列已排空 + checkpoint 含两条用户消息（带时间戳）与两个回答
        assert session.has_pending() is False
        state = await graph.aget_state(config)
        contents = [str(m.content) for m in state.values["messages"]]
        assert any("第一个问题" in c for c in contents)
        assert any("排队问题" in c for c in contents)
        assert any("（20" in c for c in contents)  # 后端时间戳尾缀
        assert "answer-1" in contents
        assert "answer-2" in contents

        # 逐轮消息计数由 check_pending 完成
        assert session.message_count == 4  # 2 轮 × (user+assistant)

        # 前端收到 pending_consumed(new_turn)
        events = _ws_events(session.ws, "pending_consumed")
        assert len(events) == 1
        assert events[0]["payload"]["mode"] == "new_turn"
        assert events[0]["payload"]["pending"] == [{"pending_id": "p1", "text": "排队问题"}]
        assert events[0]["payload"]["text"] == "排队问题"

        # 逐轮事件由 check_pending 节点按确定顺序推送：
        # answer1 → done1 → pending_consumed(new_turn) → answer2 → done2
        answers = _ws_events(session.ws, "answer")
        assert [a["payload"]["content"] for a in answers] == ["answer-1", "answer-2"]
        dones = _ws_events(session.ws, "done")
        assert len(dones) == 2
        assert [e["type"] for e in session.ws.sent] == [
            "answer", "done", "pending_consumed", "answer", "done",
        ]
    finally:
        session_manager._sessions.pop(sid, None)
