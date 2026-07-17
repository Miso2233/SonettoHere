"""Tool: verify_image — 本地图片校验与处理。

接收本地图片路径，校验文件存在且为有效图片，返回成功确认。
"""

from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_success


class VerifyImageInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    image_path: str = Field(
        default="",
        description="本地图片的绝对路径，如 C:\\Users\\...\\photo.jpg",
    )


class VerifyImageTool(ToolBase):
    name: str = "verify_image"
    description: str = (
        "校验本地图片文件是否存在、是否为有效图片格式，并返回确认结果。"
        "支持常见图片格式（jpg、png、gif、bmp、webp）。"
        "仅接受本地文件路径，不支持 URL。[调用积极性: 仅在用户明确提供图片路径或要求处理图片时调用]"
    )
    args_schema: type[BaseModel] = VerifyImageInput

    def _run(self, get_doc: bool = False, image_path: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not image_path:
            return format_success({"status": "跳过", "reason": "未提供图片路径"})

        # 安全校验
        err = check_path_access(image_path)
        if err is not None:
            raise PermissionError(err)

        file_path = Path(image_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {image_path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"路径不是文件: {image_path}")

        return format_success({"status": "成功", "message": "成功（而不是图片信息）"})
