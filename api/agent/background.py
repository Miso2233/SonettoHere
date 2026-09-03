"""后台任务注册表 — @background 装饰器的任务存储与生命周期管理。

@background 装饰的工具以 ``background=true`` 调用时，真实执行体作为独立
asyncio.Task 转入后台，工具调用本身立即返回一个**任务索引**。本模块维护
每会话的「索引 → 后台任务」表：

- ``register()`` spawn 任务；任务体内回写终态（completed/failed）、唤醒
  等待中的 Future，并通过 WebSocket 推送 ``background_update`` 事件；
- ``await_background`` 工具经 ``await_result()`` 按索引等待/取回真实结果；
- 会话删除 / TTL 过期时由 SessionManager 调 ``cancel_session()`` 清理。

任务表放在模块级 dict（沿 api/agent/interaction.py 模式）而非 SessionState
字段，避免 api.session ↔ api.agent 循环导入。进程重启后任务丢失：等待一个
不存在的索引会得到「任务不存在」错误而非永久挂起。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

from api.events import ToolSender
from api.utils.logger import get_logger
from tools.base import format_error

_log = get_logger("background")

# 单会话后台任务上限：超过后按索引淘汰最旧的**已结束**任务（结果仍可能被
# 再次查看，但不应无限累积）；全部都在运行时允许暂时超出。
_MAX_TASKS: int = 100

# 推送给前端的结果预览长度（完整结果只存服务端，供 await 取回）
_PREVIEW_LEN: int = 200

# 终态状态集合
_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})


def _preview(result: str) -> str:
    if len(result) <= _PREVIEW_LEN:
        return result
    return result[:_PREVIEW_LEN] + "…"


@dataclass
class BackgroundTask:
    """一条后台任务记录。

    ``result`` 存放真实执行体的原始返回值（工具输出信封字符串），completed
    后由 await_background 工具原样返回给 LLM。
    """

    index: int
    tool_name: str
    args_summary: str
    created_at: float = field(default_factory=time.monotonic)
    status: str = "running"  # running | completed | failed
    result: str = ""
    future: asyncio.Future[str] = field(default_factory=asyncio.Future)
    task: asyncio.Task[None] | None = None

    def elapsed(self) -> float:
        """任务从创建到现在的秒数。"""
        return time.monotonic() - self.created_at


class BackgroundTaskRegistry:
    """单会话的后台任务表：索引 → BackgroundTask。"""

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._tasks: dict[int, BackgroundTask] = {}
        self._next_index: int = 1

    # ── spawn 与执行 ─────────────────────────────────────────

    def register(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        tool_name: str,
        args_summary: str,
    ) -> BackgroundTask:
        """将 *coro* 作为独立 asyncio.Task 启动，返回任务记录。

        调用方（@background wrapper）应立即返回索引，不等待本任务完成。
        """
        bt = BackgroundTask(
            index=self._next_index,
            tool_name=tool_name,
            args_summary=args_summary,
        )
        self._next_index += 1
        bt.task = asyncio.create_task(
            self._execute(bt, coro),
            name=f"bg-{self._session_id}-{bt.index}",
        )
        self._tasks[bt.index] = bt
        self._evict_finished()
        return bt

    async def _execute(self, bt: BackgroundTask, coro: Coroutine[Any, Any, Any]) -> None:
        """后台任务体：执行 coro，回写终态、唤醒等待者并推送事件。

        detached 运行——不随发起调用的 turn 结束而取消（这正是后台语义）。
        """
        try:
            result = await coro
            bt.result = result if isinstance(result, str) else str(result)
            bt.status = "completed"
        except asyncio.CancelledError:
            bt.status = "failed"
            bt.result = format_error("后台任务已被取消")
            raise
        except Exception as e:
            bt.status = "failed"
            bt.result = format_error(f"后台任务执行失败: {e}")
        finally:
            if not bt.future.done():
                bt.future.set_result(bt.result)
            await self._notify(bt)

    async def _notify(self, bt: BackgroundTask) -> None:
        """推送 background_update 事件（spawn 气泡上的后台徽章数据源）。

        spawn 经 asyncio.create_task 拷贝了 contextvars，此处 from_context()
        可取到发起会话的 WebSocket；连接已断开时静默跳过。
        """
        try:
            sender = ToolSender.from_context()
            if sender is None:
                return
            await sender.background_update(
                index=bt.index,
                status=bt.status,
                tool_name=bt.tool_name,
                result_preview=_preview(bt.result),
                elapsed_s=bt.elapsed(),
            )
        except Exception:
            _log.exception(
                "background_update 推送失败 (session=%s, index=%d)",
                self._session_id,
                bt.index,
            )

    # ── 查询与等待 ───────────────────────────────────────────

    def get(self, index: int) -> BackgroundTask | None:
        """按索引取任务记录，不存在时返回 None。"""
        return self._tasks.get(index)

    def has_tasks(self) -> bool:
        """当前是否还存在（任意状态的）后台任务。"""
        return bool(self._tasks)

    def describe(self) -> list[dict[str, Any]]:
        """全部任务的概要列表（按索引升序），供 await_background 列表模式。"""
        return [
            {
                "index": bt.index,
                "tool_name": bt.tool_name,
                "args_summary": bt.args_summary,
                "status": bt.status,
                "elapsed_s": round(bt.elapsed(), 1),
            }
            for bt in sorted(self._tasks.values(), key=lambda t: t.index)
        ]

    async def await_result(self, index: int, timeout: float) -> BackgroundTask | None:
        """等待任务进入终态（或超时），返回任务记录；索引不存在时返回 None。

        用 ``shield`` 包住 future：``wait_for`` 超时会取消其等待对象，若不加
        保护，超时会把仍在运行的后台任务的 future 一并取消。
        """
        bt = self._tasks.get(index)
        if bt is None or bt.status != "running":
            return bt
        try:
            await asyncio.wait_for(asyncio.shield(bt.future), timeout)
        except asyncio.TimeoutError:
            pass
        return bt

    # ── 清理 ─────────────────────────────────────────────────

    def cancel_all(self) -> None:
        """取消本会话全部仍在运行的后台任务，并清空任务表（会话删除/TTL 过期时调用）。"""
        for bt in self._tasks.values():
            if bt.task is not None and not bt.task.done():
                bt.task.cancel()
        self._tasks.clear()

    def _evict_finished(self) -> None:
        """任务数达到上限时，按索引淘汰最旧的已结束任务。"""
        while len(self._tasks) >= _MAX_TASKS:
            finished = [
                idx for idx, bt in self._tasks.items() if bt.status in _TERMINAL_STATUSES
            ]
            if not finished:
                return
            del self._tasks[min(finished)]


# ── 模块级注册表：session_id → registry ─────────────────────

_registries: dict[str, BackgroundTaskRegistry] = {}


def get_registry(session_id: str) -> BackgroundTaskRegistry:
    """获取（不存在则创建）会话的后台任务注册表。"""
    registry = _registries.get(session_id)
    if registry is None:
        registry = BackgroundTaskRegistry(session_id)
        _registries[session_id] = registry
    return registry


def find_registry(session_id: str) -> BackgroundTaskRegistry | None:
    """查找会话的后台任务注册表，不存在时返回 None（不创建）。"""
    return _registries.get(session_id)


def cancel_session(session_id: str) -> None:
    """取消并移除会话的全部后台任务（会话删除/TTL 过期时调用）。"""
    registry = _registries.pop(session_id, None)
    if registry is not None:
        registry.cancel_all()
