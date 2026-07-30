"""WebSocket 端点 — 连接管理、消息派发。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.agent import interaction
from api.agent.context_usage import estimate_context_usage_from_session
from agent import build_system_prompt
from api.agent.turn import run_agent_turn
from api.events import ChatSender, MemorySender
from api.providers import FALLBACK_CTX
from api.providers.manager import get_manager
from api.session.manager import SessionState, session_manager
from api.utils.logger import get_logger

router = APIRouter()
_log = get_logger("chat")

Handler = Callable[[WebSocket, str, SessionState, asyncio.Task | None, dict], Awaitable[asyncio.Task | None]]


def _resume_sub_agent(ws: WebSocket, session: SessionState) -> asyncio.Task | None:
    """WebSocket 重连时，若会话有未完成的 sub-agent 任务则自动恢复执行。"""
    if not session.has_sub_agent_task() or session.pending_future is None:
        return None
    if session.is_pending_done():
        return None
    task = session.consume_sub_agent_task()
    interaction.current_ws.set(ws)
    agent_task = asyncio.create_task(
        run_agent_turn(session, task, private_mode=False)
    )
    session.set_active_task(agent_task)
    return agent_task


_HANDLERS: dict[str, Handler] = {}

def ws_event_handler(event_type: str):
    """装饰器：将 handler 函数注册到 _HANDLERS 字典。"""
    def decorator(func):
        _HANDLERS[event_type] = func
        return func
    return decorator


# ── 消息处理器 ────────────────────────────────────────────


@ws_event_handler("ping")
async def _handle_ping(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,
) -> asyncio.Task | None:
    """处理 ping 心跳。"""
    await ChatSender.from_context().pong()
    return agent_task


@ws_event_handler("chat")
async def _handle_chat(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,

) -> asyncio.Task | None:
    """处理聊天消息：创建 Agent 轮次。"""
    if agent_task is not None and not agent_task.done():
        return agent_task  # 已有 Agent 运行中，忽略本次输入

    payload = msg["payload"]
    user_message = payload["message"].strip()
    if not user_message:
        return agent_task

    auto_approve = payload.get("auto_approve", False)
    skip_recall = payload.get("skip_recall", False)
    interaction.current_ws.set(ws)  # 供工具函数/Sender.from_context() 通过 WebSocket 推送交互
    interaction.current_session_id.set(session_id)
    interaction.set_session_auto_approve(session_id, auto_approve)

    agent_task = asyncio.create_task(
        run_agent_turn(
            session,
            user_message,
            private_mode=payload.get("private", False),
            provider_id=payload.get("provider_id"),
            model_name=payload.get("model_name"),
            image_recognition=payload.get("image_recognition", False),
            image_refs=payload.get("image_refs", []),
            skip_recall=skip_recall,
        )
    )
    session.set_active_task(agent_task)
    return agent_task


@ws_event_handler("user_response")
async def _handle_user_response(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,

) -> asyncio.Task | None:
    """处理用户交互响应。"""
    payload = msg.get("payload", {})
    interaction_id = payload.get("interaction_id", "")
    response = payload.get("response", "")
    if interaction_id:
        interaction.resolve(interaction_id, response)
    return agent_task


@ws_event_handler("cancel")
async def _handle_cancel(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,

) -> asyncio.Task | None:
    """处理取消请求。"""
    if agent_task is not None and not agent_task.done():
        agent_task.cancel()
    return None


@ws_event_handler("update_auto_approve")
async def _handle_update_auto_approve(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,

) -> asyncio.Task | None:
    """更新自动批准设置。"""
    interaction.set_session_auto_approve(
        session_id, msg["payload"]["auto_approve"]
    )
    return agent_task


@ws_event_handler("skip_memory_search")
async def _handle_skip_memory_search(
    ws: WebSocket,
    session_id: str,
    session: SessionState,
    agent_task: asyncio.Task | None,
    msg: dict,

) -> asyncio.Task | None:
    """处理跳过记忆搜索：通过 interaction.resolve() 唤醒 retrieve_memory 节点的 Future。

    不取消 agent_task——只跳过记忆检索，Agent 图继续执行。
    """
    interaction_id = msg.get("payload", {}).get("interaction_id", "")
    if interaction_id:
        interaction.resolve(interaction_id, "skipped")
        # 立即通知前端已跳过（不等 node 中竞速结束后二次推送）
        sender = MemorySender.from_ws(ws)
        await sender.memory_search_skipped()
    return agent_task


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str) -> None:
    """WebSocket 聊天端点 — 接收消息、派发、生命周期管理。"""
    await ws.accept()
    _log.debug("WebSocket 已连接: session_id=%s", session_id)

    # ── 初始化会话 ────────────────────────────────────────
    session = session_manager.get_or_create(session_id)
    _log.debug("会话状态: id=%s, is_const=%s, const_name=%r, message_count=%d, has_active_task=%s",
               session_id, session.is_const, session.const_name, session.message_count,
               session.has_active_task())
    session.ws = ws  # 供后台记忆 consumer 推送事件
    interaction.current_ws.set(ws)  # 供 ChatSender/TurnSender/CallbackSender 使用

    # ── 推送初始上下文用量 ─────────────────────────────────
    mgr = get_manager()
    default_max_tokens, default_model = mgr.get_default_context() if mgr else (FALLBACK_CTX, "")
    initial_usage = await estimate_context_usage_from_session(
        session,
        build_system_prompt(),
        max_tokens=default_max_tokens,
        model_name=default_model,
    )
    await ChatSender.from_context().context_usage(initial_usage)

    # ── 断线重连时恢复 sub-agent ──────────────────────────
    agent_task = _resume_sub_agent(ws, session)

    # ── 消息主循环（字典派发） ─────────────────────────────
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")
            _log.debug("收到消息: session_id=%s, type=%s", session_id, msg_type)

            handler = _HANDLERS.get(msg_type)
            if handler is not None:
                agent_task = await handler(
                    ws, session_id, session, agent_task, msg
                )
            else:
                _log.debug("未知消息类型: %s", msg_type)

    except WebSocketDisconnect:
        _log.debug("WebSocket 断开: session_id=%s", session_id)
    finally:
        session.ws = None
        _log.debug("清理会话: session_id=%s, agent_task_done=%s",
                   session_id, agent_task is not None and agent_task.done())
        if agent_task is not None and not agent_task.done():
            agent_task.cancel()
        session.clear_active_task()
        interaction.clear_session_settings(session_id)
