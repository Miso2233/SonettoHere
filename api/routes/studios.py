"""工作坊 REST API — 枚举 studios/ 下的工作室。"""

from fastapi import APIRouter

from agent import load_all_studios

router = APIRouter()


@router.get("/studios")
async def list_studios() -> dict:
    """扫描 studios/*.yaml，返回 [{name, description}] 供前端工作坊选择条。"""
    return {
        "studios": [
            {"name": s.name, "description": s.description}
            for s in load_all_studios()
        ]
    }
