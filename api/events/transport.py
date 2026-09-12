"""WsTransport 基类 — WebSocket 统一发送封装。

提供 _send() 方法统一处理序列化、断开检测、异常日志，
以及 from_ws / from_session / from_session_id / from_context 四种工厂方法。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self

from fastapi import WebSocket, WebSocketDisconnect

from api.agent import interaction
from api.utils.logger import get_logger

if TYPE_CHECKING:
    from api.session.manager import SessionState

_log = get_logger("ws-send")

# 模块级 WS 锁映射：(id(ws), id(loop)) → asyncio.Lock
# 之所以用二元组作 key，是因为 LangChain 内部有时会创建临时事件循环来调度
# async callback（如 MemoryToolCallback），导致 callback 中的 _send() 与
# 主循环共用同一把锁 → "bound to a different event loop" 错误。
# 按 (ws, loop) 各自持锁，彻底隔离不同循环的锁竞争。
_ws_locks: dict[tuple[int, int], asyncio.Lock] = {}


def _cleanup_ws_locks(ws_id: int) -> None:
    """断开时清理所有涉及给定 ws 的锁条目。"""
    for key in list(_ws_locks.keys()):
        if key[0] == ws_id:
            _ws_locks.pop(key, None)


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

    def __init__(self, ws: WebSocket | None, *, session_id: str | None = None) -> None:
        self._ws = ws
        #: 绑定的会话 ID。设置后**每次发送时**重新解析该会话当前的连接，
        #: 用于生命周期远长于一次请求的发送方（后台记忆 consumer）。
        self._session_id = session_id

    def _resolve_ws(self) -> WebSocket | None:
        """取本次发送应写入的连接。

        未绑定会话的 Sender 用构造时留存的引用（请求内使用，生命周期与连接一致）；
        绑定会话的 Sender 现取 ``session.ws``——连接可能在发送间隙被换掉。
        """
        if self._session_id is None:
            return self._ws
        # 延迟导入：api.session.manager 会经 api.memory 拉入整条依赖链，
        # 顶层导入会与 api.events 包初始化形成循环（events → session → memory → events）。
        from api.session.manager import session_manager  # noqa: PLC0415

        session = session_manager.get(self._session_id)
        return None if session is None else session.ws

    @property
    def ws_id(self) -> int | None:
        """本次发送将写入的连接实例 id；``None`` 表示当前无可用连接。"""
        ws = self._resolve_ws()
        return id(ws) if ws is not None else None

    # ── 工厂方法 ─────────────────────────────────────────────

    @classmethod
    def from_ws(cls, ws: WebSocket) -> Self:
        """从 FastAPI WebSocket 实例创建。"""
        return cls(ws)

    @classmethod
    def from_session_id(cls, session_id: str) -> Self:
        """创建**绑定会话**的发送器：每次发送时现取该会话当前的连接。

        记忆层等无法直接拿到 ws 和 SessionState 的场景使用此方式。

        这里刻意**不**固定 ws 引用：记忆消费协程要跑数秒到数十秒（LLM 延迟 +
        上百条记忆的提示词），期间用户可能刷新页面、切换会话或后端重启，
        连接会被换掉。固定引用会把此后的 ``memory_tool_end`` / ``memory_done`` /
        ``memory_review_required`` 全部发给已死的连接并静默丢弃，前端表现为
        「回调图标永远停在处理中」且「复核卡片永不出现」。按会话现取才能跟上
        重连后的新连接。
        """
        return cls(None, session_id=session_id)

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
        传输层故障（对端已断开等）只记日志不上抛——事件是「尽力送达」的，
        发送失败不该把生产者协程（如记忆 consumer）一起掀翻。
        调用方（LangChain 回调/工具层/记忆层）各自负责逻辑层异常处理。
        """
        ws = self._resolve_ws()
        if ws is None:
            # 只有记忆事件会落到这里（请求内的 Sender 与连接同生命周期）。
            # 留痕是必要的：否则前端只会永远停在「处理中」而没有任何线索。
            _log.warning(
                "事件未送达 type=%s turn_id=%s 原因=会话无活动连接 session=%s",
                event_type, payload.get("turn_id"), self._session_id,
            )
            return

        # 按 (ws, loop) 获取锁，不同循环各自隔离，避免 LangChain 临时
        # 事件循环与主循环共用锁导致的 "bound to a different event loop"。
        ws_id = id(ws)
        loop_id = id(asyncio.get_running_loop())
        key = (ws_id, loop_id)
        if key not in _ws_locks:
            _ws_locks[key] = asyncio.Lock()

        async with _ws_locks[key]:
            try:
                await ws.send_json({"type": event_type, "payload": payload})
            except (WebSocketDisconnect, RuntimeError, OSError) as e:
                # WebSocketDisconnect(1006) 由 starlette 从 OSError 转换而来；
                # RuntimeError 覆盖「close 消息已发出后再 send」的用例。
                # 绑定会话的 Sender 无需置空：下次发送会重新解析新连接。
                if self._session_id is None:
                    self._ws = None
                _cleanup_ws_locks(ws_id)
                _log.warning(
                    "事件发送失败 type=%s turn_id=%s ws=%d err=%r",
                    event_type, payload.get("turn_id"), ws_id, e,
                )
