"""WebSocket 端点 — 流式 Agent 对话，含取消、用户交互和多轮上下文。"""

import asyncio
import json
import sys
import traceback
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import build_agent
from agent.prompts import build_system_prompt, get_system_prompt_parts
from api import interaction
from api.callbacks.websocket_callback import WebSocketCallback
from api.const_session_store import save_const_session, serialize_messages
from api.context_usage import estimate_context_usage
from api.session_manager import SessionState
from tools.base import format_error

router = APIRouter()


def _get_provider_context(app_state) -> tuple[int, str]:
    """从 ProviderManager 获取默认 context_window 和 model_name。"""
    mgr = getattr(app_state, "provider_manager", None)
    if mgr is not None and mgr.count > 0:
        for provider in mgr.iter_enabled():
            return provider.config.context_window, provider.default_model
    return 256_000, ""


async def _get_session_messages(session) -> list[dict]:
    """从 LangGraph checkpointer 提取全量会话消息并映射为记忆 Agent 格式。"""
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        if cpt is None:
            return []
        raw = cpt.checkpoint.get("channel_values", {}).get("messages", [])
    except Exception:
        return []

    role_map = {"human": "user", "ai": "assistant", "tool": "tool"}
    result = []
    for m in raw:
        role = role_map.get(m.type)
        if role is None:
            continue
        content = m.content if isinstance(m.content, str) else str(m.content)
        result.append({"role": role, "content": content})
    return result


def _get_final_answer(event) -> str:
    """
    从 on_chain_end 事件提取原始 final_answer，
    返回 content。
    """
    output = event["data"].get("output", {})
    messages = output.get("messages", [])
    if not messages:
        return ""
    raw_final_answer = messages[-1]  # 最后一条message为Final Answer
    final_answer = (
        raw_final_answer.content
        if hasattr(raw_final_answer, "content")
        else str(raw_final_answer)
    )
    return final_answer


async def _stream_turn(
    graph,
    inputs,
    config,
    ws,
    session,
    system_prompt,
    model_name: str | None = None,
    max_tokens: int = 256_000,
) -> str:
    """流式执行 Agent 图，返回最终回答。"""
    final_answer = ""
    async for event in graph.astream_events(inputs, config=config, version="v2"):
        if event.get("event") == "on_chain_end" and event.get("name") == "agent":
            final_answer = _get_final_answer(event)
        # 一轮工具执行完毕，ToolMessage 已写入 checkpoint，推送上下文用量
        if event.get("event") == "on_chain_end" and event.get("name") == "tools":
            usage = await _calculate_context_usage(
                session,
                system_prompt,
                max_tokens=max_tokens,
                model_name=model_name or "",
            )
            await ws.send_json({"type": "context_usage", "payload": usage})

    # 事件未捕获到 final_answer 时，从 checkpoint 兜底提取
    if not final_answer:
        try:
            cpt = await session.checkpointer.aget_tuple(config)
            if cpt is not None:
                messages = cpt.checkpoint.get("channel_values", {}).get("messages", [])
                if messages:
                    last = messages[-1]
                    candidate = last.content if hasattr(last, "content") else str(last)
                    if candidate:
                        final_answer = candidate
        except Exception:
            pass
    return final_answer


async def _calculate_context_usage(
    session,
    system_prompt,
    *,
    max_tokens: int = 256_000,
    model_name: str = "",
) -> dict:
    """
    从 checkpointer 拉取消息列表，估算上下文用量。
    返回字典，包括现用量、最大用量、占比、模型名称。
    """
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
        max_tokens=max_tokens,
        model_name=model_name,
        system_prompt_parts=get_system_prompt_parts(),
    )


async def _inject_cancel_tool_messages(session, config, ws: WebSocket) -> None:
    """为 checkpoint 中孤立的 tool_calls 注入统一格式的正常 ToolMessage，
    并通知前端使对应工具气泡进入错误状态。

    由 CancelledError 处理器调用，确保取消后 checkpoint 状态一致，
    下一条消息不会触发 "tool_calls without corresponding ToolMessage" 错误。

    注入的 ToolMessage 使用 status="success"（默认），content 套用 format_error()
    统一错误响应格式，使 LLM 在下一轮能正确识别工具调用已被取消。

    前端 tool_error 事件：如果对应工具气泡尚在 'running' 状态，则标记为 'error'；
    若工具从未启动过（无对应气泡）则事件被前端静默忽略。

    与 time_traveler.py 的 undo_rounds() 使用同一模式（graph.aupdate_state）。
    注意必需传入 as_node="tools"，否则 aupdate_state 评估路由时会从 model 节点的
    model_to_tools 条件边走，检测到人造 ToolMessage 后返回 "model" 但该边目的地
    不含 "model" 导致 KeyError 使写入失败。
    """
    graph = session._graph
    if graph is None:
        return

    try:
        state = await graph.aget_state(config)
    except Exception:
        return  # checkpoint 不可读时静默跳过

    messages = state.values.get("messages", [])
    if not messages:
        return

    # 从后往前找最后一个 AIMessage
    last_ai = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            last_ai = messages[i]
            break

    if last_ai is None:
        return

    tool_calls = getattr(last_ai, "tool_calls", [])
    if not tool_calls:
        return

    # 收集其后所有 ToolMessage 的 tool_call_id 集合
    try:
        idx = messages.index(last_ai)
    except ValueError:
        return
    following = messages[idx + 1 :]

    tool_msg_ids = {m.tool_call_id for m in following if isinstance(m, ToolMessage)}

    orphaned = [tc for tc in tool_calls if tc["id"] not in tool_msg_ids]
    if not orphaned:
        return  # checkpoint 已一致

    # 通知前端：使运行的工具体进入错误状态
    for tc in orphaned:
        try:
            await ws.send_json(
                {
                    "type": "tool_error",
                    "payload": {
                        "tool_name": tc["name"],
                        "error": "用户取消了该工具调用",
                    },
                }
            )
        except Exception:
            pass  # WebSocket 已断开时静默忽略

    # 生成取消 ToolMessage 并写入 checkpoint
    cancel_msgs = []
    for tc in orphaned:
        cancel_msgs.append(
            ToolMessage(
                content=format_error("用户取消了该工具调用"),
                name=tc["name"],
                tool_call_id=tc["id"],
            )
        )
    try:
        await graph.aupdate_state(config, {"messages": cancel_msgs}, as_node="tools")
    except Exception as e:
        print(
            f"[cancel] aupdate_state failed: {type(e).__name__}: {e}", file=sys.stderr
        )
        raise


async def _run_agent_turn(
    ws: WebSocket,
    session: SessionState,
    user_message: str,
    private_mode: bool = False,
    auto_approve: bool = False,
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
    session.auto_approve = auto_approve
    ws_callback = WebSocketCallback(ws)  # WebUI 回调函数系统

    # 获取默认上下文窗口大小
    default_max_tokens, _ = _get_provider_context(app_state)

    # 动态 LLM 选择（Phase 2：每次消息独立指定提供商/模型）
    current_max_tokens = default_max_tokens
    if provider_id and model_name and hasattr(app_state, "provider_manager"):
        try:
            provider = app_state.provider_manager.get(provider_id)
            llm = provider.create_llm(model_name, temperature=0.7, streaming=True)
            current_model_name = model_name
            current_max_tokens = provider.config.context_window
        except KeyError:
            llm = app_state.llm
            current_model_name = None
    else:
        llm = app_state.llm
        current_model_name = None

    if llm is None:
        await ws.send_json(
            {
                "type": "error",
                "payload": {
                    "code": "NO_LLM",
                    "message": "No LLM provider configured. Add one in Model Settings first.",
                },
            }
        )
        return

    system_prompt = build_system_prompt()
    agent_sonetto = build_agent(
        model=llm,
        tools=app_state.tools,
        system_prompt=system_prompt,
        checkpointer=session.checkpointer,
    )
    session._graph = agent_sonetto
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
        initial_turn_usage = await _calculate_context_usage(
            session,
            system_prompt,
            max_tokens=current_max_tokens,
            model_name=current_model_name or "",
        )
        await ws.send_json({"type": "context_usage", "payload": initial_turn_usage})

        final_answer = await _stream_turn(
            agent_sonetto,
            inputs,
            config,
            ws,
            session,
            system_prompt,
            model_name=current_model_name,
            max_tokens=current_max_tokens,
        )
        await ws.send_json(
            {  # [向前端通信] 1. 向客户端推送最终答案
                "type": "answer",
                "payload": {"content": final_answer},
            }
        )
    except asyncio.CancelledError:
        # 清理 interaction 挂起 Future
        interaction.cancel_all()

        # 修复 checkpoint：为孤立 tool_calls 注入取消 ToolMessage，并通知前端
        try:
            await _inject_cancel_tool_messages(session, config, ws)
        except Exception as e:
            print(f"[cancel] checkpoint cleanup error: {e}", file=sys.stderr)

        await ws.send_json(
            {  # [向前端通信] 2. 通知客户端生成已被取消
                "type": "error",
                "payload": {"code": "CANCELLED", "message": "生成已取消"},
            }
        )
    except Exception as e:
        _run_error = str(e)
        print(
            f"[sub-agent:{session.session_id[:8]}] _run_agent_turn error: {e}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        await ws.send_json(
            {
                "type": "error",
                "payload": {"code": "AGENT_ERROR", "message": str(e)},
            }
        )
    finally:
        session._active_task = None
        context_usage = await _calculate_context_usage(
            session,
            system_prompt,
            max_tokens=current_max_tokens,
            model_name=current_model_name or "",
        )
        turn_id = uuid.uuid4().hex
        await ws.send_json(
            {  # [向前端通信] 3. 推送 turn 结束 + 上下文用量 + turn_id（用于记忆事件关联）
                "type": "done",
                "payload": {
                    "turn_id": turn_id,
                    "context_usage": context_usage,
                },
            }
        )

    # 3. [后处理] 增加消息计数器，将对话记录入长期记忆
    if final_answer:
        session.message_count += 2
    if not private_mode:
        # 传入全会话历史，让记忆 Agent 有更多上下文
        messages_for_memory = await _get_session_messages(session)
        if not messages_for_memory:
            messages_for_memory = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_answer},
            ]
        await app_state.ltm.send_history(
            messages_for_memory,
            session_id=session.session_id,
            turn_id=turn_id,
        )
        print(
            f"[ltm] send_history enqueued session={session.session_id[:8]} turn_id={turn_id[:8]}"
        )

    # 4. [Const 会话] 自动持久化到磁盘 YAML
    if final_answer and session.is_const:
        try:
            cpt = await session.checkpointer.aget_tuple(
                {"configurable": {"thread_id": session.session_id}}
            )
            raw_messages = (
                cpt.checkpoint.get("channel_values", {}).get("messages", [])
                if cpt
                else []
            )
            metadata = {
                "created_at": session.created_at,
                "last_active": session.last_active,
                "message_count": session.message_count,
            }
            serialized = serialize_messages(raw_messages)
            save_const_session(
                session.session_id, session.const_name, metadata, serialized
            )
        except Exception as e:
            print(
                f"[const] 自动保存会话 {session.session_id[:8]} 失败: {e}",
                file=sys.stderr,
            )

    # 5. [Sub-agent] 如果有待处理的 pending_result，resolve 它
    if session._pending_result is not None and not session._pending_result.done():
        if _run_error:
            print(
                f"[sub-agent:{session.session_id[:8]}] resolving pending_result with run error",
                file=sys.stderr,
            )
            session._pending_result.set_exception(
                RuntimeError(f"子 Agent 执行失败: {_run_error}")
            )
        elif final_answer:
            print(
                f"[sub-agent:{session.session_id[:8]}] resolving pending_result with answer",
                file=sys.stderr,
            )
            session._pending_result.set_result(final_answer)
        else:
            print(
                f"[sub-agent:{session.session_id[:8]}] resolving pending_result with exception (empty answer)",
                file=sys.stderr,
            )
            session._pending_result.set_exception(
                RuntimeError("Sub-agent 未能产生有效回答")
            )


def _resume_sub_agent(ws: WebSocket, session: SessionState) -> asyncio.Task | None:
    """WebSocket 重连时，若会话有未完成的 sub-agent 任务则自动恢复执行。"""
    if session._sub_agent_task is None or session._pending_result is None:
        return None
    if session._pending_result.done():
        return None
    task = session._sub_agent_task
    session._sub_agent_task = None  # 消费掉，防止重连后重复启动
    interaction.current_ws.set(ws)
    agent_task = asyncio.create_task(
        _run_agent_turn(ws, session, task, private_mode=False)
    )
    session._active_task = agent_task
    return agent_task


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    """WebSocket 聊天端点 — 接收用户消息、驱动 Agent、处理取消和用户交互。"""
    await ws.accept()

    # 校验 Token（accept 之后检查，避免 403 日志噪声）
    token = ws.query_params.get("token", "")
    expected = ws.app.state.auth_token
    if not expected or token != expected:
        await ws.close(code=4001)
        return

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
                    interaction.auto_approve.set(auto_approve)  # 设置自动批准模式

                    agent_task = asyncio.create_task(
                        _run_agent_turn(
                            ws,
                            session,
                            user_message,
                            private_mode=payload.get("private", False),
                            auto_approve=auto_approve,
                            provider_id=payload.get("provider_id"),
                            model_name=payload.get("model_name"),
                        )
                    )
                    session._active_task = agent_task  # 供外部 REST 接口查询活跃状态

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

    except WebSocketDisconnect:
        pass  # 客户端断开是正常行为
    finally:
        app_state.ws_registry.unregister(session_id)
        if agent_task and not agent_task.done():
            agent_task.cancel()
        session._active_task = None
