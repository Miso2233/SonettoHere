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
        now = time.time()
        result = []
        for s in self._sessions.values():
            has_active = (
                s._active_task is not None
                and not s._active_task.done()
            )
            result.append({
                "session_id": s.session_id,
                "message_count": s.message_count,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "has_active_agent": has_active,
                "is_subagent": s.is_subagent,
                "is_const": s.is_const,
                "const_name": s.const_name,
            })
        result.sort(key=lambda x: x["last_active"], reverse=True)
        return result

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
