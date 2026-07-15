"""Agent 对话编排 — 构建 Agent 图、流式执行、取消处理与记忆持久化。"""

import asyncio
import base64
import sys
import traceback
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import Sonetto, build_agent
from agent.prompts import build_system_prompt
from api import interaction
from api.callbacks.websocket_callback import WebSocketCallback
from api.const_session_store import save_const_session, serialize_messages
from api.context_usage import estimate_context_usage_from_session
from api.session_manager import SessionState
from tools.base import format_error
from tools.network.tool_image_understand import load_image_bytes, get_mime_type

from api.providers import FALLBACK_CTX
from api.providers.manager import ProviderManager
from langchain_core.language_models.chat_models import BaseChatModel


# ── 内部数据对象 ──────────────────────────────────────────


@dataclass
class _LlmConfig:
    """LLM 实例及上下文窗口配置。"""
    llm: BaseChatModel
    model_name: str
    max_tokens: int


@dataclass
class _TurnContext:
    """一轮 Agent 执行所需的全部上下文。"""
    system_prompt: str
    agent: Sonetto
    inputs: dict[str, list[HumanMessage]]
    config: dict[str, Any]


@dataclass
class _TurnResult:
    """一轮 Agent 执行的结果。"""
    final_answer: str
    turn_id: str
    error: str | None


# ── 叶子辅助函数 ──────────────────────────────────────────


def _get_final_answer(event: dict[str, Any]) -> str:
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


async def _inject_cancel_tool_messages(session: SessionState, config: dict[str, Any], ws: WebSocket) -> None:
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
    graph = session.get_graph()
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


async def _stream_turn(
    graph: Sonetto,
    inputs: dict[str, list[HumanMessage]],
    config: dict[str, Any],
    ws: WebSocket,
    session: SessionState,
    system_prompt: str,
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
            usage = await estimate_context_usage_from_session(
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


# ── 阶段 1：LLM 解析 ──────────────────────────────────────


def _resolve_llm(app_state: Any, provider_id: str | None, model_name: str | None) -> _LlmConfig | None:
    """从 ProviderManager 解析 LLM 实例及上下文窗口配置。

    优先使用指定的 provider_id + model_name 创建 LLM，
    否则回退到 app_state.default_llm。
    返回 None 表示无可用的 LLM。
    """
    mgr: ProviderManager | None = getattr(app_state, "provider_manager", None)
    llm: BaseChatModel | None = app_state.default_llm
    resolved_model = model_name or ""
    max_tokens = FALLBACK_CTX

    if mgr and provider_id and model_name:
        result = mgr.create_llm(provider_id, model_name, temperature=0.7, streaming=True)
        if result:
            llm, resolved_model, max_tokens = result

    return _LlmConfig(llm=llm, model_name=resolved_model, max_tokens=max_tokens) if llm else None


# ── 阶段 2：构建 Agent 与输入 ──────────────────────────────


async def _build_turn_context(
    app_state: Any,
    session: SessionState,
    ws: WebSocket,
    llm_conf: _LlmConfig,
    user_message: str,
    image_recognition: bool,
    image_refs: list[str] | None,
) -> _TurnContext:
    """构建 Agent 图、输入消息和执行配置。"""
    system_prompt = build_system_prompt()
    ws_callback = WebSocketCallback(ws)

    agent = build_agent(
        model=llm_conf.llm,
        tools=app_state.tools,
        system_prompt=system_prompt,
        checkpointer=session.checkpointer,
    )
    session.set_graph(agent)

    # 多模态输入
    if image_recognition and image_refs:
        content_parts: list[dict] = [{"type": "text", "text": user_message}]
        for img_path in image_refs:
            if not img_path.strip():
                continue
            try:
                image_bytes, mime = load_image_bytes(f"local:{img_path}")
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                })
            except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
                print(f"[image_recognition] 跳过无法加载的图片 {img_path}: {e}", file=sys.stderr)
                continue
        inputs = {"messages": [HumanMessage(content=content_parts)]}
    else:
        inputs = {"messages": [HumanMessage(content=user_message)]}

    config = {
        "configurable": {"thread_id": session.session_id},
        "callbacks": [ws_callback],
        "recursion_limit": 120,
    }

    return _TurnContext(system_prompt=system_prompt, agent=agent, inputs=inputs, config=config)


# ── 阶段 3：执行轮次 ──────────────────────────────────────


async def _execute_agent_turn(
    ctx: _TurnContext,
    ws: WebSocket,
    session: SessionState,
    llm_conf: _LlmConfig,
) -> _TurnResult:
    """流式执行 Agent 轮次，处理取消与异常，返回结果。"""
    final_answer = ""
    error: str | None = None
    turn_id = ""

    try:
        # 推送初始上下文用量（含刚加入的 user message）
        initial_usage = await estimate_context_usage_from_session(
            session, ctx.system_prompt,
            max_tokens=llm_conf.max_tokens, model_name=llm_conf.model_name,
        )
        await ws.send_json({"type": "context_usage", "payload": initial_usage})

        final_answer = await _stream_turn(
            ctx.agent, ctx.inputs, ctx.config, ws, session,
            ctx.system_prompt, model_name=llm_conf.model_name, max_tokens=llm_conf.max_tokens,
        )
        await ws.send_json({"type": "answer", "payload": {"content": final_answer}})

    except asyncio.CancelledError:
        interaction.cancel_all()
        try:
            await _inject_cancel_tool_messages(session, ctx.config, ws)
        except Exception as e:
            print(f"[cancel] checkpoint cleanup error: {e}", file=sys.stderr)
        await ws.send_json({"type": "error", "payload": {"code": "CANCELLED", "message": "生成已取消"}})

    except Exception as e:
        error = str(e)
        print(f"[sub-agent:{session.session_id[:8]}] run_agent_turn error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        await ws.send_json({"type": "error", "payload": {"code": "AGENT_ERROR", "message": str(e)}})

    finally:
        session.clear_active_task()
        context_usage = await estimate_context_usage_from_session(
            session, ctx.system_prompt,
            max_tokens=llm_conf.max_tokens, model_name=llm_conf.model_name,
        )
        turn_id = uuid.uuid4().hex
        await ws.send_json({"type": "done", "payload": {"turn_id": turn_id, "context_usage": context_usage}})

    return _TurnResult(final_answer=final_answer, turn_id=turn_id, error=error)


# ── 阶段 4：后处理 ────────────────────────────────────────


async def _postprocess_turn(
    app_state: Any,
    session: SessionState,
    result: _TurnResult,
    user_message: str,
    private_mode: bool,
) -> None:
    """后处理：消息计数、长期记忆持久化、Const 会话保存、Sub-agent 结果回调。"""
    if result.final_answer:
        session.increment_messages()

    if not private_mode:
        await app_state.ltm.send_history_from_session(
            session, turn_id=result.turn_id, user_message=user_message, final_answer=result.final_answer,
        )

    # Const 会话持久化
    if result.final_answer and session.is_const:
        try:
            cpt = await session.checkpointer.aget_tuple(
                {"configurable": {"thread_id": session.session_id}}
            )
            raw_messages = cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
            metadata = {
                "created_at": session.created_at,
                "last_active": session.last_active,
                "message_count": session.message_count,
            }
            save_const_session(session.session_id, session.const_name, metadata, serialize_messages(raw_messages))
        except Exception as e:
            print(f"[const] 自动保存会话 {session.session_id[:8]} 失败: {e}", file=sys.stderr)

    # Sub-agent pending 结果回调
    if session.has_pending_result():
        if result.error:
            print(f"[sub-agent:{session.session_id[:8]}] resolving pending_result with run error", file=sys.stderr)
            session.fail_pending(f"子 Agent 执行失败: {result.error}")
        elif result.final_answer:
            print(f"[sub-agent:{session.session_id[:8]}] resolving pending_result with answer", file=sys.stderr)
            session.resolve_pending(result.final_answer)
        else:
            session.fail_pending("Sub-agent 未能产生有效回答")


# ═══════════════════════════════════════════════════════════
# 公共接口（最顶层：仅编排，不包含逻辑）
# ═══════════════════════════════════════════════════════════


async def run_agent_turn(
    ws: WebSocket,
    session: SessionState,
    user_message: str,
    private_mode: bool = False,
    provider_id: str | None = None,
    model_name: str | None = None,
    image_recognition: bool = False,
    image_refs: list[str] | None = None,
):
    """编排一轮 Agent 对话。

    分 4 个阶段执行：
      1. _resolve_llm        — 解析 LLM 与上下文窗口配置
      2. _build_turn_context  — 构建 Agent 图、多模态输入与运行配置
      3. _execute_agent_turn  — 流式执行、异常/取消处理
      4. _postprocess_turn    — 消息计数、记忆持久化、Const 保存、Sub-agent 回调
    """
    app_state = ws.app.state

    # 1. 解析 LLM 配置
    llm_conf = _resolve_llm(app_state, provider_id, model_name)
    if llm_conf is None:
        await ws.send_json({
            "type": "error",
            "payload": {
                "code": "NO_LLM",
                "message": "No LLM provider configured. Add one in Model Settings first.",
            },
        })
        return

    # 2. 构建执行上下文
    ctx = await _build_turn_context(app_state, session, ws, llm_conf, user_message, image_recognition, image_refs)

    # 3. 执行轮次
    result = await _execute_agent_turn(ctx, ws, session, llm_conf)

    # 4. 后处理
    await _postprocess_turn(app_state, session, result, user_message, private_mode)
