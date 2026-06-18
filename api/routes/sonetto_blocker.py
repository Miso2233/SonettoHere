"""REST API — SonettoBlocker（拒止锚）管理。

在目标目录中创建/删除 SonettoBlocker 标记文件，
并持久化跟踪列表到 sonetto_blocker.yaml。"""

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "api"
    / "data"
    / "sonetto_blocker.yaml"
)

BLOCKER_FILENAME = "SonettoBlocker"


class BlockerEntry(BaseModel):
    path: str
    description: str = ""


class BlockerResponse(BaseModel):
    entries: list[BlockerEntry]


def _load() -> list[dict]:
    if not YAML_PATH.exists():
        return []
    with open(YAML_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("blockers", []) or []


def _save(entries: list[dict]) -> None:
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"blockers": entries}, f, allow_unicode=True, default_flow_style=False)


def _create_marker(dir_path: str) -> None:
    """在目标目录中创建 SonettoBlocker 标记文件。"""
    marker = Path(dir_path) / BLOCKER_FILENAME
    if not marker.exists():
        marker.write_text("", encoding="utf-8")


def _remove_marker(dir_path: str) -> None:
    """移除目标目录中的 SonettoBlocker 标记文件（忽略扩展名）。"""
    target = Path(dir_path)
    if not target.is_dir():
        return
    for item in target.iterdir():
        name, _ = os.path.splitext(item.name)
        if name.lower() == BLOCKER_FILENAME.lower():
            item.unlink()
            return


@router.get("/sonetto-blocker", response_model=BlockerResponse)
async def list_blockers():
    entries = _load()
    return BlockerResponse(entries=[BlockerEntry(**e) for e in entries])


@router.post("/sonetto-blocker", response_model=BlockerEntry, status_code=201)
async def add_blocker(entry: BlockerEntry):
    if not entry.path or not Path(entry.path).is_dir():
        raise HTTPException(status_code=400, detail="无效目录路径")
    _create_marker(entry.path)
    entries = _load()
    entries.append(entry.model_dump())
    _save(entries)
    return entry


@router.delete("/sonetto-blocker/{index}")
async def delete_blocker(index: int):
    entries = _load()
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail=f"索引 {index} 超出范围")
    removed = entries.pop(index)
    _remove_marker(removed["path"])
    _save(entries)
    return {"status": "ok", "removed": removed}
