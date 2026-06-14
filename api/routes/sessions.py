"""REST API — 会话 CRUD + Const 固定会话。"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.context_usage import estimate_context_usage
from config.settings import get_settings

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
        "has_active_agent": session._active_task is not None and not session._active_task.done(),
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
        msgs = cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
    except Exception:
        msgs = []
    return {"session_id": session_id, "messages": [{"role": m.type, "content": m.content} for m in msgs]}


@router.post("/sessions/{session_id}/undo")
async def undo_session_messages(session_id: str, request: Request, n: int = 1):
    """撤回最近 n 轮对话（默认撤回最后一轮）。"""
    from api.time_traveler import undo_rounds

    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session._graph is None:
        raise HTTPException(status_code=400, detail="No agent graph available for this session")

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
    settings = get_settings()
    system_prompt = request.app.state.system_prompt
    try:
        cpt = await session.checkpointer.aget_tuple(
            {"configurable": {"thread_id": session.session_id}}
        )
        counting_messages = cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
    except Exception:
        counting_messages = []
    usage = estimate_context_usage(
        messages=counting_messages,
        system_prompt=system_prompt,
        max_tokens=settings.model_context_window,
        model_name=settings.model_name,
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
        raw_messages = cpt.checkpoint.get("channel_values", {}).get("messages", []) if cpt else []
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
