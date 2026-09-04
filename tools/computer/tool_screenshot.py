"""Tool: computer_screenshot — 截取当前屏幕并注入 LLM 上下文。

仅在启用识图（模型具备多模态视觉）时交付给 LLM。与 read_image 同一条
Command(goto="model") 注入通道，区别仅是图片来源为实时截屏而非本地文件。
"""

from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.computer import _screen as screen
from tools.get_doc import get_doc


class ScreenshotInput(BaseModel):
    tool_call_id: Annotated[str, InjectedToolCallId] = ""


@get_doc
class ScreenshotTool(ToolBase):
    name: str = "computer_screenshot"
    description: str = (
        "截取当前屏幕（主显示器全屏）为图片并注入上下文，使你能直接“看到”真实桌面"
        "画面（窗口 / 按钮 / 输入框 / 图标位置），用于电脑图形界面操作的视觉定位。"
        "截图按 1920x1080 逻辑画布呈现：坐标原点在左上角 (0,0)，横坐标 0..1920，"
        "纵坐标 0..1080。如需操作鼠标，请基于本截图输出画布整数坐标并调用 "
        "computer_click；每次点击后 computer_click 会回传带标记的新画面，"
        "无需重复截图，除非界面没有随之更新。"
        "[调用积极性: 用户要求操作电脑屏幕/GUI（看画面、找按钮、点图标）或需要确认桌面"
        "状态时，先调用本工具截屏。]"
    )
    args_schema: type[BaseModel] = ScreenshotInput

    async def _arun(self, tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, tool_call_id)

    def _run_impl(self, tool_call_id: str = "") -> Command:
        try:
            img = screen.capture_screen()
            width, height = screen.logical_screen_size()
        except screen.ScreenError as exc:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(str(exc)),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        canvas = screen.to_canvas_image(img)
        data_url, png_bytes = screen.image_to_data_url(canvas)

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "screenshot",
                            "screen_size": {"width": width, "height": height},
                            "canvas_size": {
                                "width": screen.CANVAS_WIDTH,
                                "height": screen.CANVAS_HEIGHT,
                            },
                            "image_bytes": len(png_bytes),
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": (
                                "当前屏幕截图已注入（1920x1080 逻辑画布，"
                                "坐标原点在左上角，据此输出点击坐标）："
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