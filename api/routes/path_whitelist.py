"""REST API — 路径白名单 (path_whitelist.yaml) CRUD。"""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# 导入安全检查函数
from tools.base import check_path_whitelisted, check_sonetto_blocker

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


# ── 路径安全检查（供前端气泡标红使用） ──


@router.get("/check-path-blocked")
async def check_path_blocked(path: str = Query(..., description="要检查的路径")):
    """检查路径是否被拒止锚或白名单阻挡。

    返回:
        - ``blocked``: 是否被阻挡
        - ``reason``: 阻挡原因（仅 blocked=True 时有值）
        - ``blocker_path``: 拒止锚所在目录（仅拒止锚阻挡时有值）
    """
    # 1. 拒止锚检查
    blocker = check_sonetto_blocker(path)
    if blocker is not None:
        return {
            "blocked": True,
            "reason": f"被拒止锚阻挡：目录「{blocker}」含有 SonettoBlocker 标记",
            "blocker_path": blocker,
        }

    # 2. 白名单检查
    whitelist_result = check_path_whitelisted(path)
    if whitelist_result is not None:
        return {
            "blocked": True,
            "reason": whitelist_result,
            "blocker_path": None,
        }

    return {
        "blocked": False,
        "reason": None,
        "blocker_path": None,
    }
