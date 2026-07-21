"""REST API — 长期记忆叙事。"""

import random

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/long-term")
async def get_long_term(request: Request) -> dict:
    ltm = request.app.state.ltm
    return {"long_term": ltm.get_narrative()}


@router.get("/memories")
async def get_memories(request: Request) -> dict:
    ltm = request.app.state.ltm
    return ltm._mm.get_memories_grouped()


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, request: Request) -> dict:
    """删除指定 ID 的单条记忆。"""
    ltm = request.app.state.ltm
    try:
        description = ltm.delete_memory(memory_id)
        return {"status": "deleted", "id": memory_id, "description": description}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.get("/moment")
async def get_moment(request: Request) -> dict:
    ltm = request.app.state.ltm
    items = ltm._mm.show()
    if not items:
        return {"moment": None}
    chosen = random.choice(items)
    history = ltm._mm.show_description_history(chosen["id"])
    return {
        "moment": {
            "id": chosen["id"],
            "description": chosen["description"],
            "theme": chosen["theme"],
            "history": history,
        }
    }
