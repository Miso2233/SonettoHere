"""REST API — 长期记忆叙事。"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/narrative")
async def get_narrative(request: Request):
    ltm = request.app.state.ltm
    return {"narrative": ltm.get_narrative()}
