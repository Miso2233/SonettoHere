"""REST API — 会话 CRUD。"""

from fastapi import APIRouter, HTTPException, Request

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
        "message_count": len(session.message_history),
        "created_at": session.created_at,
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": session.short_term_memory.to_dict_list()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    sm = request.app.state.session_manager
    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}
