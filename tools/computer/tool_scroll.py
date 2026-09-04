"""Tool: computer_scroll — 滚动：在真实屏幕上滚动页面/列表。

执行一次真实滚轮滚动，可指定方向（up/down/left/right）与滚动量，并可传可选
画布坐标作为落点（先移动光标到该处再滚）。只做动作、返回文字确认，不截屏。
"""

from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.computer import _screen as screen
from tools.get_doc import get_doc


class Point(BaseModel):
    x: int = Field(
        ge=0,
        le=screen.CANVAS_WIDTH,
        description=(
            f"画布 X 坐标（整数，0..{screen.CANVAS_WIDTH}，"
            "基于最近一张截图画布推算）"
        ),
    )
    y: int = Field(
        ge=0,
        le=screen.CANVAS_HEIGHT,
        description=(
            f"画布 Y 坐标（整数，0..{screen.CANVAS_HEIGHT}，"
            "基于最近一张截图画布推算）"
        ),
    )


class ScrollInput(BaseModel):
    scroll_direction: Literal["up", "down", "left", "right"] = Field(
        description="滚动方向：up 向上 / down 向下 / left 向左 / right 向右"
    )
    scroll_amount: int = Field(
        ge=1,
        description="滚动量（滚轮格数/档数），数值越大滚得越多",
    )
    coordinate: Point | None = Field(
        default=None,
        description=(
            "可选的滚动落点（1920x1080 画布坐标）：先移动光标到该处再滚动，"
            "用于悬停在某个元素上滚动；不传则在当前光标位置滚动"
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
class ScrollTool(ToolBase):
    name: str = "computer_scroll"
    description: str = (
        "滚动：在真实屏幕上执行一次真实滚轮滚动。scroll_direction 为滚动方向"
        "（up/down/left/right），scroll_amount 为滚动量（滚轮格数）。可选 "
        "coordinate 传入 1920x1080 画布坐标作为落点（先移光标到该处再滚，适合"
        "悬停列表/面板上滚动）；不传则在当前光标位置滚动。只执行滚动并返回确认，"
        "如需查看滚动后的内容请调用 computer_screenshot 截屏。"
        "[调用积极性: 页面/列表/窗口内容需要上下（或左右）翻动查看更多时使用。]"
    )
    args_schema: type[BaseModel] = ScrollInput

    async def _arun(
        self,
        scroll_direction: str = "down",
        scroll_amount: int = 1,
        coordinate: Point | None = None,
        tool_call_id: str = "",
    ) -> Command:
        return await off_thread(
            self._run_impl, scroll_direction, scroll_amount, coordinate, tool_call_id
        )

    def _run_impl(
        self,
        scroll_direction: str = "down",
        scroll_amount: int = 1,
        coordinate: Point | None = None,
        tool_call_id: str = "",
    ) -> Command:
        screen_size: dict[str, int] | None = None
        coordinate_screen: dict[str, int] | None = None
        at_text = "当前光标位置"
        try:
            native_x: int | None = None
            native_y: int | None = None
            if coordinate is not None:
                width, height = screen.logical_screen_size()
                screen_size = {"width": width, "height": height}
                native_x, native_y = screen.canvas_to_screen(
                    coordinate.x, coordinate.y, width, height
                )
                coordinate_screen = {"x": native_x, "y": native_y}
                at_text = f"画布坐标 ({coordinate.x}, {coordinate.y})"
            screen.scroll(scroll_direction, scroll_amount, native_x, native_y)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        message = (
            f"已在{at_text}向 {scroll_direction} 方向滚动 {scroll_amount} 格。"
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "scroll",
                            "message": message,
                            "scroll_direction": scroll_direction,
                            "scroll_amount": scroll_amount,
                            "coordinate_canvas": (
                                {"x": coordinate.x, "y": coordinate.y}
                                if coordinate is not None
                                else None
                            ),
                            "coordinate_screen": coordinate_screen,
                            "screen_size": screen_size,
                        }),
                        tool_call_id=tool_call_id,
                    ),
                ],
            },
        )
