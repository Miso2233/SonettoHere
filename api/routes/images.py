"""REST API — 提供本地图片文件访问（供前端渲染缩略图）。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from tools.base import check_path_access

router = APIRouter()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


@router.get("/images/serve")
async def serve_image(path: str = Query(...)):
    """根据绝对路径返回图片文件。

    仅允许常见的图片扩展名，防止任意文件读取。
    前端通过 fetch + 认证头调用，转换为 blob URL 用于 <img> 渲染。
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="路径不是文件")
    ext = file_path.suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    # 安全校验：SonettoBlocker + 路径白名单
    blocker_err = check_path_access(str(file_path))
    if blocker_err is not None:
        raise HTTPException(status_code=403, detail="路径被安全策略阻断")

    return FileResponse(path=str(file_path))
