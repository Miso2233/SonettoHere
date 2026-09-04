"""Tool: computer_real_click — 真实点击：对系统执行一次物理左键点击。

与 computer_click（虚拟点击，仅标注不做操作）是**两个不同工具**。本工具会真实
移动系统光标并在指定坐标按下左键，随后截取点击后的屏幕，在点击处画红色标记，
把带标注画面注入 LLM 上下文并落盘到工程内 git 不跟踪的临时目录 ——
返回值结构（字段集合）与虚拟点击完全一致，仅 action 取值不同。
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


class RealClickInput(BaseModel):
    x: int = Field(
        ge=0,
        le=screen.CANVAS_WIDTH,
        description=(
            f"点击目标的 X 坐标（整数，0..{screen.CANVAS_WIDTH}，"
            "基于最近一张截图画布推算）"
        ),
    )
    y: int = Field(
        ge=0,
        le=screen.CANVAS_HEIGHT,
        description=(
            f"点击目标的 Y 坐标（整数，0..{screen.CANVAS_HEIGHT}，"
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
class RealClickTool(ToolBase):
    name: str = "computer_real_click"
    description: str = (
        "真实点击：在最近一张截图对应的位置，对真实系统执行一次**物理左键点击**"
        "（会真实移动鼠标光标并按下左键，触发应用的真实行为）。"
        "坐标必须是基于 1920x1080 逻辑画布输出的整数（x: 0..1920，y: 0..1080，"
        "原点在画布左上角），后端会线性映射回真实像素并执行。点击后本工具重新截屏，"
        "在点击处叠加红色标记并把点击后的画面注入上下文供确认，同时把带标记截图保存到"
        "工程 .computer_use/ 目录（返回 saved_file）。返回值结构与 computer_click"
        "（虚拟点击，仅标注不做操作）完全一致，仅 action 不同。"
        "如需先无副作用地核对落点是否命中，应先用 computer_click 标注试算。"
        "[调用积极性: 用户明确要求/确认后需要在系统里真实按下某个按钮、图标、菜单项时"
        "才使用；坐标不确定时先用 computer_screenshot / computer_click 确认。]"
    )
    args_schema: type[BaseModel] = RealClickInput

    async def _arun(self, x: int = 0, y: int = 0, tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, x, y, tool_call_id)

    def _run_impl(self, x: int = 0, y: int = 0, tool_call_id: str = "") -> Command:
        if not (0 <= x <= screen.CANVAS_WIDTH and 0 <= y <= screen.CANVAS_HEIGHT):
            return _error_command(
                tool_call_id,
                f"坐标越界：x/y 必须在 0..{screen.CANVAS_WIDTH} / 0..{screen.CANVAS_HEIGHT} 之间",
            )

        try:
            width, height = screen.logical_screen_size()
            native_x, native_y = screen.canvas_to_screen(x, y, width, height)
            screen.real_click_at(native_x, native_y)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        # 等待点击引起的界面变化基本稳定后再截屏回读
        time.sleep(0.25)

        try:
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(
                tool_call_id,
                f"点击已执行，但回读屏幕截图失败：{exc}",
            )

        screen.draw_click_marker(canvas, x, y)
        data_url, png_bytes = screen.image_to_data_url(canvas)

        message = (
            f"已执行一次真实左键点击：画布坐标 ({x}, {y})"
            f"（对应真实像素 {native_x}, {native_y}）。"
        )
        saved_file = ""
        try:
            filename = screen.new_filename("computer_real_click")
            saved_file = str(screen.save_tmp_image(canvas, filename))
        except OSError as exc:
            message += f" 标注截图保存失败：{exc}"

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "real_click",
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
                                f"已完成一次真实左键点击（画布坐标 {x}, {y}）。"
                                "以下为点击后的屏幕，红圈即本次点击位置："
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
