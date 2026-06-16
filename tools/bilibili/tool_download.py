"""Tool: bilibili_download — 下载 B 站视频。"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.bilibili.tool_set_cookie import COOKIE_FILE

logger = logging.getLogger(__name__)


class BilibiliDownloadInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    url: str = Field(default="", description="B 站视频链接，如 https://www.bilibili.com/video/BVxxx/")
    quality: Optional[str] = Field(
        default="highest",
        description="画质: highest（自动最高）/ 1080P / 720P / 480P / 360P / 4K / 8K",
    )


class BilibiliDownloadTool(ToolBase):
    name: str = "bilibili_download"
    description: str = (
        "下载 B 站 (Bilibili) 视频。支持 /video/BV* 和 /video/av* 格式。"
        "需要先用 bilibili_set_cookie 设置有效的 Cookie（约 30 天过期）。"
        "画质默认选最高可用，未登录时自动降级到 360P。"
        "[调用积极性: 仅在用户引用或提及时调用] [get_doc: 使用前必须 get_doc]"
    )
    args_schema: type[BaseModel] = BilibiliDownloadInput

    def _run(self, get_doc: bool = False, url: str = "", quality: str = "highest") -> str:
        if get_doc:
            return self._load_doc()
        if not url.strip():
            return format_error("url 不能为空")

        cookie = self._read_cookie()
        if not cookie:
            return format_error(
                "Cookie 未配置。请先使用 bilibili_set_cookie 工具设置 B 站 Cookie。"
                "Cookie 可从浏览器开发者工具 > Application > Cookies 中复制。"
            )

        from tools.bilibili.downloader import BilibiliDownloader

        project_root = Path(os.path.abspath(__file__)).parent.parent.parent
        output_dir = project_root / "output" / "bilibili"

        downloader = BilibiliDownloader(cookie=cookie, output_dir=str(output_dir))

        try:
            video = asyncio.run(downloader.run(url, quality))
            return format_success({
                "title": video.title,
                "quality": video.get_quality_name(),
                "file_path": video.output_path,
                "cover_path": video.cover_path,
            })
        except Exception as e:
            logger.exception("下载失败: %s", url)
            return format_error(f"下载失败: {e}")

    @staticmethod
    def _read_cookie() -> str:
        try:
            if os.path.exists(COOKIE_FILE):
                return Path(COOKIE_FILE).read_text(encoding="utf-8").strip()
        except OSError:
            pass
        return ""
