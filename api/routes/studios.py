"""工作坊 REST API — studios/ 目录枚举、schema 与 CRUD。"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent import (
    create_studio,
    delete_studio,
    get_studio,
    load_all_studios,
    studio_schema,
    update_studio,
)

router = APIRouter()


class StudioBody(BaseModel):
    """新建/更新的工作坊完整文档（YAML dict）。"""
    document: dict[str, Any]


def _as_info_dict(name: str, description: str, filename: str) -> dict:
    return {"name": name, "description": description, "filename": filename}


@router.get("/studios")
async def list_studios() -> dict:
    """扫描 studios/*.yaml，返回 [{name, description, filename}] 供选择条与管理页。"""
    return {
        "studios": [
            _as_info_dict(s.name, s.description, s.filename)
            for s in load_all_studios()
        ]
    }


# 注意：/schema 必须先于 /{name} 声明，否则 "schema" 会被捕获为 name。
@router.get("/studios/schema")
async def get_schema() -> dict:
    """返回 STUDIO_SPEC 序列化后的字段列表，供前端动态生成编辑表单。"""
    return {"fields": studio_schema()}


@router.get("/studios/{name}")
async def get_one(name: str) -> dict:
    """按 name 返回工作坊完整文档（编辑回填用）。"""
    data = get_studio(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"工作坊「{name}」不存在")
    return data


@router.post("/studios")
async def create(body: StudioBody) -> dict:
    """新建工作坊（文件名 = name 安全化）。"""
    try:
        info = create_studio(body.document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_info_dict(info.name, info.description, info.filename)


@router.put("/studios/{name}")
async def update(name: str, body: StudioBody) -> dict:
    """更新工作坊；body 内 name 变更则重命名文件。"""
    try:
        info = update_studio(name, body.document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _as_info_dict(info.name, info.description, info.filename)


@router.delete("/studios/{name}")
async def delete(name: str) -> dict:
    """删除工作坊文件。"""
    if not delete_studio(name):
        raise HTTPException(status_code=404, detail=f"工作坊「{name}」不存在")
    return {"status": "ok"}
