"""Tool: computer_key — 击键：对当前聚焦窗口执行一次真实按键/快捷键。

输入形如 "Return"、"ctrl+s"、"alt+Tab"，解析后触发真实键盘事件。与
computer_click / computer_type 同类，属真实系统动作；结束后等待 0.1s 截取
**未标注**屏幕画面注入 LLM 上下文。截图不落盘保存。
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


class KeyInput(BaseModel):
    keys: str = Field(
        min_length=1,
        description=(
            "要按下的键/快捷键：单个键名如 Return、Esc、F5、Space，或用 + 连接的"
            "组合如 ctrl+s、alt+Tab、ctrl+shift+esc"
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
class KeyTool(ToolBase):
    name: str = "computer_key"
    description: str = (
        "击键：对当前聚焦窗口执行一次**真实按键/快捷键**（触发真实键盘事件）。"
        "输入单个键名（如 Return、Esc、F5、Space、Tab、箭头键）或 + 连接的组合"
        "（如 ctrl+s 保存、alt+Tab 切换窗口、ctrl+shift+esc 打开任务管理器、"
        "ctrl+c / ctrl+v / ctrl+a / ctrl+z 等）。执行结束后等待 0.1s 截取"
        "**未标注**画面注入上下文供确认。需要输入一段文本用 computer_type，需要"
        "逐点点击用 computer_click。"
        "[调用积极性: 需要触发回车/取消/保存/复制粘贴/切换窗口等单个键或快捷键时"
        "使用；光标位置或焦点不定时先 computer_screenshot 观察定位。]"
    )
    args_schema: type[BaseModel] = KeyInput

    async def _arun(self, keys: str = "", tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, keys, tool_call_id)

    def _run_impl(self, keys: str = "", tool_call_id: str = "") -> Command:
        if not keys or not keys.strip():
            return _error_command(tool_call_id, "keys 不能为空")

        try:
            width, height = screen.logical_screen_size()
            screen.press_keys(keys)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        # 按键结束后等待 0.1s，再截取屏幕（不叠加标记、不落盘）
        time.sleep(0.1)

        try:
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(
                tool_call_id,
                f"按键已执行，但回读屏幕截图失败：{exc}",
            )

        data_url, png_bytes = screen.image_to_data_url(canvas)

        message = f"已按下按键/快捷键 {keys!r}。"

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "key",
                            "message": message,
                            "keys": keys,
                            "screen_size": {"width": width, "height": height},
                            "image_bytes": len(png_bytes),
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": (
                                f"已完成一次击键：{keys!r}。"
                                "以下为执行后的屏幕（未标注）："
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
