"""WebSocket 端点 — 连接管理、消息派发。"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api import interaction
from api.agent_turn import (
    run_agent_turn,
    _get_provider_context,
    _calculate_context_usage,
)
from api.session_manager import SessionState

router = APIRouter()


def _resume_sub_agent(ws: WebSocket, session: SessionState) -> asyncio.Task | None:
    """WebSocket 重连时，若会话有未完成的 sub-agent 任务则自动恢复执行。"""
    if not session.has_sub_agent_task() or session.pending_future is None:
        return None
    if session.is_pending_done():
        return None
    task = session.consume_sub_agent_task()
    interaction.current_ws.set(ws)
    agent_task = asyncio.create_task(
        run_agent_turn(ws, session, task, private_mode=False)
    )
    session.set_active_task(agent_task)
    return agent_task


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    """WebSocket 聊天端点 — 接收用户消息、驱动 Agent、处理取消和用户交互。"""
    await ws.accept()

    # ── 初始化会话 ────────────────────────────────────────
    app_state = ws.app.state
    session = app_state.session_manager.get_or_create(session_id)

    # 注册 WebSocket 到注册表，供后台记忆 consumer 推送事件
    app_state.ws_registry.register(session_id, ws)

    # ── 推送初始上下文用量 ─────────────────────────────────
    default_max_tokens, default_model = _get_provider_context(app_state)
    initial_usage = await _calculate_context_usage(
        session,
        app_state.system_prompt,
        max_tokens=default_max_tokens,
        model_name=default_model,
    )
    await ws.send_json({"type": "context_usage", "payload": initial_usage})

    # ── 断线重连时恢复 sub-agent ──────────────────────────
    agent_task = _resume_sub_agent(ws, session)

    # ── 消息主循环 ────────────────────────────────────────
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            match msg.get("type", ""):
                case "ping":
                    await ws.send_json({"type": "pong", "payload": {}})

                case "chat":
                    if agent_task and not agent_task.done():
                        continue  # 已有 Agent 运行中，忽略本次输入

                    payload = msg["payload"]
                    user_message = payload["message"].strip()
                    if not user_message:
                        continue

                    auto_approve = payload.get("auto_approve", False)
                    interaction.current_ws.set(ws)  # 供工具函数通过 WebSocket 推送交互
                    interaction.current_session_id.set(session_id)
                    interaction.set_session_auto_approve(session_id, auto_approve)

                    # 图像认知模式参数
                    image_recognition = payload.get("image_recognition", False)
                    image_refs = payload.get("image_refs", [])

                    agent_task = asyncio.create_task(
                        run_agent_turn(
                            ws,
                            session,
                            user_message,
                            private_mode=payload.get("private", False),
                            auto_approve=auto_approve,
                            provider_id=payload.get("provider_id"),
                            model_name=payload.get("model_name"),
                            image_recognition=image_recognition,
                            image_refs=image_refs,
                        )
                    )
                    session.set_active_task(agent_task)  # 供外部 REST 接口查询活跃状态

                case "user_response":
                    payload = msg.get("payload", {})
                    interaction_id = payload.get("interaction_id", "")
                    response = payload.get("response", "")
                    if interaction_id:
                        interaction.resolve(interaction_id, response)

                case "cancel":
                    if agent_task and not agent_task.done():
                        agent_task.cancel()
                        agent_task = None

                case "update_auto_approve":
                    interaction.set_session_auto_approve(
                        session_id, msg["payload"]["auto_approve"]
                    )
                    session.auto_approve = msg["payload"]["auto_approve"]

    except WebSocketDisconnect:
        pass  # 客户端断开是正常行为
    finally:
        app_state.ws_registry.unregister(session_id)
        if agent_task and not agent_task.done():
            agent_task.cancel()
        session.clear_active_task()
        interaction.clear_session_settings(session_id)
