"""交互注册表 — 管理 ask_user 系列工具的挂起与唤醒。

工具函数通过 register() 注册一个待交互，返回 interaction_id 和 Future；
前端通过 user_response 携带同一 ID 送达响应；
resolve() 唤醒挂起的 Future，工具函数继续执行返回结果。
"""

import asyncio
import contextvars
import uuid

from skills.base import format_error

# 当前连接对应的 WebSocket 实例（在 chat.py 中设置）
current_ws: contextvars.ContextVar = contextvars.ContextVar("current_ws")

# 当前会话的自动批准模式（在 chat.py 中设置）
auto_approve: contextvars.ContextVar = contextvars.ContextVar("auto_approve", default=False)

# 全局待处理交互表：interaction_id → Future
_pending: dict[str, asyncio.Future] = {}


def register() -> tuple[str, asyncio.Future]:
    """注册一次待处理的用户交互，返回 (interaction_id, future)。"""
    interaction_id = uuid.uuid4().hex
    future: asyncio.Future = asyncio.Future()
    _pending[interaction_id] = future
    return interaction_id, future


def resolve(interaction_id: str, response) -> bool:
    """用用户响应结果唤醒并解决挂起的 Future。返回是否成功。"""
    future = _pending.get(interaction_id)
    if not future:
        return False
    if future.done():
        return False
    future.set_result(response)
    return True


def cleanup(interaction_id: str):
    """清理（超时或取消时调用）。"""
    _pending.pop(interaction_id, None)


def cancel_all(reason: str | None = None):
    """将所有挂起的交互 Future 以取消原因标记为已完成，并清空 _pending。

    在取消 Agent 任务时由 _run_agent_turn 的 CancelledError 处理器调用。
    返回值套用统一错误响应格式。
    """
    if reason is None:
        reason = "用户取消了该工具调用"
    formatted = format_error(reason)
    for interaction_id, future in list(_pending.items()):
        if not future.done():
            future.set_result(formatted)
        _pending.pop(interaction_id, None)
