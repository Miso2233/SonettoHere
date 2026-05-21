"""REST API — 会话 CRUD。"""

from fastapi import APIRouter, HTTPException, Request

from api.context_usage import estimate_context_usage
from config.settings import get_settings

router = APIRouter()


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
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        state = await session.checkpointer.aget_state(
            {"configurable": {"thread_id": session.session_id}}
        )
        msgs = state.values.get("messages", [])
    except Exception:
        msgs = []
    return {"session_id": session_id, "messages": [{"role": m.type, "content": m.content} for m in msgs]}


@router.get("/sessions/{session_id}/context-usage")
async def get_context_usage(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    settings = get_settings()
    system_prompt = request.app.state.system_prompt
    try:
        state = await session.checkpointer.aget_state(
            {"configurable": {"thread_id": session.session_id}}
        )
        counting_messages = state.values.get("messages", [])
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
    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}
