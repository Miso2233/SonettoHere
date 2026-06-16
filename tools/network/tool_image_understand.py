"""Tool: analyze_image — 图片理解（GLM-5V-Turbo）。"""

import base64
import mimetypes
import urllib.parse
from pathlib import Path

import requests
from pydantic import BaseModel, Field
from zai import ZhipuAiClient

from config.settings import get_settings
from tools.base import ToolBase, format_error, format_success

MODEL = "glm-5v-turbo"


def _get_mime_type(source: str, content_type: str | None = None) -> str:
    """从 Content-Type 或文件扩展名推断 MIME 类型。"""
    if content_type and "/" in content_type:
        return content_type.split(";")[0].strip()
    ext = Path(urllib.parse.urlparse(source).path).suffix.lower()
    mime, _ = mimetypes.guess_type(f"file{ext}")
    return mime or "image/png"


def _load_image_bytes(image_source: str) -> tuple[bytes, str]:
    """解析 image_source 前缀，返回 (bytes, mime_type)。"""
    if image_source.startswith("local:"):
        path = image_source[6:]
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"路径不是文件: {path}")
        image_bytes = file_path.read_bytes()
        mime = _get_mime_type(path)
        return image_bytes, mime

    if image_source.startswith("url:"):
        url = image_source[4:]
        resp = requests.get(url, timeout=30, headers={"User-Agent": "SonettoHere/1.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type")
        mime = _get_mime_type(url, content_type)
        return resp.content, mime

    raise ValueError(f"image_source 必须以 'local:' 或 'url:' 开头: {image_source}")


class ImageUnderstandInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    image_source: str = Field(
        default="",
        description="图片来源: 'local:C:\\path\\to\\image.jpg' 或 'url:https://example.com/photo.png'",
    )
    prompt: str = Field(default="请描述这张图片", description="向模型提问的指令")


class ImageUnderstandTool(ToolBase):
    name: str = "analyze_image"
    description: str = (
        "使用智谱 GLM-5V-Turbo 多模态模型理解图片内容。"
        "支持本地文件（local:path）和网络图片（url:https://...）。"
        "可指定 prompt 提问，如 '这张图里有什么文字？'。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = ImageUnderstandInput

    def _run(
        self,
        get_doc: bool = False,
        image_source: str = "",
        prompt: str = "请描述这张图片",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not image_source.strip():
            return format_error("image_source 不能为空")

        settings = get_settings()
        client = ZhipuAiClient(api_key=settings.zhipuai_api_key)

        try:
            image_bytes, mime = _load_image_bytes(image_source)
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            data_url = f"data:{mime};base64,{image_b64}"

            response = client.chat.completions.create(
                model=MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                thinking={"type": "enabled"},
            )

            return format_success({
                "response": response.choices[0].message.content,
            })
        except Exception as e:
            return format_error(f"图片理解失败: {e}")
