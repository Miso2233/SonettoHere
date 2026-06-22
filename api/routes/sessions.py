"""REST API — 会话 CRUD + Const 固定会话。"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.context_usage import estimate_context_usage
from agent.prompts import get_system_prompt_parts

router = APIRouter()


class ConstifyRequest(BaseModel):
    name: str


@router.post("/sessions")
async def create_session(request: Request):
    sm = request.app.state.session_manager
    session = sm.create()
    return {"session_id": session.session_id, "created_at": session.created_at}


@router.get("/sessions")
async def list_sessions(request: Request):
    sm = request.app.state.session_manager
    return {"sessions": sm.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "message_count": session.message_count,
        "created_at": session.created_at,
        "has_active_agent": session._active_task is not None
        and not session._active_task.done(),
        "is_const": session.is_const,
        "const_name": session.const_name,
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        msgs = (
            cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
        )
    except Exception:
        msgs = []
    return {
        "session_id": session_id,
        "messages": [{"role": m.type, "content": m.content} for m in msgs],
    }


@router.post("/sessions/{session_id}/undo")
async def undo_session_messages(session_id: str, request: Request, n: int = 1):
    """撤回最近 n 轮对话（默认撤回最后一轮）。"""
    from api.time_traveler import undo_rounds

    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session._graph is None:
        raise HTTPException(
            status_code=400, detail="No agent graph available for this session"
        )

    config = {"configurable": {"thread_id": session_id}}
    deleted = await undo_rounds(session._graph, config, n=n)
    session.message_count = max(0, session.message_count - deleted)
    return {"deleted_count": deleted}


@router.get("/sessions/{session_id}/context-usage")
async def get_context_usage(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    mgr = getattr(request.app.state, "provider_manager", None)
    max_tokens = 256_000
    model_name = ""
    if mgr is not None and mgr.count > 0:
        for provider in mgr.iter_enabled():
            max_tokens = provider.config.context_window
            model_name = provider.default_model
            break

    system_prompt = request.app.state.system_prompt
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        counting_messages = (
            cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
        )
    except Exception:
        counting_messages = []
    usage = estimate_context_usage(
        messages=counting_messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model_name=model_name,
        system_prompt_parts=get_system_prompt_parts(),
    )
    usage["session_id"] = session_id
    return usage


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)

    # 若为 const 会话，先清理磁盘文件
    if session is not None and session.is_const:
        from api.const_session_store import delete_const_session

        delete_const_session(session_id)

    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


# ── Const 固定会话 ────────────────────────────────────────────


@router.post("/sessions/{session_id}/const")
async def constify_session(session_id: str, body: ConstifyRequest, request: Request):
    """将当前会话固定为 const 持久化保存。"""
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Agent 运行中禁止固定
    if session._active_task is not None and not session._active_task.done():
        raise HTTPException(status_code=409, detail="Agent 仍在运行中，无法固定会话")

    # 从 checkpointer 提取消息
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        raw_messages = (
            cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
        )
    except Exception:
        raw_messages = []

    from api.const_session_store import save_const_session, serialize_messages

    metadata = {
        "created_at": session.created_at,
        "last_active": session.last_active,
        "message_count": session.message_count,
    }
    serialized = serialize_messages(raw_messages)
    save_const_session(session.session_id, body.name, metadata, serialized)

    # 标记为 const
    session.is_const = True
    session.const_name = body.name

    return {
        "session_id": session.session_id,
        "is_const": True,
        "const_name": body.name,
    }


@router.post("/sessions/{session_id}/generate-title")
async def generate_session_title(session_id: str, request: Request):
    """根据会话内容使用 LLM 生成简洁标题。"""
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # 从 checkpointer 提取消息
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        messages = (
            cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
        )
    except Exception:
        messages = []

    if not messages:
        raise HTTPException(status_code=400, detail="没有消息可供生成标题")

    # 构建对话文本（仅 human/ai，截断长内容）
    conversation_lines = []
    for m in messages:
        role = "user" if m.type == "human" else "assistant"
        content = (m.content[:600] if hasattr(m, "content") else str(m))[:600]
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
        llm = request.app.state.llm
        response = await llm.ainvoke(prompt)
        title = (
            response.content.strip().strip('"').strip("'")
            if hasattr(response, "content")
            else str(response).strip()
        )
        title = title[:50]
        if not title:
            title = "未命名会话"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标题生成失败: {e}")

    return {"title": title}


@router.delete("/sessions/{session_id}/const")
async def unconstify_session(session_id: str, request: Request):
    """取消固定，删除磁盘文件。"""
    from api.const_session_store import delete_const_session

    delete_const_session(session_id)

    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is not None:
        session.is_const = False
        session.const_name = ""

    return {"status": "ok"}
