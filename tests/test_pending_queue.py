"""测试：流式输出期间消息排队并注入 Agent 上下文。

覆盖：
- SessionState 挂起队列（入队/FIFO/清空/断连存活）
- clear_active_task owner 守卫
- merge_pending_batch 合并逻辑
- _handle_chat 忙碌路径入队 + ack + 重查补启动
- _handle_cancel 清队列 + pending_cancelled
- _start_turn_from_ws FIFO 合并
- CallAgentNode 工具间隙注入（LangGraph 状态持久化）
- run_agent_turn drain 循环（正常续跑 / CANCELLED 中断）
"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import MessagesState

from agent.graph import CallAgentNode
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
    assert kw["queued_pending_ids"] == ["q1", "q2"]  # 仅排队消息（不含 incoming）
    assert s.pending_count() == 0


@pytest.mark.asyncio
async def test_start_turn_from_ws_no_messages_returns_none(monkeypatch):
    s = _make_session()
    monkeypatch.setattr("api.routes.chat.run_agent_turn", lambda *a, **k: None)
    ws = FakeWs()
    assert _start_turn_from_ws(ws, "test-sid", s) is None


# ── CallAgentNode 工具间隙注入 ────────────────────────────────


@pytest.mark.asyncio
async def test_call_agent_node_mid_turn_injection():
    captured: list = []

    def fake_model(messages: list) -> AIMessage:
        captured.append(messages)
        return AIMessage(content="response")

    model_with_tools = RunnableLambda(fake_model)
    node = CallAgentNode(SystemMessage(content="sys"), model_with_tools)

    builder = StateGraph(MessagesState)
    builder.add_node("agent", node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
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

        # (a) 排队文本进入模型输入
        assert any(
            isinstance(m, HumanMessage) and m.content == "排队问题"
            for m in captured[0]
        )
        assert isinstance(captured[0][-1], HumanMessage)  # 注入在响应之前

        # (b) 节点返回值持久化到 checkpoint（含注入消息）
        state = await graph.aget_state(config)
        contents = [m.content for m in state.values["messages"]]
        assert "第一个问题" in contents
        assert "排队问题" in contents
        assert contents[-1] == "response"

        # (c) 队列已排空，且前端收到 mid_turn 注入事件
        assert session.has_pending() is False
        events = _ws_events(session.ws, "pending_consumed")
        assert len(events) == 1
        assert events[0]["payload"]["pending_ids"] == ["p1"]
        assert events[0]["payload"]["mode"] == "mid_turn"
    finally:
        session_manager._sessions.pop(sid, None)


# ── run_agent_turn drain 循环 ─────────────────────────────────


@pytest.mark.asyncio
async def test_run_agent_turn_drains_queue(monkeypatch):
    s = _make_session()
    s.enqueue_pending(PendingMessage(pending_id="q1", text="排队"))
    ws = FakeWs()
    interaction.current_ws.set(ws)

    built_texts: list[str] = []

    async def fake_build(tools, session, llm_conf, **kw):
        built_texts.append(kw["user_message"])
        return SimpleNamespace(user_message=kw["user_message"])

    async def fake_execute(ctx, sender, session, llm_conf):
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

    assert built_texts == ["hi", "排队"]  # 首轮 + 队列合并轮
    assert s.pending_count() == 0
    assert s.has_active_task() is False

    # 合并轮启动前发送 pending_consumed(new_turn)
    events = _ws_events(ws, "pending_consumed")
    assert len(events) == 1
    assert events[0]["payload"]["mode"] == "new_turn"
    assert events[0]["payload"]["text"] == "排队"
    assert events[0]["payload"]["pending_ids"] == ["q1"]


@pytest.mark.asyncio
async def test_run_agent_turn_cancelled_breaks_loop(monkeypatch):
    """CANCELLED 后不得继续启动合并轮。"""
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

    assert len(exec_calls) == 1  # 只执行首轮，未消费队列
    assert s.has_pending() is True  # 队列保留
    assert s.has_active_task() is False  # finally 清空 active task
