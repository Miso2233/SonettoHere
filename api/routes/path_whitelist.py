"""REST API — 路径白名单 (path_whitelist.yaml) CRUD。"""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

WHITELIST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "api"
    / "data"
    / "path_whitelist.yaml"
)


class WhitelistEntry(BaseModel):
    path: str
    description: str = ""


class WhitelistResponse(BaseModel):
    entries: list[WhitelistEntry]


def _load() -> list[dict]:
    if not WHITELIST_PATH.exists():
        return []
    with open(WHITELIST_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("whitelist", []) or []


def _save(entries: list[dict]) -> None:
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"whitelist": entries}, f, allow_unicode=True, default_flow_style=False)


@router.get("/path-whitelist", response_model=WhitelistResponse)
async def list_whitelist():
    entries = _load()
    return WhitelistResponse(entries=[WhitelistEntry(**e) for e in entries])


@router.post("/path-whitelist", response_model=WhitelistEntry)
async def add_whitelist(entry: WhitelistEntry):
    entries = _load()
    entries.append(entry.model_dump())
    _save(entries)
    return entry


@router.put("/path-whitelist/{index}", response_model=WhitelistEntry)
async def update_whitelist(index: int, entry: WhitelistEntry):
    entries = _load()
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail=f"索引 {index} 超出范围")
    entries[index] = entry.model_dump()
    _save(entries)
    return entry


@router.delete("/path-whitelist/{index}")
async def delete_whitelist(index: int):
    entries = _load()
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail=f"索引 {index} 超出范围")
    removed = entries.pop(index)
    _save(entries)
    return {"status": "ok", "removed": removed}
