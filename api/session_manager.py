"""会话状态管理 — 多会话隔离 + TTL 过期清理。"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    _active_task: asyncio.Task | None = field(default=None, repr=False)
    checkpointer: MemorySaver = field(default_factory=MemorySaver)
    _graph: CompiledStateGraph | None = field(default=None, repr=False)
    auto_approve: bool = False

    # ── Sub-agent 字段 ─────────────────────────────────────
    is_subagent: bool = False
    parent_session_id: str | None = None
    _sub_agent_task: str | None = field(default=None, repr=False)
    _pending_result: asyncio.Future | None = field(default=None, repr=False)

    # ── Const 固定会话字段 ──────────────────────────────────
    is_const: bool = False
    const_name: str = ""

    # ── _graph 封装 ────────────────────────────────────────────
    def get_graph(self) -> CompiledStateGraph | None:
        """返回缓存的 Agent 编译图，未构建时返回 None。"""
        return self._graph

    def set_graph(self, graph: CompiledStateGraph) -> None:
        """缓存 Agent 编译图（供 undo/重放使用）。"""
        self._graph = graph

    # ── _active_task 封装 ──────────────────────────────────────
    def has_active_task(self) -> bool:
        """Agent 是否正在运行（协程未完成）。"""
        return self._active_task is not None and not self._active_task.done()

    def set_active_task(self, task: asyncio.Task | None) -> None:
        """设置当前 Agent 运行任务。"""
        self._active_task = task

    def clear_active_task(self) -> None:
        """清除 Agent 任务引用。"""
        self._active_task = None

    def cancel_active_task(self) -> None:
        """取消正在运行的 Agent 任务（如存在且未完成）。"""
        if self._active_task is not None and not self._active_task.done():
            self._active_task.cancel()

    # ── _sub_agent_task 封装 ───────────────────────────────────
    def has_sub_agent_task(self) -> bool:
        """是否有子 Agent 任务描述待消费。"""
        return self._sub_agent_task is not None

    def consume_sub_agent_task(self) -> str | None:
        """消费子 Agent 任务描述（一次性取出并清空）。"""
        task = self._sub_agent_task
        self._sub_agent_task = None
        return task

    # ── _pending_result 封装 ───────────────────────────────────
    @property
    def pending_future(self) -> asyncio.Future | None:
        """暴露内部 Future，用于 asyncio.wait_for 等原生操作。"""
        return self._pending_result

    def has_pending_result(self) -> bool:
        """是否有待处理的 Future 且未完成。"""
        return self._pending_result is not None and not self._pending_result.done()

    def is_pending_done(self) -> bool:
        """Future 是否存在且已完成（含成功和异常）。"""
        return self._pending_result is not None and self._pending_result.done()

    def resolve_pending(self, value: str) -> None:
        """以结果值完成子 Agent 的 Future。"""
        if self._pending_result is not None and not self._pending_result.done():
            self._pending_result.set_result(value)

    def fail_pending(self, message: str) -> None:
        """以 RuntimeError 失败子 Agent 的 Future。"""
        if self._pending_result is not None and not self._pending_result.done():
            self._pending_result.set_exception(RuntimeError(message))

    def cancel_pending(self) -> None:
        """取消子 Agent 的 Future。"""
        if self._pending_result is not None and not self._pending_result.done():
            self._pending_result.cancel()

    # ── 公有字段便捷方法 ───────────────────────────────────────
    def constify(self, name: str) -> None:
        """将会话标记为固定会话。"""
        self.is_const = True
        self.const_name = name

    def unconstify(self) -> None:
        """取消固定标记。"""
        self.is_const = False
        self.const_name = ""

    def increment_messages(self, by: int = 2) -> None:
        """增加消息计数（默认 user+assistant 一对）。"""
        self.message_count += by

    def reduce_messages(self, by: int) -> None:
        """减少消息计数（下限 0，用于 undo）。"""
        self.message_count = max(0, self.message_count - by)


class SessionManager:
    def __init__(self, ttl_seconds: int = 1800):
        self._sessions: dict[str, SessionState] = {}
        self._ttl = ttl_seconds

    def create(self) -> SessionState:
        session_id = uuid.uuid4().hex
        session = SessionState(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def create_sub_session(
        self,
        task: str,
        parent_session_id: str | None = None,
    ) -> SessionState:
        """创建 sub-agent 会话，携带任务文本和 pending future。"""
        session_id = uuid.uuid4().hex
        session = SessionState(
            session_id=session_id,
            is_subagent=True,
            parent_session_id=parent_session_id,
            _sub_agent_task=task,
            _pending_result=asyncio.Future(),
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = time.time()
        return session

    def get_or_create(self, session_id: str) -> SessionState:
        session = self.get(session_id)
        if session is None:
            session = SessionState(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[dict]:
        result = []
        for s in self._sessions.values():
            has_active = s.has_active_task()
            result.append(
                {
                    "session_id": s.session_id,
                    "message_count": s.message_count,
                    "created_at": s.created_at,
                    "last_active": s.last_active,
                    "has_active_agent": has_active,
                    "is_subagent": s.is_subagent,
                    "is_const": s.is_const,
                    "const_name": s.const_name,
                }
            )
        result.sort(key=lambda x: x["last_active"], reverse=True)
        return result

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
