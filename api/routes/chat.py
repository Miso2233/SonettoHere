"""WebSocket 端点 — 流式 Agent 对话，含取消、用户交互和多轮上下文。"""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import build_agent
from agent.prompts import build_enhanced_prompt
from api import interaction
from api.callbacks.websocket_callback import WebSocketCallback, _extract_content
from api.context_usage import estimate_context_usage
from config.settings import get_settings

router = APIRouter()


async def _run_agent_turn(
    ws: WebSocket,
    session,
    app_state,
    user_message: str,
):
    """在后台任务中执行一轮 Agent 对话。"""
    app_state = ws.app.state
    ws_callback = WebSocketCallback(ws)
    turn_id = uuid.uuid4().hex

    enhanced_prompt = build_enhanced_prompt(
        app_state.system_prompt, user_message
    )

    graph = build_agent(
        model=app_state.llm,
        tools=app_state.tools,
        system_prompt=enhanced_prompt,
    )

    history = session.short_term_memory.messages
    inputs = {
        "messages": history + [HumanMessage(content=user_message)]
    }

    config = {
        "configurable": {"thread_id": session.session_id},
        "callbacks": [ws_callback],
    }

    session.message_history.append(
        {"role": "user", "content": user_message}
    )

    final_answer = ""
    try:
        task = asyncio.current_task()
        if task:
            session._active_task = task

        async for event in graph.astream_events(
            inputs, config=config, version="v2"
        ):
            kind = event.get("event", "")
            name = event.get("name", "")

            if kind == "on_tool_end":
                output = event["data"].get("output", "")
                out_str = _extract_content(output)
                if len(out_str) > 300:
                    out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"
                session.message_history.append(
                    {"role": "tool", "content": out_str}
                )

            elif kind == "on_chain_end" and name == "agent":
                output = event["data"].get("output", {})
                messages = output.get("messages", [])
                if messages:
                    last = messages[-1]
                    final_answer = (
                        last.content
                        if hasattr(last, "content")
                        else str(last)
                    )
                    await ws.send_json({
                        "type": "answer",
                        "payload": {"content": final_answer},
                    })
                    session.message_history.append(
                        {"role": "assistant", "content": final_answer}
                    )

    except asyncio.CancelledError:
        await ws.send_json({
            "type": "error",
            "payload": {
                "code": "CANCELLED",
                "message": "生成已取消",
            },
        })
    finally:
        session._active_task = None
        settings = get_settings()
        context_usage = estimate_context_usage(
            messages=session.short_term_memory.messages,
            system_prompt=enhanced_prompt,
            max_tokens=settings.model_context_window,
            model_name=settings.model_name,
        )
        await ws.send_json({
            "type": "done",
            "payload": {
                "turn_id": turn_id,
                "context_usage": context_usage,
            },
        })

    session.short_term_memory.add_message(
        HumanMessage(content=user_message)
    )
    if final_answer:
        session.short_term_memory.add_message(
            AIMessage(content=final_answer)
        )

    await app_state.ltm.send_history([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": final_answer},
    ])


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    await ws.accept()

    app_state = ws.app.state
    sm = app_state.session_manager
    session = sm.get_or_create(session_id)

    # 连接建立后立即推送初始上下文用量
    settings = get_settings()
    initial_usage = estimate_context_usage(
        messages=[],
        system_prompt=app_state.system_prompt,
        max_tokens=settings.model_context_window,
        model_name=settings.model_name,
    )
    await ws.send_json({"type": "context_usage", "payload": initial_usage})

    agent_task: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong", "payload": {}})

            elif msg_type == "chat":
                if agent_task and not agent_task.done():
                    continue  # 已有 Agent 运行中，忽略此次输入

                user_message = msg["payload"]["message"].strip()
                if not user_message:
                    continue

                # 设置当前连接的上下文变量，供工具函数使用
                interaction.current_ws.set(ws)

                agent_task = asyncio.create_task(
                    _run_agent_turn(ws, session, app_state, user_message)
                )

            elif msg_type == "user_response":
                interaction_id = msg["payload"].get("interaction_id", "")
                response = msg["payload"].get("response", "")
                if interaction_id:
                    interaction.resolve(interaction_id, response)

            elif msg_type == "cancel":
                if agent_task and not agent_task.done():
                    agent_task.cancel()
                    agent_task = None
                if session._active_task:
                    session._active_task.cancel()
                    session._active_task = None

    except WebSocketDisconnect:
        pass
    finally:
        if agent_task and not agent_task.done():
            agent_task.cancel()
        session._active_task = None
