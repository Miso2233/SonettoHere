"""api.events.transport 测试 —— 发送目标解析与传输层故障处理。

核心回归点是 :meth:`WsTransport.from_session_id`：绑定会话的 Sender 必须在
**每次发送时**重新解析该会话当前的连接。记忆消费协程的生命周期远长于一次
请求（LLM 延迟 + 上百条记忆的提示词，数十秒量级），期间用户可能刷新页面、
切换会话或后端重启。若像请求内的 Sender 那样固定构造时的 ws 引用，重连之后
的 ``memory_tool_end`` / ``memory_done`` / ``memory_review_required`` 会全部
发给已死的连接并静默丢弃——前端表现为回调图标永久停在「处理中」、复核卡片
永不出现。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketDisconnect

# api.session.manager 作为解释器首导入会触发 manager→memory→manager 循环
# （api.memory.long_term 反向依赖 SessionState）；先导入 long_term 打破循环。
import api.memory.long_term  # noqa: F401

from api.events.memory import MemorySender


def _ws() -> MagicMock:
    """假 WebSocket：send_json 可断言、可注入异常。"""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


class _FakeSession:
    """只带 ``ws`` 属性的最小会话替身（``_resolve_ws`` 只读这一个字段）。"""

    def __init__(self, ws: Any) -> None:
        self.ws = ws


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> dict[str, _FakeSession]:
    """把 session_manager 的查找换成内存字典：session_id → _FakeSession。

    延迟导入是必须的：``api.session.manager`` 顶层会经 ``api.memory`` 回到
    ``api.session.manager``（循环导入），只能在已有模块加载完之后再取。
    """
    from api.session.manager import session_manager  # noqa: PLC0415

    store: dict[str, _FakeSession] = {}
    monkeypatch.setattr(session_manager, "get", lambda sid: store.get(sid))
    return store


class TestSessionBoundSender:
    """绑定会话的 Sender：跟着重连后的新连接走。"""

    @pytest.mark.asyncio
    async def test_follows_replaced_connection(
        self, sessions: dict[str, _FakeSession]
    ) -> None:
        """重连换掉 ws 后，后续事件必须发给新连接，而不是留在旧连接上。"""
        old, new = _ws(), _ws()
        sessions["s1"] = _FakeSession(old)
        sender = MemorySender.from_session_id("s1")

        await sender.memory_start("t1")
        old.send_json.assert_awaited_once()

        # 重连：会话换上了新连接（旧连接已被替换）
        sessions["s1"].ws = new
        await sender.memory_done("t1")

        new.send_json.assert_awaited_once()
        assert old.send_json.await_count == 1, "旧连接不该再收到任何事件"
        assert sender.ws_id == id(new)

    @pytest.mark.asyncio
    async def test_session_without_connection_is_skipped(
        self, sessions: dict[str, _FakeSession]
    ) -> None:
        """会话不存在或当前无连接时只跳过，不抛出。"""
        sessions["s1"] = _FakeSession(None)
        sender = MemorySender.from_session_id("s1")
        await sender.memory_done("t1")
        await MemorySender.from_session_id("不存在的会话").memory_done("t1")

    @pytest.mark.asyncio
    async def test_dead_connection_does_not_propagate(
        self, sessions: dict[str, _FakeSession]
    ) -> None:
        """对端已断开只记日志：发送失败不得掀翻后台 consumer 协程。"""
        sessions["s1"] = _FakeSession(_ws())
        sessions["s1"].ws.send_json.side_effect = OSError("连接已被对端关闭")
        sender = MemorySender.from_session_id("s1")

        await sender.memory_start("t1")  # 不抛出

        # 会话重连后仍能正常送达（绑定会话的 Sender 不会把自己置空）
        fresh = _ws()
        sessions["s1"].ws = fresh
        await sender.memory_done("t1")
        fresh.send_json.assert_awaited_once()


class TestSnapshotSender:
    """请求内使用的 Sender：固定引用，断开即停止发送。"""

    @pytest.mark.asyncio
    async def test_dead_snapshot_marks_itself_dead(self) -> None:
        ws = _ws()
        ws.send_json.side_effect = WebSocketDisconnect(code=1006)
        sender = MemorySender.from_ws(ws)

        await sender.memory_start("t1")
        assert sender.ws_id is None

        await sender.memory_done("t1")  # 后续调用直接跳过
        assert ws.send_json.await_count == 1
