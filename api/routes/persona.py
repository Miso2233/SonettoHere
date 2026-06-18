"""REST API — 人设文件 (SOUL.md / USER.md) 读写。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

PERSONAS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "personas"

VALID_TYPES = {"soul": "SOUL.md", "user": "USER.md"}


class PersonaResponse(BaseModel):
    content: str
    type: str


class PersonaUpdateRequest(BaseModel):
    content: str


@router.get("/persona", response_model=PersonaResponse)
async def get_persona(type: str = Query(..., description="soul 或 user")):
    t = type.lower()
    if t not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"无效 type: {type}，仅支持 soul/user")
    path = PERSONAS_DIR / VALID_TYPES[t]
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return PersonaResponse(content=content, type=t)


@router.put("/persona", response_model=PersonaResponse)
async def update_persona(
    type: str = Query(..., description="soul 或 user"),
    body: PersonaUpdateRequest = None,
):
    t = type.lower()
    if t not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"无效 type: {type}，仅支持 soul/user")
    path = PERSONAS_DIR / VALID_TYPES[t]
    path.write_text(body.content, encoding="utf-8")
    return PersonaResponse(content=body.content, type=t)
