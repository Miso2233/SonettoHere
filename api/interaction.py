"""交互注册表 — 管理 ask_user 系列工具的挂起与唤醒。

工具函数通过 register() 注册一个待交互，返回 interaction_id；
前端通过 user_response 携带同一 ID 送达响应；
resolve() 唤醒挂起的 Future，工具函数继续执行返回结果。
"""

import asyncio
import contextvars
import uuid

# 当前连接对应的 WebSocket 实例（在 chat.py 中设置）
current_ws: contextvars.ContextVar = contextvars.ContextVar("current_ws")

# 全局待处理交互表：interaction_id → (Future, meta)
_pending: dict[str, tuple[asyncio.Future, dict]] = {}


def register(meta: dict) -> str:
    """注册一次待处理的用户交互，返回 interaction_id。"""
    interaction_id = uuid.uuid4().hex
    _pending[interaction_id] = (asyncio.Future(), meta)
    return interaction_id


def consume_future(interaction_id: str) -> asyncio.Future | None:
    """取出 Future 引用，调用者负责 await。不弹出条目，留给 resolve/cleanup 清理。"""
    entry = _pending.get(interaction_id)
    return entry[0] if entry else None


def resolve(interaction_id: str, response) -> bool:
    """用用户响应结果唤醒挂起的 Future。返回是否成功唤醒。"""
    entry = _pending.get(interaction_id)
    if not entry:
        return False
    future, _ = entry
    if future.done():
        return False
    future.set_result(response)
    return True


def cleanup(interaction_id: str):
    """清理（超时或取消时调用）。"""
    _pending.pop(interaction_id, None)
