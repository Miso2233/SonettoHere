"""WsTransport 基类 — WebSocket 统一发送封装。

提供 _send() 方法统一处理序列化、断开检测、异常日志，
以及 from_ws / from_session / from_session_id / from_context 四种工厂方法。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self

from fastapi import WebSocket, WebSocketDisconnect

from api.agent import interaction
from api.session.manager import session_manager

if TYPE_CHECKING:
    from api.session.manager import SessionState

logger = logging.getLogger(__name__)

# 模块级 WS 锁映射：所有共享同一 ws 连接的 Sender 实例共用一把锁，
# 避免并发写入时 ws.send_json 交错，同时确保锁在 _send() 首次调用时
# 才按需创建，绑定到调用时的事件循环。
_ws_locks: dict[int, asyncio.Lock] = {}


class WsTransport:
    """WebSocket 传输基类。

    所有语义 Sender 子类继承此基类，通过 _send() 发送事件。
    子类只需提供类型安全的命名方法，形如:

        async def answer(self, content: str) -> None:
            await self._send("answer", {"content": content})

    线程安全性：本类通过模块级 ``_ws_locks`` 字典实现按 WebSocket 实例
    粒度的锁，确保所有共享同一 ws 连接的 Sender 实例并发调用 _send() 时
    不会交错写入。锁在 _send() 首次调用时按需创建，绑定调用时的事件循环。
    """

    def __init__(self, ws: WebSocket | None) -> None:
        self._ws = ws

    # ── 工厂方法 ─────────────────────────────────────────────

    @classmethod
    def from_ws(cls, ws: WebSocket) -> Self:
        """从 FastAPI WebSocket 实例创建。"""
        return cls(ws)

    @classmethod
    def from_session_id(cls, session_id: str) -> Self | None:
        """从 session_id 查找会话并获取 WebSocket 引用创建。

        记忆层等无法直接拿到 ws 和 SessionState 的场景使用此方式。
        会话不存在或 ws 已断开时返回 None。
        """
        session = session_manager.get(session_id)
        if session is None or session.ws is None:
            return None
        return cls(session.ws)

    @classmethod
    def from_session(cls, session: SessionState) -> Self | None:
        """从 SessionState 对象直接获取 WebSocket 引用创建。

        调用方已有 SessionState 引用时使用此方式，避免二次查找。
        ws 已断开时返回 None。
        """
        if session.ws is None:
            return None
        return cls(session.ws)

    @classmethod
    def from_context(cls) -> Self | None:
        """从 interaction.current_ws ContextVar 获取。

        工具层（ask_user 系列、sub_agent）使用此方式。
        ContextVar 未设置时返回 None。
        """
        try:
            ws = interaction.current_ws.get()
        except LookupError:
            return None
        return cls(ws)

    # ── 统一发送入口 ─────────────────────────────────────────

    async def _send(self, event_type: str, payload: dict) -> None:
        """统一 WebSocket JSON 发送入口。

        职责：连接断开时自动标记 _ws = None，后续调用自动跳过。
        不会吞没异常——调用方（LangChain 回调/工具层/记忆层）各自负责异常处理。
        """
        if self._ws is None:
            return

        # 按 ws 对象身份获取共享锁，所有指向同一 ws 的 Sender 实例共用，
        # 避免并发写入；锁在首次访问时按需创建，绑定当前事件循环。
        ws_id = id(self._ws)
        if ws_id not in _ws_locks:
            _ws_locks[ws_id] = asyncio.Lock()

        async with _ws_locks[ws_id]:
            try:
                await self._ws.send_json({"type": event_type, "payload": payload})
            except WebSocketDisconnect:
                self._ws = None
                _ws_locks.pop(ws_id, None)
