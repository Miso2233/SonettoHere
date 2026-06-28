"""交互注册表 — 管理 ask_user 系列工具的挂起与唤醒。

工具函数通过 register() 注册一个待交互，返回 interaction_id 和 Future；
前端通过 user_response 携带同一 ID 送达响应；
resolve() 唤醒挂起的 Future，工具函数继续执行返回结果。
"""

import asyncio
import contextvars
import uuid

from tools.base import format_error

# 当前连接对应的 WebSocket 实例（在 chat.py 中设置）
current_ws: contextvars.ContextVar = contextvars.ContextVar("current_ws")

# 当前会话 ID（在 chat.py 中设置），供工具函数查询会话级设置
current_session_id: contextvars.ContextVar = contextvars.ContextVar(
    "current_session_id", default=""
)

# 会话级 auto_approve 设置 —— 使用模块级 dict 而非 ContextVar，
# 以便 WebSocket 主循环在处理 update_auto_approve 消息时写入的值
# 能立即被正在运行的 Agent 任务中的工具函数读取到。
_settings: dict[str, bool] = {}  # session_id -> auto_approve


def set_session_auto_approve(session_id: str, value: bool) -> None:
    """设置指定会话的自动批准模式。所有 asyncio 任务共享此存储。"""
    _settings[session_id] = value


def get_session_auto_approve(session_id: str) -> bool:
    """获取指定会话的自动批准模式。不存在时返回 False（安全的默认值）。"""
    return _settings.get(session_id, False)


def clear_session_settings(session_id: str) -> None:
    """WebSocket 断开时清理会话设置，防止内存泄漏。"""
    _settings.pop(session_id, None)

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
