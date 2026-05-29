"""WebSocket 端点 — 流式 Agent 对话，含取消、用户交互和多轮上下文。"""

import asyncio
import json
import sys
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from agent.graph import build_agent
from agent.prompts import build_system_prompt
from api import interaction
from api.callbacks.websocket_callback import WebSocketCallback
from api.context_usage import estimate_context_usage
from api.session_manager import SessionState
from config.settings import get_settings

router = APIRouter()


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


async def _stream_turn(graph, inputs, config, ws, session, system_prompt, model_name: str | None = None) -> str:
    """流式执行 Agent 图，返回最终回答。"""
    final_answer = ""
    async for event in graph.astream_events(inputs, config=config, version="v2"):
        if event.get("event") == "on_chain_end" and event.get("name") == "agent":
            final_answer = _get_final_answer(event)
        # 一轮工具执行完毕，ToolMessage 已写入 checkpoint，推送上下文用量
        if event.get("event") == "on_chain_end" and event.get("name") == "tools":
            usage = await _calculate_context_usage(session, system_prompt, model_name=model_name)
            await ws.send_json({"type": "context_usage", "payload": usage})
    return final_answer


async def _calculate_context_usage(session, system_prompt, model_name: str | None = None) -> dict:
    """
    从 checkpointer 拉取消息列表，估算上下文用量。
    返回字典，包括现用量、最大用量、占比、模型名称。
    """
    settings = get_settings()
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        if cpt is not None:
            channel_values = cpt.checkpoint.get("channel_values", {})
            counting_messages = channel_values.get("messages", [])
        else:
            counting_messages = []
    except Exception:
        counting_messages = []

    return estimate_context_usage(
        messages=counting_messages,
        system_prompt=system_prompt,
        max_tokens=settings.model_context_window,
        model_name=model_name or settings.model_name,
    )


async def _run_agent_turn(
    ws: WebSocket,
    session: SessionState,
    user_message: str,
    private_mode: bool = False,
    provider_id: str | None = None,
    model_name: str | None = None,
):
    """
    在指定的session中编排一轮 Agent 对话。
    无返回值。
    以内置的 WebSocketCallback回调函数和前端通信系统作为副作用。

    若指定了 provider_id + model_name，则从 ProviderManager 动态创建 LLM；
    否则退化到 app_state.llm 全局 fallback。
    """
    # 1. [准备环境] 从 WebSocket 获取应用状态
    app_state = ws.app.state
    ws_callback = WebSocketCallback(ws) # WebUI 回调函数系统

    # 动态 LLM 选择（Phase 2：每次消息独立指定提供商/模型）
    if provider_id and model_name and hasattr(app_state, 'provider_manager'):
        try:
            provider = app_state.provider_manager.get(provider_id)
            llm = provider.create_llm(model_name, temperature=0.7, streaming=True)
            current_model_name = model_name
        except KeyError:
            llm = app_state.llm
            current_model_name = None
    else:
        llm = app_state.llm
        current_model_name = None

    system_prompt = build_system_prompt()
    agent_sonetto = build_agent(
        model=llm,
        tools=app_state.tools,
        system_prompt=system_prompt,
        checkpointer=session.checkpointer,
    )
    inputs = {"messages": [HumanMessage(content=user_message)]}
    config = {
        "configurable": {"thread_id": session.session_id},
        "callbacks": [ws_callback],
        "recursion_limit": 120,
    }

    # 2. [执行轮次] 流式执行 Agent 图，副作用推送最终回答，另有config回调副作用
    final_answer = ""
    _run_error: str | None = None
    try:
        # turn 开始时推送当前上下文用量（含刚加入的 user message）
        initial_turn_usage = await _calculate_context_usage(session, system_prompt, model_name=current_model_name)
        await ws.send_json({"type": "context_usage", "payload": initial_turn_usage})

        final_answer = await _stream_turn(agent_sonetto, inputs, config, ws, session, system_prompt, model_name=current_model_name)
        await ws.send_json({                                                # [向前端通信] 1. 向客户端推送最终答案
            "type": "answer",
            "payload": {"content": final_answer}
        })
    except asyncio.CancelledError:
        await ws.send_json({                                                # [向前端通信] 2. 通知客户端生成已被取消
            "type": "error",
            "payload": {"code": "CANCELLED", "message": "生成已取消"},
        })
    except Exception as e:
        _run_error = str(e)
        print(f"[sub-agent:{session.session_id[:8]}] _run_agent_turn error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        await ws.send_json({
            "type": "error",
            "payload": {"code": "AGENT_ERROR", "message": str(e)},
        })
    finally:
        session._active_task = None
        context_usage = await _calculate_context_usage(session, system_prompt, model_name=current_model_name)
        await ws.send_json({                                                # [向前端通信] 3. 推送 turn 结束 + 上下文用量
            "type": "done",
            "payload": {
                "context_usage": context_usage,
            },
        })

    # 3. [后处理] 增加消息计数器，将对话记录入长期记忆
    if final_answer:
        session.message_count += 2
    if not private_mode:
        await app_state.ltm.send_history([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": final_answer},
        ])

    # 4. [Sub-agent] 如果有待处理的 pending_result，resolve 它
    if session._pending_result is not None and not session._pending_result.done():
        if _run_error:
            print(f"[sub-agent:{session.session_id[:8]}] resolving pending_result with run error", file=sys.stderr)
            session._pending_result.set_exception(
                RuntimeError(f"子 Agent 执行失败: {_run_error}")
            )
        elif final_answer:
            print(f"[sub-agent:{session.session_id[:8]}] resolving pending_result with answer", file=sys.stderr)
            session._pending_result.set_result(final_answer)
        else:
            print(f"[sub-agent:{session.session_id[:8]}] resolving pending_result with exception (empty answer)", file=sys.stderr)
            session._pending_result.set_exception(
                RuntimeError("Sub-agent 未能产生有效回答")
            )


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    await ws.accept()

    app_state = ws.app.state
    sm = app_state.session_manager
    session = sm.get_or_create(session_id)  # 建立或取得会话

    # 连接建立后立即推送初始上下文用量
    settings = get_settings()
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        existing_messages = cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
    except Exception:
        existing_messages = []
    initial_usage = estimate_context_usage(
        messages=existing_messages,
        system_prompt=app_state.system_prompt,
        max_tokens=settings.model_context_window,
        model_name=settings.model_name,
    )
    await ws.send_json({"type": "context_usage", "payload": initial_usage})

    agent_task: asyncio.Task | None = None  # 局部变量 用于存储当前正在执行的 Agent Task

    # ── Sub-agent 自动启动 ────────────────────────────────
    if session._sub_agent_task is not None and session._pending_result is not None:
        print(f"[ws:{session_id[:8]}] sub-agent detected, auto-starting", file=sys.stderr)
        if session._pending_result.done():
            print(f"[ws:{session_id[:8]}] pending_result already done, skipping", file=sys.stderr)
            pass
        else:
            task = session._sub_agent_task
            session._sub_agent_task = None  # 消费掉，防止重连后重复启动
            interaction.current_ws.set(ws)
            agent_task = asyncio.create_task(
                _run_agent_turn(ws, session, task, private_mode=False)
            )
            session._active_task = agent_task
            print(f"[ws:{session_id[:8]}] sub-agent task created", file=sys.stderr)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            match msg_type:
                case "ping":
                    await ws.send_json({"type": "pong", "payload": {}})

                case "chat":
                    if agent_task and not agent_task.done():
                        continue  # 已有 Agent 运行中，忽略此次输入

                    payload = msg["payload"]
                    user_message = payload["message"].strip()
                    if not user_message:
                        continue

                    private_mode = payload.get("private", False)
                    provider_id = payload.get("provider_id")
                    model_name = payload.get("model_name")

                    # 设置当前连接的上下文变量，供工具函数使用
                    interaction.current_ws.set(ws)

                    agent_task = asyncio.create_task(
                        _run_agent_turn(ws, session, user_message, private_mode, provider_id, model_name)
                    )
                    session._active_task = agent_task  # 立即写入，消除竞争窗口 会话状态 供外部读取 典型用法为绿色黄色呼吸灯

                case "user_response":
                    interaction_id = msg["payload"].get("interaction_id", "")
                    response = msg["payload"].get("response", "")
                    if interaction_id:
                        interaction.resolve(interaction_id, response)

                case "cancel":
                    if agent_task and not agent_task.done():
                        agent_task.cancel()
                        agent_task = None

    except WebSocketDisconnect:
        pass
    finally:
        if agent_task and not agent_task.done():
            agent_task.cancel()
        session._active_task = None
