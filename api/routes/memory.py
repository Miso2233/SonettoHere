"""REST API — 长期记忆叙事。"""

import random

from fastapi import APIRouter, Request

from memory.memory_manager import MemoryManager

router = APIRouter()


@router.get("/narrative")
async def get_narrative(request: Request):
    ltm = request.app.state.ltm
    return {"narrative": ltm.get_narrative()}


@router.get("/memories")
async def get_memories(request: Request):
    ltm = request.app.state.ltm
    mm = MemoryManager(yaml_file=str(ltm._memory_path))
    return mm.get_memories_grouped()


@router.get("/moment")
async def get_moment(request: Request):
    ltm = request.app.state.ltm
    mm = MemoryManager(yaml_file=str(ltm._memory_path))
    items = mm.show()
    if not items:
        return {"moment": None}
    chosen = random.choice(items)
    history = mm.show_description_history(chosen["id"])
    return {
        "moment": {
            "id": chosen["id"],
            "description": chosen["description"],
            "theme": chosen["theme"],
            "history": history,
        }
    }
