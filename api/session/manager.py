"""会话状态管理 — 多会话隔离 + TTL 过期清理。"""

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from fastapi import WebSocket
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from api.memory.short_term import get_checkpointer, delete_thread as _delete_memory_thread
from api.utils.logger import get_logger

_log = get_logger("manager")


# ── 子数据类：会话元信息 ──────────────────────────────────────────

@dataclass
class SessionMeta:
    """会话基础元信息：标识、创建/活动时间、消息计数。"""
    session_id: str
    created_at: float
    last_active: float
    message_count: int = 0


# ── 子数据类：Agent 运行时 ────────────────────────────────────────

@dataclass
class AgentRuntime:
    """Agent 运行时状态：活动任务、检查点、编译图。"""
    _active_task: asyncio.Task | None = field(default=None, repr=False)
    checkpointer: MemorySaver | None = field(default=None, repr=False)
    _graph: CompiledStateGraph | None = field(default=None, repr=False)

    # ── _graph 封装 ─────────────────────────────────────────
    def get_graph(self) -> CompiledStateGraph | None:
        """返回缓存的 Agent 编译图，未构建时返回 None。"""
        return self._graph

    def set_graph(self, graph: CompiledStateGraph) -> None:
        """缓存 Agent 编译图（供 undo/重放使用）。"""
        self._graph = graph

    # ── _active_task 封装 ───────────────────────────────────
    def has_active_task(self) -> bool:
        """Agent 是否正在运行（协程未完成）。"""
        return self._active_task is not None and not self._active_task.done()

    def set_active_task(self, task: asyncio.Task | None) -> None:
        """设置当前 Agent 运行任务。"""
        self._active_task = task

    def clear_active_task(self, task: asyncio.Task | None = None) -> None:
        """清除 Agent 任务引用。

        传入 task 时仅当引用指向该任务才清除（owner 守卫），防止
        取消后立刻重发导致旧任务的 finally 覆盖新任务引用。
        """
        if task is None or self._active_task is task:
            self._active_task = None

    def cancel_active_task(self) -> None:
        """取消正在运行的 Agent 任务（如存在且未完成）。"""
        if self._active_task is not None and not self._active_task.done():
            self._active_task.cancel()


# ── 子数据类：Sub-agent 状态 ──────────────────────────────────────

@dataclass
class SubAgentData:
    """Sub-agent 会话状态：标记、任务描述、异步 Future。"""
    is_subagent: bool = False
    _sub_agent_task: str | None = field(default=None, repr=False)
    _pending_result: asyncio.Future | None = field(default=None, repr=False)

    # ── _pending_result 封装 ────────────────────────────────
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

    # ── _sub_agent_task 封装 ────────────────────────────────
    def has_sub_agent_task(self) -> bool:
        """是否有子 Agent 任务描述待消费。"""
        return self._sub_agent_task is not None

    def consume_sub_agent_task(self) -> str | None:
        """消费子 Agent 任务描述（一次性取出并清空）。"""
        task = self._sub_agent_task
        self._sub_agent_task = None
        return task


# ── 子数据类：固定会话 ────────────────────────────────────────────

@dataclass
class ConstSession:
    """固定会话标记与名称。"""
    is_const: bool = False
    const_name: str = ""

    def constify(self, name: str) -> None:
        """将会话标记为固定会话。"""
        self.is_const = True
        self.const_name = name

    def unconstify(self) -> None:
        """取消固定标记。"""
        self.is_const = False
        self.const_name = ""


# ── 子数据类：排队消息 ──────────────────────────────────────────

@dataclass
class PendingMessage:
    """一条被挂起的用户消息（Agent 输出期间发送，等待注入）。

    Attributes:
        pending_id:   唯一标识（前端 client_msg_id 或后端生成的 UUID）。
        text:         消息文本（含时间戳/引用标记，与正常 chat payload 一致）。
        private:      私密模式标记。
        skip_recall:  失忆模式标记。
        auto_approve: 自动批准模式。
        provider_id:  指定 LLM 提供商（可选）。
        model_name:   指定模型（可选）。
        image_recognition: 是否图像认知模式。
        image_refs:   图像文件绝对路径列表。
        created_at:   入队时间。
    """
    pending_id: str
    text: str
    private: bool = False
    skip_recall: bool = False
    auto_approve: bool = False
    provider_id: str | None = None
    model_name: str | None = None
    image_recognition: bool = False
    image_refs: list[str] | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class PendingQueue:
    """Agent 输出期间挂起的用户消息队列（FIFO）。"""
    _items: deque[PendingMessage] = field(default_factory=deque, repr=False)

    def enqueue(self, pm: PendingMessage) -> int:
        """入队，返回 1-based 位置（供前端展示排队序号）。"""
        self._items.append(pm)
        return len(self._items)

    def has_pending(self) -> bool:
        """是否有待处理消息。"""
        return bool(self._items)

    def peek_all(self) -> list[PendingMessage]:
        """非破坏性查看全部待处理消息（供重连同步）。"""
        return list(self._items)

    def drain_all(self) -> list[PendingMessage]:
        """取走并清空全部待处理消息。"""
        items = list(self._items)
        self._items.clear()
        return items

    def remove(self, pending_id: str) -> bool:
        """按 pending_id 移除一条消息，返回是否成功。"""
        for i, pm in enumerate(self._items):
            if pm.pending_id == pending_id:
                del self._items[i]
                return True
        return False

    def clear(self) -> list[PendingMessage]:
        """清空队列并返回被移除的消息（语义与 drain_all 相同）。"""
        return self.drain_all()


# ── 会话状态（组合层）───────────────────────────────────────────

class SessionState:
    """会话状态 — 组合多个子数据类，保持原有外部接口不变。"""

    def __init__(self, session_id: str, **kwargs):
        self.meta = SessionMeta(
            session_id=session_id,
            created_at=kwargs.pop("created_at", time.time()),
            last_active=kwargs.pop("last_active", time.time()),
            message_count=kwargs.pop("message_count", 0),
        )
        self.runtime = AgentRuntime(
            _active_task=kwargs.pop("_active_task", None),
            checkpointer=kwargs.pop("checkpointer", None),
            _graph=kwargs.pop("_graph", None),
        )
        self.sub_agent = SubAgentData(
            is_subagent=kwargs.pop("is_subagent", False),
            _sub_agent_task=kwargs.pop("_sub_agent_task", None),
            _pending_result=kwargs.pop("_pending_result", None),
        )
        self._ws: WebSocket | None = kwargs.pop("ws", None)
        self.const = ConstSession(
            is_const=kwargs.pop("is_const", False),
            const_name=kwargs.pop("const_name", ""),
        )
        self.pending_queue = PendingQueue()
        if kwargs:
            raise TypeError(
                f"__init__() got unexpected keyword arguments: {kwargs}"
            )

    # ── 扁平转发属性 ─────────────────────────────────────────

    @property
    def session_id(self) -> str:
        return self.meta.session_id

    @property
    def created_at(self) -> float:
        return self.meta.created_at

    @property
    def last_active(self) -> float:
        return self.meta.last_active

    @last_active.setter
    def last_active(self, value: float) -> None:
        self.meta.last_active = value

    @property
    def message_count(self) -> int:
        return self.meta.message_count

    async def get_messages(self) -> list[BaseMessage]:
        """获取当前会话的对话消息列表（从全局 checkpointer 按 thread_id 查询）。"""
        cpt = await get_checkpointer().aget_tuple(
            {"configurable": {"thread_id": self.session_id}}
        )
        if cpt is not None:
            return cpt.checkpoint.get("channel_values", {}).get("messages", [])
        return []

    @property
    def is_subagent(self) -> bool:
        return self.sub_agent.is_subagent

    @property
    def is_const(self) -> bool:
        return self.const.is_const

    @property
    def const_name(self) -> str:
        return self.const.const_name

    @property
    def pending_future(self) -> asyncio.Future | None:
        return self.sub_agent.pending_future

    @property
    def ws(self) -> WebSocket | None:
        return self._ws

    @ws.setter
    def ws(self, value: WebSocket | None) -> None:
        self._ws = value

    # ── 转发方法 ─────────────────────────────────────────────

    def get_graph(self) -> CompiledStateGraph | None:
        """返回缓存的 Agent 编译图，未构建时返回 None。"""
        return self.runtime.get_graph()

    def set_graph(self, graph: CompiledStateGraph) -> None:
        """缓存 Agent 编译图（供 undo/重放使用）。"""
        self.runtime.set_graph(graph)

    def has_active_task(self) -> bool:
        """Agent 是否正在运行（协程未完成）。"""
        return self.runtime.has_active_task()

    def set_active_task(self, task: asyncio.Task | None) -> None:
        """设置当前 Agent 运行任务。"""
        self.runtime.set_active_task(task)

    def clear_active_task(self, task: asyncio.Task | None = None) -> None:
        """清除 Agent 任务引用（带 owner 守卫，见 AgentRuntime.clear_active_task）。"""
        self.runtime.clear_active_task(task)

    def cancel_active_task(self) -> None:
        """取消正在运行的 Agent 任务（如存在且未完成）。"""
        self.runtime.cancel_active_task()

    def has_sub_agent_task(self) -> bool:
        """是否有子 Agent 任务描述待消费。"""
        return self.sub_agent.has_sub_agent_task()

    def consume_sub_agent_task(self) -> str | None:
        """消费子 Agent 任务描述（一次性取出并清空）。"""
        return self.sub_agent.consume_sub_agent_task()

    def has_pending_result(self) -> bool:
        """是否有待处理的 Future 且未完成。"""
        return self.sub_agent.has_pending_result()

    def is_pending_done(self) -> bool:
        """Future 是否存在且已完成（含成功和异常）。"""
        return self.sub_agent.is_pending_done()

    def resolve_pending(self, value: str) -> None:
        """以结果值完成子 Agent 的 Future。"""
        self.sub_agent.resolve_pending(value)

    def fail_pending(self, message: str) -> None:
        """以 RuntimeError 失败子 Agent 的 Future。"""
        self.sub_agent.fail_pending(message)

    def cancel_pending(self) -> None:
        """取消子 Agent 的 Future。"""
        self.sub_agent.cancel_pending()

    def constify(self, name: str) -> None:
        """将会话标记为固定会话。"""
        self.const.constify(name)

    def unconstify(self) -> None:
        """取消固定标记。"""
        self.const.unconstify()

    # ── 排队消息转发 ────────────────────────────────────────

    def enqueue_pending(self, pm: PendingMessage) -> int:
        """入队一条挂起消息，返回 1-based 位置。"""
        return self.pending_queue.enqueue(pm)

    def has_pending(self) -> bool:
        """是否有挂起消息待注入。"""
        return self.pending_queue.has_pending()

    def pending_count(self) -> int:
        """挂起消息数量。"""
        return len(self.pending_queue._items)

    def peek_pending(self) -> list[PendingMessage]:
        """非破坏性查看全部挂起消息。"""
        return self.pending_queue.peek_all()

    def drain_pending(self) -> list[PendingMessage]:
        """取走并清空全部挂起消息。"""
        return self.pending_queue.drain_all()

    def remove_pending(self, pending_id: str) -> bool:
        """按 pending_id 移除一条挂起消息，返回是否成功。"""
        return self.pending_queue.remove(pending_id)

    def clear_pending(self) -> list[PendingMessage]:
        """清空挂起队列并返回被移除的消息。"""
        return self.pending_queue.clear()

    def increment_messages(self, by: int = 2) -> None:
        """增加消息计数（默认 user+assistant 一对）。"""
        self.meta.message_count += by

    def reduce_messages(self, by: int) -> None:
        """减少消息计数（下限 0，用于 undo）。"""
        self.meta.message_count = max(0, self.meta.message_count - by)

    def __repr__(self) -> str:
        return (
            f"SessionState(session_id={self.session_id!r}, "
            f"created_at={self.created_at}, "
            f"last_active={self.last_active}, "
            f"message_count={self.message_count}, "
            f"is_subagent={self.is_subagent})"
        )


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
    ) -> SessionState:
        """创建 sub-agent 会话，携带任务文本和 pending future。"""
        session_id = uuid.uuid4().hex
        session = SessionState(
            session_id=session_id,
            is_subagent=True,
            _sub_agent_task=task,
            _pending_result=asyncio.Future(),
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = time.time()
        else:
            _log.debug("get: 会话 %s 不存在", session_id)
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
            _delete_memory_thread(session_id)
            return True
        return False

    def list_sessions(self) -> list[dict]:
        result = []
        const_count = 0
        for s in self._sessions.values():
            has_active = s.has_active_task()
            if s.is_const:
                const_count += 1
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
        _log.debug("list_sessions: 内存中共 %d 个会话, 返回 %d 条, 其中固定会话 %d 个",
                   len(self._sessions), len(result), const_count)
        return result

    def exists(self, session_id: str) -> bool:
        """session_id 是否已存在。"""
        return session_id in self._sessions

    def put(self, session_id: str, session: SessionState) -> None:
        """直接插入会话（用于 const 重建等内部场景）。"""
        self._sessions[session_id] = session

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
            _delete_memory_thread(sid)
        return len(expired)


# ── 模块级单例 ──────────────────────────────────────────────

session_manager = SessionManager()
