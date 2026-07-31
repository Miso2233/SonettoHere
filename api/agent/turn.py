"""Agent 对话编排 — 构建 Agent 图、流式执行、取消处理与记忆持久化。"""

import asyncio
import base64
import datetime
import re
import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import Sonetto, build_agent, build_system_prompt
from api.agent import interaction
from api.agent.context_usage import estimate_context_usage_from_session
from api.events import CallbackSender, TurnSender
from api.callbacks.websocket_callback import WebSocketCallback
from api.providers import FALLBACK_CTX
from api.providers.manager import get_manager
from api.providers.default_llm import get_default_llm
from api.providers.manager import ProviderManager
from api.session.const_store import save_const_session, serialize_messages
from api.session.manager import PendingMessage, SessionState
from api.memory.short_term import get_checkpointer
from langchain_core.language_models.chat_models import BaseChatModel
from tools.base import format_error
from tools.network.tool_image_understand import load_image_bytes, get_mime_type
from api.utils.logger import get_logger

_log = get_logger("turn")


# ── 内部数据对象 ──────────────────────────────────────────


@dataclass
class _LlmConfig:
    """LLM 实例及上下文窗口配置。

    Attributes:
        llm:        LangChain 聊天模型实例
        model_name: 当前使用的模型名称（如 gpt-4o、deepseek-chat）
        max_tokens: 模型的最大上下文窗口大小（token 数）
        multimodal: 当前 LLM 是否支持多模态（视觉能力）
    """
    llm: BaseChatModel
    model_name: str
    max_tokens: int
    multimodal: bool = False


@dataclass
class _TurnContext:
    """一轮 Agent 执行所需的全部上下文（构建后不可变）。

    Attributes:
        system_prompt: 当前会话的系统提示词
        agent:         编译后的 LangGraph Agent (Sonetto)
        inputs:        本轮输入消息字典（含 HumanMessage 列表）
        config:        运行配置（thread_id、callbacks、recursion_limit）
        turn_id:       本轮唯一标识（UUID hex），用于关联记忆事件
    """
    system_prompt: str
    agent: Sonetto
    inputs: dict[str, list[HumanMessage]]
    config: dict[str, Any]
    turn_id: str


@dataclass
class _TurnResult:
    """一轮 Agent 执行的结果。

    Attributes:
        final_answer: Agent 产出的最终文本回答（空串表示无回答）
        error:        执行过程中抛出的异常信息；成功时为 None
    """
    final_answer: str
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


# ── 排队消息合并 ──────────────────────────────────────────

# 消息尾部时间标记（与前端 web/src/utils/references.ts TIME_SUFFIX_RE 一致）
_TIME_SUFFIX_RE = re.compile(r"（\d{4}-\d{2}-\d{2} \w{3} \d{2}:\d{2}）$")


def _strip_time_suffix(text: str) -> str:
    """剥离消息尾部的时间标记（如「（2026-07-29 Wed 14:30）」。"""
    return _TIME_SUFFIX_RE.sub("", text).rstrip()


def now_timestamp() -> str:
    """当前服务器时间尾缀，如（2026-07-31 Fri 10:24）。

    时间戳是必须进入 LLM 上下文的输入数据（Agent 需感知当前时间以回答
    时间相关查询），由后端统一生成，前端不再拼接。
    """
    now = datetime.datetime.now()
    wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][now.weekday()]
    return f"（{now.year:04d}-{now.month:02d}-{now.day:02d} {wd} {now.hour:02d}:{now.minute:02d}）"


def merge_pending_batch(batch: list[PendingMessage]) -> tuple[str, bool, list[str] | None]:
    """将一批排队消息合并为单个 Agent 输入（合并处理语义）。

    返回 ``(text, image_recognition, image_refs)``：
    - 文本以空行（\\n\\n）连接（消息文本已不含时间戳，时间戳由注入侧统一追加）；
    - 图片标记 OR 累积——任一消息启用图像认知则整体启用，路径全部合并。
    """
    text = "\n\n".join(_strip_time_suffix(p.text) for p in batch)
    images = [
        img
        for p in batch
        if p.image_recognition
        for img in (p.image_refs or [])
    ]
    return text, bool(images), images or None


async def _inject_cancel_tool_messages(session: SessionState, config: dict[str, Any], sender: TurnSender) -> None:
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
            await sender.tool_error(tc["name"], "用户取消了该工具调用")
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
        _log.error("aupdate_state failed: %s: %s", type(e).__name__, e)
        raise


async def _stream_turn(
    graph: Sonetto,
    inputs: dict[str, list[HumanMessage]],
    config: dict[str, Any],
    sender: TurnSender,
    session: SessionState,
    system_prompt: str,
    model_name: str | None = None,
    max_tokens: int = 256_000,
) -> str:
    """流式执行 Agent 图，返回最终回答。

    图的逐轮 answer/done/pending_consumed 事件由轮末查询点（check_pending）
    在节点内按序推送（顺序确定）；此处仅消费流式事件、提取最终回答。
    """
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
            await sender.context_usage(usage)

    # 事件未捕获到 final_answer 时，从 checkpoint 兜底提取
    if not final_answer:
        try:
            messages = await session.get_messages()
            if messages:
                last = messages[-1]
                candidate = last.content if hasattr(last, "content") else str(last)
                if candidate:
                    final_answer = candidate
        except Exception:
            pass
    return final_answer


# ── 阶段 1：LLM 解析 ──────────────────────────────────────


def _resolve_llm(
    provider_manager: ProviderManager | None,
    default_llm: BaseChatModel | None,
    provider_id: str | None,
    model_name: str | None,
) -> _LlmConfig | None:
    """解析 LLM 实例及上下文窗口配置。

    优先使用指定的 provider_id + model_name 创建 LLM，
    否则回退到 default_llm（全局 fallback）。
    返回 None 表示无可用的 LLM。
    """
    llm: BaseChatModel | None = default_llm
    resolved_model = model_name or ""
    max_tokens = FALLBACK_CTX
    multimodal = False

    if provider_manager and provider_id and model_name:
        custom_llm = provider_manager.create_llm(provider_id, model_name, temperature=0.7, streaming=True)
        if custom_llm:
            llm = custom_llm

    # 查询当前 LLM 元数据（上下文窗口、多模态能力等）
    if provider_manager and resolved_model:
        meta = provider_manager.get_model_metadata(provider_id, resolved_model)
        max_tokens = meta["max_tokens"]  # type: ignore[assignment]
        multimodal = meta["multimodal"]  # type: ignore[assignment]

    return _LlmConfig(llm=llm, model_name=resolved_model, max_tokens=max_tokens, multimodal=multimodal) if llm else None


# ── 阶段 2：构建 Agent 与输入 ──────────────────────────────


async def _build_turn_context(
    tools: list,
    session: SessionState,
    llm_conf: _LlmConfig,
    user_message: str,
    image_recognition: bool,
    image_refs: list[str] | None,
    ltm: Any | None = None,
    private_mode: bool = False,
    skip_recall: bool = False,
) -> _TurnContext:
    """构建 Agent 图、输入消息和执行配置。"""
    system_prompt = build_system_prompt()
    cb_sender = CallbackSender.from_context()
    ws_callback = WebSocketCallback(cb_sender)

    agent = build_agent(
        model=llm_conf.llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=get_checkpointer(),
        ltm=ltm,
    )
    session.set_graph(agent)

    # 多模态输入
    # 时间戳由后端统一追加并进入 LLM 上下文（Agent 需感知当前时间）
    timestamped = user_message + now_timestamp()

    if image_recognition and image_refs:
        content_parts: list[dict] = [{"type": "text", "text": timestamped}]
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
                _log.warning("跳过无法加载的图片 %s: %s", img_path, e)
                continue
        inputs = {"messages": [HumanMessage(content=content_parts)]}
    else:
        inputs = {"messages": [HumanMessage(content=timestamped)]}

    turn_id = uuid.uuid4().hex

    config = {
        "configurable": {
            "thread_id": session.session_id,
            "private_mode": private_mode,
            "skip_recall": skip_recall,
            "turn_id": turn_id,
            # 供图内 check_pending 计算逐轮上下文用量（answer/done 事件）
            "system_prompt": system_prompt,
            "model_name": llm_conf.model_name,
            "max_tokens": llm_conf.max_tokens,
        },
        "callbacks": [ws_callback],
        "recursion_limit": 120,
    }

    return _TurnContext(
        system_prompt=system_prompt, agent=agent,
        inputs=inputs, config=config, turn_id=turn_id,
    )


# ── 阶段 3：执行轮次 ──────────────────────────────────────


async def _execute_agent_turn(
    ctx: _TurnContext,
    sender: TurnSender,
    session: SessionState,
    llm_conf: _LlmConfig,
) -> _TurnResult:
    """流式执行 Agent 轮次，处理取消与异常，返回结果。"""
    final_answer = ""
    error: str | None = None

    try:
        # 推送初始上下文用量（含刚加入的 user message）
        initial_usage = await estimate_context_usage_from_session(
            session, ctx.system_prompt,
            max_tokens=llm_conf.max_tokens, model_name=llm_conf.model_name,
        )
        await sender.context_usage(initial_usage)

        # 逐轮 answer/done 已由图内 check_pending 节点按序推送
        final_answer = await _stream_turn(
            ctx.agent, ctx.inputs, ctx.config, sender, session,
            ctx.system_prompt, model_name=llm_conf.model_name, max_tokens=llm_conf.max_tokens,
        )

    except asyncio.CancelledError:
        interaction.cancel_all()
        try:
            await _inject_cancel_tool_messages(session, ctx.config, sender)
        except Exception as e:
            _log.warning("checkpoint cleanup error: %s", e)
        await sender.error("CANCELLED", "生成已取消")

    except Exception as e:
        error = str(e)
        _log.error("run_agent_turn error: %s", e, exc_info=True)
        await sender.error("AGENT_ERROR", str(e))

    finally:
        # 兜底 done：若最后一轮未达 ltm_write（异常/取消中断）则补发收尾；
        # 正常完成时前端 currentTurn 已为 null，重复 done 被前端静默忽略。
        context_usage = await estimate_context_usage_from_session(
            session, ctx.system_prompt,
            max_tokens=llm_conf.max_tokens, model_name=llm_conf.model_name,
        )
        await sender.done(ctx.turn_id, context_usage)

    return _TurnResult(final_answer=final_answer, error=error)


# ── 阶段 4：后处理 ────────────────────────────────────────


async def _postprocess_turn(
    session: SessionState,
    result: _TurnResult,
) -> None:
    """后处理：Const 会话保存、Sub-agent 结果回调。

    LTM 持久化已移至图内 ``ltm_write`` 节点；
    消息计数已移至图内 ``check_pending`` 节点（逐轮计数）。
    """
    # Const 会话持久化
    if result.final_answer and session.is_const:
        try:
            raw_messages = await session.get_messages()
            metadata = {
                "created_at": session.created_at,
                "last_active": session.last_active,
                "message_count": session.message_count,
            }
            save_const_session(session.session_id, session.const_name, metadata, serialize_messages(raw_messages))
        except Exception as e:
            _log.warning("自动保存会话 %s 失败: %s", session.session_id[:8], e)

    # Sub-agent pending 结果回调
    if session.has_pending_result():
        if result.error:
            _log.info("resolving pending_result with run error (session=%s)", session.session_id[:8])
            session.fail_pending(f"子 Agent 执行失败: {result.error}")
        elif result.final_answer:
            _log.info("resolving pending_result with answer (session=%s)", session.session_id[:8])
            session.resolve_pending(result.final_answer)
        else:
            session.fail_pending("Sub-agent 未能产生有效回答")


# ═══════════════════════════════════════════════════════════
# 公共接口（最顶层：仅编排，不包含逻辑）
# ═══════════════════════════════════════════════════════════


async def run_agent_turn(
    session: SessionState,
    user_message: str,
    private_mode: bool = False,
    skip_recall: bool = False,
    provider_id: str | None = None,
    model_name: str | None = None,
    image_recognition: bool = False,
    image_refs: list[str] | None = None,
    queued_pending: list[PendingMessage] | None = None,
):
    """编排一次 Agent 图执行（单次调用）。

    排队消息的注入与下一轮编排全部在图内完成——工具间隙注入（inject_pending）
    与轮末查询点（check_pending）负责队列消费，本函数不再循环驱动。

    分 4 个阶段执行：
      1. _resolve_llm        — 解析 LLM 与上下文窗口配置
      2. _build_turn_context  — 构建 Agent 图、多模态输入与运行配置
      3. _execute_agent_turn  — 流式执行、逐轮 answer/done、异常/取消处理
      4. _postprocess_turn    — Const 保存、Sub-agent 回调

    Args:
        queued_pending: 随首轮一起被消费的排队消息列表（_start_turn_from_ws
            合并残留队列时非空），此时需先发 ``pending_consumed(new_turn)`` 让前端
            创建 currentTurn。普通发送为 ``None``。
    """
    # Sub-agent 跳过长期记忆的读（retrieve_memory）和写（ltm_write）
    if session.is_subagent:
        private_mode = True
        skip_recall = True

    ws = interaction.current_ws.get()
    app_state = ws.app.state
    sender = TurnSender.from_context()

    current_task = asyncio.current_task()
    try:
        # 1. 解析 LLM 配置
        llm_conf: _LlmConfig = _resolve_llm(
            provider_manager=get_manager(),
            default_llm=get_default_llm(),
            provider_id=provider_id,
            model_name=model_name,
        )
        if llm_conf is None:
            await sender.error(
                "NO_LLM",
                "No LLM provider configured. Add one in Model Settings first.",
            )
            return

        # 首轮若合并了排队消息（_start_turn_from_ws 传入），通知前端创建 currentTurn
        if queued_pending:
            await sender.pending_consumed(
                [{"pending_id": p.pending_id, "text": p.text} for p in queued_pending],
                mode="new_turn",
                text=user_message,
            )

        # 2. 构建执行上下文
        ctx: _TurnContext = await _build_turn_context(
            tools=app_state.tool_manager.get_all(multimodal=llm_conf.multimodal),
            session=session,
            llm_conf=llm_conf,
            user_message=user_message,
            image_recognition=image_recognition,
            image_refs=image_refs,
            ltm=app_state.ltm,
            private_mode=private_mode,
            skip_recall=skip_recall,
        )

        # 3. 执行（图内完成全部轮次）
        result: _TurnResult = await _execute_agent_turn(ctx, sender, session, llm_conf)

        # 4. 后处理（消息计数已在图内 check_pending 节点完成）
        await _postprocess_turn(
            session=session,
            result=result,
        )
    finally:
        session.clear_active_task(current_task)
