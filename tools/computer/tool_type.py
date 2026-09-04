"""Tool: computer_type — 输入文本：把任意文本粘贴进当前聚焦的输入框。

与 computer_click 同类：执行的是真实系统动作。文本**统一经剪贴板粘贴**
（pyperclip 写入 → Ctrl/Cmd+V），支持任意文本含中文；内容按字面粘入
（`\\n`/`\\r` 不会触发独立回车），粘贴后尽力还原用户原剪贴板。输入结束后
等待 0.1s 截取**未标注**的屏幕画面注入 LLM 上下文。截图不落盘保存。
"""

import time
from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.computer import _screen as screen
from tools.get_doc import get_doc


class TypeInput(BaseModel):
    text: str = Field(
        min_length=1,
        description=(
            "要输入的文本（任意字符含中文）：统一经剪贴板粘贴，内容按字面粘入"
        ),
    )
    tool_call_id: Annotated[str, InjectedToolCallId] = ""


def _error_command(tool_call_id: str, message: str) -> Command:
    return Command(update={
        "messages": [
            ToolMessage(
                content=format_error(message),
                tool_call_id=tool_call_id,
                status="error",
            ),
        ],
    })


@get_doc
class TypeTool(ToolBase):
    name: str = "computer_type"
    description: str = (
        "输入文本：把 *text* 粘贴进当前聚焦的输入框（真实系统动作）。"
        "**统一经剪贴板粘贴**（写入剪贴板 → Ctrl/Cmd+V），支持任意文本含中文，"
        "内容按字面粘入（\\n/\\r 不会触发回车）；粘贴后尽力还原用户原剪贴板。"
        "调用前应确保目标输入框已聚焦（必要时先用 computer_click 点一下）。"
        "输入结束后等待 0.1s 截取**未标注**的输入后画面注入上下文供确认。"
        "[调用积极性: 需要在搜索框/输入框/对话框等已聚焦控件中输入文本（含中文）时"
        "使用；光标位置不定时先 computer_screenshot 观察并 computer_click 定位。]"
    )
    args_schema: type[BaseModel] = TypeInput

    async def _arun(self, text: str = "", tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, text, tool_call_id)

    def _run_impl(self, text: str = "", tool_call_id: str = "") -> Command:
        if not text:
            return _error_command(tool_call_id, "text 不能为空")

        # 统一经剪贴板粘贴输入（type_text 内完成写剪贴板→Ctrl/Cmd+V→还原）
        try:
            width, height = screen.logical_screen_size()
            screen.type_text(text)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        # 输入结束后等待 0.1s，再截取输入后的屏幕（不叠加标记、不落盘）
        time.sleep(0.1)

        try:
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(
                tool_call_id,
                f"输入已执行，但回读屏幕截图失败：{exc}",
            )

        data_url, png_bytes = screen.image_to_data_url(canvas)

        message = (
            f"已通过剪贴板粘贴把文本（{len(text)} 个字符）输入到当前输入框。"
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "type",
                            "message": message,
                            "text": text,
                            "char_count": len(text),
                            "screen_size": {"width": width, "height": height},
                            "image_bytes": len(png_bytes),
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": (
                                "已完成一次文本输入（经剪贴板粘贴），内容："
                                f"{text!r}。以下为输入后的屏幕（未标注）："
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ]),
                ],
            },
            goto="model",
        )
