"""Tool: computer_virtual_click — 虚拟点击：在指定画布坐标标注一次「拟点击」。

与 computer_click（真实点击）是**两个不同工具**。本工具（computer_virtual_click）
**不会**移动真实鼠标、**不会**触发任何系统点击：它截取当前屏幕，在传入的
画布坐标处画上红色标记，把带标注画面注入 LLM 上下文并落盘到工程内 git 不跟踪
的临时目录，用于无副作用地模拟/核对一次点击落点。
"""

from typing import Annotated

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.computer import _screen as screen
from tools.get_doc import get_doc


class VirtualClickInput(BaseModel):
    x: int = Field(
        ge=0,
        le=screen.CANVAS_WIDTH,
        description=(
            f"拟点击的 X 坐标（整数，0..{screen.CANVAS_WIDTH}，"
            "基于最近一张截图画布推算）"
        ),
    )
    y: int = Field(
        ge=0,
        le=screen.CANVAS_HEIGHT,
        description=(
            f"拟点击的 Y 坐标（整数，0..{screen.CANVAS_HEIGHT}，"
            "基于最近一张截图画布推算）"
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
class VirtualClickTool(ToolBase):
    name: str = "computer_virtual_click"
    description: str = (
        "虚拟点击：在最近一张截图对应的画布坐标上标注一次「拟点击」，只做标记、"
        "**不执行任何真实鼠标操作**（不移动光标、不触发系统点击）。"
        "坐标必须是基于 1920x1080 逻辑画布输出的整数（x: 0..1920，y: 0..1080，"
        "原点在画布左上角）；后端会算出该点对应的真实屏幕像素一并回显。"
        "执行后截取当前屏幕，在标注处画上红色标记，把画面注入上下文供确认，"
        "同时把带标记截图保存到工程 .computer_use/ 目录（返回 saved_file）。"
        "它用于无副作用地模拟/核对一次点击落点；真正执行系统点击用 computer_click，"
        "本工具不负责。"
        "[调用积极性: 需要先确认某坐标是否命中目标控件、或在画面上标记一个目标点，"
        "避免误触发真实操作时使用。]"
    )
    args_schema: type[BaseModel] = VirtualClickInput

    async def _arun(self, x: int = 0, y: int = 0, tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, x, y, tool_call_id)

    def _run_impl(self, x: int = 0, y: int = 0, tool_call_id: str = "") -> Command:
        if not (0 <= x <= screen.CANVAS_WIDTH and 0 <= y <= screen.CANVAS_HEIGHT):
            return _error_command(
                tool_call_id,
                f"坐标越界：x/y 必须在 0..{screen.CANVAS_WIDTH} / 0..{screen.CANVAS_HEIGHT} 之间",
            )

        # 仅截屏 + 标注，全程不触碰真实鼠标 / 系统点击
        try:
            width, height = screen.logical_screen_size()
            native_x, native_y = screen.canvas_to_screen(x, y, width, height)
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        screen.draw_click_marker(canvas, x, y)
        data_url, png_bytes = screen.image_to_data_url(canvas)

        message = (
            f"已记录一次虚拟点击：画布坐标 ({x}, {y})"
            f"（对应真实像素 {native_x}, {native_y}）。未执行任何真实鼠标操作。"
        )
        saved_file = ""
        try:
            filename = screen.new_filename("computer_virtual_click")
            saved_file = str(screen.save_tmp_image(canvas, filename))
        except OSError as exc:
            message += f" 标注截图保存失败：{exc}"

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "virtual_click",
                            "message": message,
                            "click_canvas": {"x": x, "y": y},
                            "click_screen": {"x": native_x, "y": native_y},
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
                                f"完成一次虚拟点击标注（画布坐标 {x}, {y}）。"
                                "红圈即拟点击位置；本次未执行真实鼠标操作："
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
