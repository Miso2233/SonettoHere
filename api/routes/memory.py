"""REST API — 长期记忆叙事。"""

import random

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/long-term")
async def get_long_term(request: Request) -> dict:
    ltm = request.app.state.ltm
    return {"long_term": ltm.get_narrative()}


@router.get("/memories")
async def get_memories(request: Request) -> dict:
    ltm = request.app.state.ltm
    return ltm._mm.get_memories_grouped()


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
