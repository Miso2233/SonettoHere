"""Tool: computer_type — 键盘输入：把字符串逐字符真实敲入当前聚焦的输入框。

与 computer_click 同类：执行的是真实系统动作（触发真实键盘事件）。仅支持
ASCII 可打印字符；输入结束后等待 0.1s 截取**未标注**的屏幕画面，注入 LLM
上下文并落盘到工程内 git 不跟踪的临时目录。
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
            "要输入的字符串（ASCII 可打印字符与空格；换行按回车、Tab 按制表键）。"
            "中文等非 ASCII 字符不支持，请改用其它输入方式"
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
        "键盘输入：把 *text* 逐字符真实敲入当前聚焦的输入框（触发真实键盘事件）。"
        "调用前应确保目标输入框已处于聚焦状态（必要时先用 computer_click 点一下）。"
        "仅支持 ASCII 可打印字符与空格；换行/回车（\\n、\\r）会触发 Enter、\\t 触发 Tab，"
        "中文字符不支持，需改用剪贴板粘贴等其它方式。输入结束后等待 0.1s 截取"
        "**未标注**的输入后画面注入上下文供确认，同时把该截图保存到工程 "
        ".computer_use/ 目录（返回 saved_file）。"
        "[调用积极性: 需要在搜索框/输入框/对话框等已聚焦控件中输入文本时使用；"
        "光标位置不定时先 computer_screenshot 观察并 computer_click 定位。]"
    )
    args_schema: type[BaseModel] = TypeInput

    async def _arun(self, text: str = "", tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, text, tool_call_id)

    def _run_impl(self, text: str = "", tool_call_id: str = "") -> Command:
        if not text:
            return _error_command(tool_call_id, "text 不能为空")

        # 真实键盘逐字符输入（ASCII 之外字符在 type_text 内报错）
        try:
            width, height = screen.logical_screen_size()
            screen.type_text(text)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        # 输入结束后等待 0.1s，再截取输入后的屏幕（不叠加标记）
        time.sleep(0.1)

        try:
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(
                tool_call_id,
                f"输入已执行，但回读屏幕截图失败：{exc}",
            )

        data_url, png_bytes = screen.image_to_data_url(canvas)

        message = f"已向当前输入框逐字符输入文本（{len(text)} 个字符）。"
        saved_file = ""
        try:
            filename = screen.new_filename("computer_type")
            saved_file = str(screen.save_tmp_image(canvas, filename))
        except OSError as exc:
            message += f" 截图保存失败：{exc}"

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
                            "saved_file": saved_file,
                            "image_bytes": len(png_bytes),
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": (
                                "已完成一次键盘输入，内容："
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
