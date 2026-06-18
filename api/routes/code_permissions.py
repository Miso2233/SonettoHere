"""REST API — 代码执行权限 (code_permissions.yaml) CRUD。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.code_permission_store import (
    add_permission,
    list_permissions,
    remove_permission,
)

router = APIRouter()


class CodePermissionEntry(BaseModel):
    hash: str = ""
    code_preview: str = ""
    action: str
    description: str = ""


class ListPermissionsResponse(BaseModel):
    permissions: list[CodePermissionEntry]


class AddPermissionRequest(BaseModel):
    code: str
    action: str
    description: str = ""


@router.get("/code-permissions", response_model=ListPermissionsResponse)
async def get_permissions():
    return ListPermissionsResponse(
        permissions=[CodePermissionEntry(**e) for e in list_permissions()]
    )


@router.post("/code-permissions", response_model=CodePermissionEntry)
async def create_permission(req: AddPermissionRequest):
    if req.action not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="action 必须是 allow 或 deny")
    entry = add_permission(req.code, req.action, req.description)
    return CodePermissionEntry(**entry)


@router.delete("/code-permissions/{index}")
async def delete_permission(index: int):
    if not remove_permission(index):
        raise HTTPException(status_code=404, detail=f"索引 {index} 超出范围")
    return {"status": "ok"}
