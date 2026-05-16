"""REST API — 本地文件服务（封面图等）。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/file")
async def serve_file(path: str):
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    file_path = file_path.resolve()

    # 防止目录遍历攻击：仅允许访问项目目录内的文件
    if not str(file_path).startswith(str(PROJECT_ROOT.resolve())):
        raise HTTPException(status_code=403, detail="文件路径不在项目目录内")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="不是文件")

    return FileResponse(str(file_path))
