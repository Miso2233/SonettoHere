"""REST API — 会话 CRUD + 撤回 + 上下文用量查询。"""

from fastapi import APIRouter, HTTPException, Request

from api.agent.context_usage import estimate_context_usage_from_session
from agent import build_system_prompt
from api.utils.messages import flatten_content
from api.session.manager import session_manager

from api.providers import FALLBACK_CTX
from api.providers.manager import get_manager
from api.utils.logger import get_logger

router = APIRouter()
_log = get_logger("sessions")


@router.post("/sessions")
async def create_session(request: Request) -> dict:
    sm = session_manager
    session = sm.create()
    return {"session_id": session.session_id, "created_at": session.created_at}


@router.get("/sessions")
async def list_sessions(request: Request) -> dict:
    sm = session_manager
    sessions = sm.list_sessions()
    _log.debug("list_sessions: 返回 %d 个会话", len(sessions))
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
        "messages": [{"role": m.type, "content": flatten_content(m.content)} for m in msgs],
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
    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}
