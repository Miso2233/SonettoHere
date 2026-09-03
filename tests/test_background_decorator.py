"""测试 background 装饰器（tools/background.py）。

覆盖 schema 注入、sync/async 工具后台 spawn、background=False 直通、
异常终态、get_doc / confirm_execution 叠加顺序，以及 background_update
事件推送与 WebSocket 回调对 spawn 信封的提取。
"""

import asyncio
import json
import time
from typing import Any

import pytest
from pydantic import BaseModel

from api.agent import background as bg
from api.agent import interaction
from tools.background import background
from tools.base import ToolBase


# ── 测试用探针工具 ──────────────────────────────────────────

class ProbeInput(BaseModel):
    seconds: float = 0.0
    fail: bool = False


class ProbeTool(ToolBase):
    name: str = "probe"
    description: str = "probe tool"
    args_schema: type[BaseModel] = ProbeInput

    def _run(self, seconds: float = 0.0, fail: bool = False) -> str:  # type: ignore[override]
        if seconds:
            time.sleep(seconds)
        if fail:
            raise RuntimeError("probe boom")
        return json.dumps({"success": True, "data": {"ran": True}})


class FakeSender:
    """记录 background_update 调用的最小发送器替身。"""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    @classmethod
    def from_context(cls) -> "FakeSender":
        return _CURRENT_FAKE[-1]

    async def background_update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


_CURRENT_FAKE: list[FakeSender] = []


def _use_fake_sender(monkeypatch: pytest.MonkeyPatch, fake: FakeSender) -> None:
    import api.agent.background as bg_module

    _CURRENT_FAKE.append(fake)
    monkeypatch.setattr(bg_module, "ToolSender", FakeSender)


def _setup_session() -> str:
    sid = f"bg-test-{time.time_ns()}"
    interaction.current_session_id.set(sid)
    return sid


# ── schema 注入 ─────────────────────────────────────────────


def test_schema_field_injected() -> None:
    """装饰后 args_schema 注入 background 字段（默认 False），未装饰工具不受影响。"""
    from tools.policies import current_input

    decorated = background(ProbeTool)
    # pydantic 2.13 下类级字段经 model_fields 读取（与 policies.current_input 一致）
    assert "background" in current_input(decorated).model_fields
    assert current_input(decorated).model_fields["background"].default is False
    # 原类不被原地修改（enrich_tool_class 返回新子类）
    assert "background" not in current_input(ProbeTool).model_fields


# ── 直通路径 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_background_false_passthrough() -> None:
    """background=False（或缺省）时行为与未装饰完全一致：等待并返回真实结果。"""
    sid = _setup_session()
    try:
        tool = background(ProbeTool)()
        result = await tool.arun({"seconds": 0})
        assert json.loads(result)["success"] is True
        # 不应产生后台任务
        assert bg.find_registry(sid) is None
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


# ── 后台 spawn（sync 工具） ─────────────────────────────────


@pytest.mark.asyncio
async def test_background_true_returns_index_and_completes() -> None:
    """background=True 立即返回索引信封；后台任务完成后状态流转为 completed。"""
    sid = _setup_session()
    try:
        tool = background(ProbeTool)()
        out = await tool.arun({"seconds": 0.2, "background": True})
        parsed = json.loads(out)
        assert parsed["success"] is True
        data = parsed["data"]
        assert data["background"] is True
        assert data["status"] == "running"
        assert data["hint"]

        index = data["task_index"]
        registry = bg.get_registry(sid)
        bt = registry.get(index)
        assert bt is not None
        assert bt.status == "running"

        bt = await registry.await_result(index, 5)
        assert bt is not None
        assert bt.status == "completed"
        assert json.loads(bt.result)["data"] == {"ran": True}
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_exception_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """后台任务抛异常 → 终态 failed，存储的结果为统一 format_error 格式。"""
    sid = _setup_session()
    fake = FakeSender()
    _use_fake_sender(monkeypatch, fake)
    try:
        tool = background(ProbeTool)()
        out = await tool.arun({"fail": True, "background": True})
        index = json.loads(out)["data"]["task_index"]

        registry = bg.get_registry(sid)
        bt = await registry.await_result(index, 5)

        assert bt is not None and bt.status == "failed"
        assert json.loads(bt.result)["success"] is False
        # 终态事件已推送
        assert fake.updates and fake.updates[-1]["status"] == "failed"
    finally:
        _CURRENT_FAKE.pop()
        bg.cancel_session(sid)
        interaction.current_session_id.set("")
        _CURRENT_FAKE.clear()


@pytest.mark.asyncio
async def test_async_tool_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """async 工具同样可后台化：spawn 返回索引，协程真实结果回写。"""
    sid = _setup_session()
    try:
        class AsyncProbe(ProbeTool):
            async def _arun(self, seconds: float = 0.0, fail: bool = False) -> str:
                await asyncio.sleep(seconds)
                return json.dumps({"success": True, "data": {"async": True}})

        tool = background(AsyncProbe)()
        out = await tool.arun({"background": True})
        index = json.loads(out)["data"]["task_index"]

        registry = bg.get_registry(sid)
        bt = await registry.await_result(index, 5)
        assert bt is not None and bt.status == "completed"
        assert json.loads(bt.result)["data"] == {"async": True}
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_notify_sends_completed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """任务完成后经 ToolSender 推送 background_update（终态 + 结果预览）。"""
    sid = _setup_session()
    fake = FakeSender()
    _use_fake_sender(monkeypatch, fake)
    try:
        tool = background(ProbeTool)()
        out = await tool.arun({"background": True})
        index = json.loads(out)["data"]["task_index"]

        await bg.get_registry(sid).await_result(index, 5)
        assert len(fake.updates) == 1
        update = fake.updates[0]
        assert update["index"] == index
        assert update["status"] == "completed"
        assert "ran" in update["result_preview"]
        assert update["tool_name"] == "probe"
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")
        _CURRENT_FAKE.pop()


# ── 叠加顺序 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_doc_stacks_outer(monkeypatch: pytest.MonkeyPatch) -> None:
    """@get_doc 在外层：get_doc=True 读文档不 spawn；正常调用穿透两层。"""
    sid = _setup_session()
    try:
        from tools.get_doc import get_doc
        from tools.policies import current_input

        stacked = get_doc(background(ProbeTool))
        assert "background" in current_input(stacked).model_fields
        assert "get_doc" in current_input(stacked).model_fields

        tool = stacked()
        doc = await tool.arun({"get_doc": True})
        assert "暂无文档" in doc or "TOOL" in doc
        # 读文档路径未产生后台任务
        assert bg.find_registry(sid) is None

        result = await tool.arun({"seconds": 0})
        assert json.loads(result)["success"] is True
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_confirm_stacks_outer(monkeypatch: pytest.MonkeyPatch) -> None:
    """@confirm_execution 在外层：确认载荷不含 background；approve 后才 spawn。"""
    from tools import confirm as confirm_module
    from tools.confirm import confirm_execution

    sid = f"bg-confirm-{time.time_ns()}"
    interaction.current_session_id.set(sid)  # 真实 sid（registry 需要）；未开 auto_approve → 手动确认

    asked: list[dict[str, Any]] = []
    recorded: dict[str, Any] = {}

    class ConfirmSender:
        @classmethod
        def from_context(cls) -> "ConfirmSender":
            return cls()

        async def ask_user(self, **kwargs: Any) -> None:
            asked.append(kwargs)

    monkeypatch.setattr(confirm_module, "ToolSender", ConfirmSender)

    real_register = interaction.register

    def patched_register() -> tuple[str, asyncio.Future]:
        iid, fut = real_register()
        recorded["id"] = iid
        recorded["future"] = fut
        return iid, fut

    monkeypatch.setattr(interaction, "register", patched_register)

    try:
        stacked = confirm_execution(question="确认？")(background(ProbeTool))
        tool = stacked()
        task = asyncio.create_task(tool.arun({"seconds": 0.1, "background": True}))
        for _ in range(10):  # 公共 arun 需多次让步才进入确认等待
            await asyncio.sleep(0)

        # 确认载荷已剔除 background 字段（INJECTED_KWARGS）
        assert asked and "background" not in asked[0]

        assert interaction.resolve(recorded["id"], {"action": "approve", "reason": ""}) is True
        out = await asyncio.wait_for(task, timeout=5)
        parsed = json.loads(out)
        assert parsed["data"]["background"] is True

        # approve 后才 spawn：任务最终完成
        index = parsed["data"]["task_index"]
        bt = await bg.get_registry(sid).await_result(index, 5)
        assert bt is not None and bt.status == "completed"
    finally:
        interaction.current_session_id.set("")
        bg.cancel_session(sid)


# ── WebSocket 回调：spawn 信封提取 ──────────────────────────


def test_callback_extracts_background_envelope() -> None:
    """on_tool_end 对 spawn 信封输出 background 卡片数据（含入参），优先于按工具提取器。"""
    from api.callbacks.websocket_callback import WebSocketCallback

    spawn_output = json.dumps(
        {
            "success": True,
            "data": {"background": True, "task_index": 7, "status": "running"},
        }
    )
    tool_data = WebSocketCallback._extract_tool_data("tavily_search", spawn_output)
    assert tool_data == {
        "background": {
            "index": 7,
            "status": "running",
            "tool_name": "tavily_search",
            "args": {},
        }
    }

    # 入参元数据：剔除 background 字段后随 tool_data 下发
    tool_data = WebSocketCallback._extract_tool_data(
        "tavily_search",
        spawn_output,
        tool_input='{"query": ".latest AI news", "background": true}',
    )
    assert tool_data is not None
    assert tool_data["background"]["args"] == {"query": ".latest AI news"}

    # 非信封输出仍走按工具注册的提取器
    normal_output = json.dumps({"success": True, "data": {"query": "x", "results": []}})
    tool_data = WebSocketCallback._extract_tool_data("tavily_search", normal_output)
    assert tool_data is not None and "query" in tool_data


@pytest.mark.asyncio
async def test_callback_enriches_await_with_original_extractor() -> None:
    """await_background 完成态：tool_data 携带 original_tool + 原工具提取结果。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)

        async def done() -> str:
            return json.dumps(
                {
                    "success": True,
                    "data": {
                        "query": "q",
                        "answer": "a",
                        "results": [{"url": "u", "title": "t", "content": "c", "score": 1}],
                        "response_time": 0.1,
                    },
                }
            )

        index = registry.register(
            done(), tool_name="tavily_search", args_summary='{"query": "q"}'
        ).index
        await registry.await_result(index, 5)

        from api.callbacks.websocket_callback import WebSocketCallback

        cb = WebSocketCallback(sender=object())
        tool_input = str({"index": index, "timeout_seconds": 180})
        tool_data = cb._enrich_await_tool_data(tool_input, registry.get(index).result, None)

        assert tool_data is not None
        assert tool_data["original_tool"] == "tavily_search"
        assert tool_data["query"] == "q"
        assert isinstance(tool_data["results"], list)
        assert "original_elapsed_s" in tool_data

        # 等待态信封（含 task_index）不被富化，保持原提取
        waiting_output = json.dumps(
            {"success": True, "data": {"task_index": index, "status": "running"}}
        )
        tool_data = cb._enrich_await_tool_data(tool_input, waiting_output, {"keep": 1})
        assert tool_data == {"keep": 1}
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")
