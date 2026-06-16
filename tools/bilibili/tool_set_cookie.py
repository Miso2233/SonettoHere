"""Tool: bilibili_set_cookie — 设置 B 站 Cookie。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookie.txt")


class SetCookieInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    cookie: str = Field(default="", description="完整的 B 站 Cookie 字符串，从浏览器开发者工具 Application > Cookies 复制")


class BilibiliSetCookieTool(ToolBase):
    name: str = "bilibili_set_cookie"
    description: str = (
        "设置/更新 B 站 Cookie 用于视频下载。"
        "Cookie 可从浏览器开发者工具 > Application > Cookies 中复制完整字符串。"
        "Cookie 约 30 天过期，过期后需重新设置。"
        "[调用积极性: 仅在用户引用或提及时调用] [get_doc: 使用前必须 get_doc]"
    )
    args_schema: type[BaseModel] = SetCookieInput

    def _run(self, get_doc: bool = False, cookie: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not cookie.strip():
            return format_error("cookie 不能为空")
        try:
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                f.write(cookie.strip())
            return format_success({"message": "Cookie 已保存"})
        except OSError as e:
            return format_error(f"写入 Cookie 文件失败: {e}")
