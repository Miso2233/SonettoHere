"""WebSocket 注册表 — 为后台任务提供推送事件到指定会话的能力。"""

from fastapi import WebSocket


class WebSocketRegistry:
    """协程安全的 WebSocket 注册表。

    在 websocket_chat() accept 后 register，断开时 unregister。
    所有操作在单线程事件循环中执行，无需加锁。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, WebSocket] = {}

    def register(self, session_id: str, ws: WebSocket) -> None:
        """注册 session_id → WebSocket 映射。"""
        self._sessions[session_id] = ws

    def unregister(self, session_id: str) -> None:
        """移除 session_id 的映射。"""
        self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        """获取指定 session_id 的 WebSocket，不存在时返回 None。"""
        return self._sessions.get(session_id)
