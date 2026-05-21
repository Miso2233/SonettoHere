"""WebSocket 端点 — 流式 Agent 对话，含取消、用户交互和多轮上下文。"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from agent.graph import build_agent
from agent.prompts import build_system_prompt
from api import interaction
from api.callbacks.websocket_callback import WebSocketCallback
from api.context_usage import estimate_context_usage
from config.settings import get_settings

router = APIRouter()


def _prepare_turn(app_state, session, enhanced_prompt, user_message, ws_callback):
    """构建 graph、inputs、config，无 I/O。"""
    graph = build_agent(
        model=app_state.llm,
        tools=app_state.tools,
        system_prompt=enhanced_prompt,
        checkpointer=session.checkpointer,
    )
    inputs = {"messages": [HumanMessage(content=user_message)]}
    config = {
        "configurable": {"thread_id": session.session_id},
        "callbacks": [ws_callback],
    }
    return graph, inputs, config


def _get_final_answer(event) -> str:
    """
    从 on_chain_end 事件提取原始 final_answer，
    返回 content。
    """
    output = event["data"].get("output", {})
    messages = output.get("messages", [])
    if not messages:
        return ""
    raw_final_answer = messages[-1] # 最后一条message为Final Answer
    final_answer = raw_final_answer.content if hasattr(raw_final_answer, "content") else str(raw_final_answer)
    return final_answer


async def _stream_turn(graph, inputs, config) -> str:
    """流式执行 Agent 图，返回最终回答。"""
    final_answer = ""
    async for event in graph.astream_events(inputs, config=config, version="v2"):
        if event.get("event") == "on_chain_end" and event.get("name") == "agent":
            final_answer = _get_final_answer(event)
    return final_answer


async def _calculate_context_usage(session, enhanced_prompt) -> dict:
    """
    从 checkpointer 拉取消息列表，估算上下文用量。
    返回字典，包括现用量、最大用量、占比、模型名称。
    """
    settings = get_settings()
    try:
        state = await session.checkpointer.aget_state(
            {"configurable": {"thread_id": session.session_id}}
        )
        counting_messages = state.values.get("messages", [])
    except Exception:
        counting_messages = []

    return estimate_context_usage(
        messages=counting_messages,
        system_prompt=enhanced_prompt,
        max_tokens=settings.model_context_window,
        model_name=settings.model_name,
    )


async def _run_agent_turn(
    ws: WebSocket,
    session,
    user_message: str,
):
    """
    在指定的session中编排一轮 Agent 对话。
    无返回值。
    以内置的 WebSocketCallback回调函数系统作为副作用。
    """
    app_state = ws.app.state            # 应用状态 包含五个属性 所有对话共享
        # app_state.llm	                ChatOpenAI	                LLM 模型实例
        # app_state.system_prompt	    str	                        组装好的系统提示词
        # app_state.tools	            list[BaseTool]	            Agent 可用的工具列表
        # app_state.session_manager	    SessionManager	            会话生命周期管理器（创建/查询/过期清理）
        # app_state.ltm	                LongTermMemoryInterface	    长期记忆接口，send_history() 将对话入队供后台消费写入 MEMORY.md
    ws_callback = WebSocketCallback(ws) # WebUI 回调函数系统
    enhanced_prompt = build_system_prompt()

    graph, inputs, config = _prepare_turn(app_state, session, enhanced_prompt, user_message, ws_callback)

    final_answer = ""
    try:
        final_answer = await _stream_turn(graph, inputs, config)  # 核心运算 执行 Agent 图，返回最终回答，以config回调作为副作用
        await ws.send_json({                                                # [向前端通信] 1. 向客户端推送最终答案
            "type": "answer",
            "payload": {"content": final_answer}
        })
    except asyncio.CancelledError:
        await ws.send_json({                                                # [向前端通信] 2. 通知客户端生成已被取消
            "type": "error",
            "payload": {"code": "CANCELLED", "message": "生成已取消"},
        })
    finally:
        session._active_task = None
        context_usage = await _calculate_context_usage(session, enhanced_prompt)
        await ws.send_json({                                                # [向前端通信] 3. 推送 turn 结束 + 上下文用量
            "type": "done",
            "payload": {
                "context_usage": context_usage,
            },
        })

    if final_answer:
        session.message_count += 2
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

    # 连接建立后立即推送初始上下文用量（尚无 graph 执行，消息为空）
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
                    _run_agent_turn(ws, session, user_message)
                )
                session._active_task = agent_task  # 立即写入，消除竞争窗口

            elif msg_type == "user_response":
                interaction_id = msg["payload"].get("interaction_id", "")
                response = msg["payload"].get("response", "")
                if interaction_id:
                    interaction.resolve(interaction_id, response)

            elif msg_type == "cancel":
                if agent_task and not agent_task.done():
                    agent_task.cancel()
                    agent_task = None

    except WebSocketDisconnect:
        pass
    finally:
        if agent_task and not agent_task.done():
            agent_task.cancel()
        session._active_task = None
