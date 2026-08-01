"""REST API — 会话 CRUD + Const 固定会话。"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.agent.context_usage import estimate_context_usage_from_session
from agent import build_system_prompt
from api.session.const_store import flatten_content
from api.session.manager import session_manager
from langchain_core.language_models.chat_models import BaseChatModel

from api.providers import FALLBACK_CTX
from api.providers.manager import get_manager
from api.utils.logger import get_logger

router = APIRouter()
_log = get_logger("sessions")


class ConstifyRequest(BaseModel):
    name: str


@router.post("/sessions")
async def create_session(request: Request) -> dict:
    sm = session_manager
    session = sm.create()
    return {"session_id": session.session_id, "created_at": session.created_at}


@router.get("/sessions")
async def list_sessions(request: Request) -> dict:
    sm = session_manager
    sessions = sm.list_sessions()
    const_count = sum(1 for s in sessions if s.get("is_const"))
    _log.debug("list_sessions: 返回 %d 个会话, 其中固定会话 %d 个", len(sessions), const_count)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    sm = session_manager
    session = sm.get(session_id)
    _log.debug("get_session: id=%s, found=%s", session_id, session is not None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "message_count": session.message_count,
        "created_at": session.created_at,
        "has_active_agent": session.has_active_task(),
        "is_const": session.is_const,
        "const_name": session.const_name,
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request) -> dict:
    sm = session_manager
    session = sm.get(session_id)
    if session is None:
        _log.info("get_messages: 会话不存在, session_id=%s", session_id)
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        msgs = await session.get_messages()
        _log.debug("get_messages: session_id=%s, 获取到 %d 条消息", session_id, len(msgs))
    except Exception as e:
        _log.warning("get_messages: 获取消息失败, session_id=%s, error=%s", session_id, e)
        msgs = []
    return {
        "session_id": session_id,
        "messages": [{"role": m.type, "content": m.content} for m in msgs],
    }


@router.post("/sessions/{session_id}/undo")
async def undo_session_messages(session_id: str, request: Request, n: int = 1) -> dict:
    """撤回最近 n 轮对话（默认撤回最后一轮）。"""
    from api.agent.time_traveler import undo_rounds

    sm = session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get_graph() is None:
        raise HTTPException(
            status_code=400, detail="No agent graph available for this session"
        )

    config = {"configurable": {"thread_id": session_id}}
    deleted = await undo_rounds(session.get_graph(), config, n=n)
    session.reduce_messages(deleted)
    return {"deleted_count": deleted}


@router.get("/sessions/{session_id}/context-usage")
async def get_context_usage(session_id: str, request: Request) -> dict:
    sm = session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    mgr = get_manager()
    max_tokens, model_name = mgr.get_default_context() if mgr else (FALLBACK_CTX, "")

    usage = await estimate_context_usage_from_session(
        session,
        build_system_prompt(),
        max_tokens=max_tokens,
        model_name=model_name,
    )
    usage["session_id"] = session_id
    return usage


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request) -> dict:
    sm = session_manager
    session = sm.get(session_id)

    # 若为 const 会话，先清理磁盘文件
    if session is not None and session.is_const:
        from api.session.const_store import delete_const_session

        delete_const_session(session_id)

    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


# ── Const 固定会话 ────────────────────────────────────────────


@router.post("/sessions/{session_id}/const")
async def constify_session(session_id: str, body: ConstifyRequest, request: Request) -> dict:
    """将当前会话固定为 const 持久化保存。"""
    sm = session_manager
    session = sm.get(session_id)
    _log.debug("constify: session_id=%s, name=%r, found=%s", session_id, body.name, session is not None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Agent 运行中禁止固定
    if session.has_active_task():
        _log.warning("constify: 拒绝 — Agent 仍在运行中, session_id=%s", session_id)
        raise HTTPException(status_code=409, detail="Agent 仍在运行中，无法固定会话")

    # 从短期记忆提取消息
    try:
        raw_messages = await session.get_messages()
        _log.debug("constify: 获取到 %d 条消息", len(raw_messages))
    except Exception as e:
        _log.warning("constify: 获取消息失败: %s", e)
        raw_messages = []

    from api.session.const_store import save_const_session, serialize_messages

    metadata = {
        "created_at": session.created_at,
        "last_active": session.last_active,
        "message_count": session.message_count,
    }
    serialized = serialize_messages(raw_messages)
    saved_path = save_const_session(session.session_id, body.name, metadata, serialized)
    _log.info("constify: YAML 已保存到 %s", saved_path)

    # 标记为 const
    session.constify(body.name)
    _log.info("constify: 完成, session_id=%s, const_name=%r", session_id, body.name)

    return {
        "session_id": session.session_id,
        "is_const": True,
        "const_name": body.name,
    }


@router.post("/sessions/{session_id}/generate-title")
async def generate_session_title(session_id: str, request: Request) -> dict:
    """根据会话内容使用 LLM 生成简洁标题。"""
    sm = session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # 从短期记忆提取消息
    try:
        messages = await session.get_messages()
    except Exception:
        messages = []

    if not messages:
        raise HTTPException(status_code=400, detail="没有消息可供生成标题")

    # 构建对话文本（仅 human/ai，截断长内容）
    conversation_lines = []
    for m in messages:
        role = "user" if m.type == "human" else "assistant"
        content = flatten_content(getattr(m, "content", None))[:600]
        conversation_lines.append(f"[{role}]\n{content}")
    conversation_text = "\n\n".join(conversation_lines)

    system_prompt = """你是一个对话标题生成器。根据用户和助理的对话内容，生成一个简短的标题。

## 规则（必须严格遵守）

1. **忠实概括**：标题必须基于对话的实际内容，不能捏造或偏离用户真实提出的问题或主题。这是最根本的原则。
2. **核心主题**：准确抓住整个对话中最主要、最核心的主题或意图。如果用户问了多个问题，优先选择覆盖最广或最重要的那个。
3. **简洁凝练**：标题通常很短，一般为5-10个字，力求用最少的词概括最多信息。剔除冗余词语，保留关键词。
4. **区分度**：生成的标题应能明显区别于用户历史对话中的其他标题，便于快速定位和识别不同对话。
5. **通用可读**：不使用具体的"您"、"我"等指代词，也不包含"对话关于…"这样的描述性前缀。标题本身是名词性短语，直接陈述主题（如"Python爬虫入门"）。
6. **中性客观**：不添加情感色彩或主观评价（如不写成"令人困惑的数学问题"），也不使用指令式语气（如"请总结这个对话"）。

## 输出格式

只输出标题本身，不要有任何额外文字、引号或标点符号。"""

    prompt = f"{system_prompt}\n\n对话内容：\n{conversation_text}\n\n标题："

    try:
        # 通过 provider_manager 动态获取 LLM（支持 Web UI 添加后的热更新）
        mgr = get_manager()
        llm: BaseChatModel | None = (
            mgr.get_default_llm()
            if mgr is not None and mgr.count > 0
            else None
        )

        if llm is None:
            raise HTTPException(
                status_code=503,
                detail="没有可用的 LLM 提供商。请在模型设置中添加并启用一个提供商。",
            )

        response = await llm.ainvoke(prompt)
        title = (
            response.content.strip().strip('"').strip("'")
            if hasattr(response, "content")
            else str(response).strip()
        )
        title = title[:50]
        if not title:
            title = "未命名会话"
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标题生成失败: {e}")

    return {"title": title}


@router.delete("/sessions/{session_id}/const")
async def unconstify_session(session_id: str, request: Request) -> dict:
    """取消固定，删除磁盘文件。"""
    from api.session.const_store import delete_const_session

    deleted = delete_const_session(session_id)
    _log.info("unconstify: session_id=%s, 文件已删除=%s", session_id, deleted)

    sm = session_manager
    session = sm.get(session_id)
    if session is not None:
        session.unconstify()
        _log.info("unconstify: 会话标记已清除, session_id=%s", session_id)
    else:
        _log.debug("unconstify: 会话不在内存中, session_id=%s", session_id)

    return {"status": "ok"}
