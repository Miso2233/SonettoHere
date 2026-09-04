"""Tool: computer_click — 真实点击：对系统执行一次物理鼠标点击。

与 computer_virtual_click（虚拟点击，仅标注不做操作）是**两个不同工具**。
本工具（computer_click）会真实移动系统光标并按指定按键/次数点击：支持
left/middle/right 与单击/双击/三击。点击结束后等待 0.1s 再截取**未标注**
的屏幕画面注入 LLM 上下文。截图不落盘保存。
"""

import time
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.computer import _screen as screen
from tools.get_doc import get_doc

# 鼠标按键 → 中文
_BUTTON_CN = {"left": "左", "middle": "中", "right": "右"}
# 点击次数 → 中文
_CLICKS_CN = {1: "单击", 2: "双击", 3: "三击"}


class ClickInput(BaseModel):
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
    button: Literal["left", "middle", "right"] = Field(
        default="left",
        description="鼠标按键：left 左键 / middle 中键 / right 右键",
    )
    clicks: Literal[1, 2, 3] = Field(
        default=1,
        description="点击次数：1 单击 / 2 双击 / 3 三击",
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
class ClickTool(ToolBase):
    name: str = "computer_click"
    description: str = (
        "真实点击：在最近一张截图对应的位置，对真实系统执行一次**物理鼠标点击**"
        "（会真实移动鼠标光标并按下，触发应用的真实行为）。支持按键 button（left "
        "左键 / middle 中键 / right 右键，默认 left）与点击次数 clicks（1 单击 / "
        "2 双击 / 3 三击，默认 1）。坐标必须是基于 1920x1080 逻辑画布输出的整数"
        "（x: 0..1920，y: 0..1080，原点在画布左上角），后端会线性映射回真实像素并"
        "执行。点击结束后等待 0.1s 再截取点击后的屏幕（**不叠加标记**），把画面注入"
        "上下文供确认。如需先无副作用地核对落点是否命中，应先用 computer_virtual_click "
        "标注试算。"
        "[调用积极性: 用户明确要求/确认后需要在系统里真实按下某个按钮、图标、菜单项"
        "（含左/中/右键，需双击/三击）时使用；坐标不确定时先用 computer_screenshot / "
        "computer_virtual_click 确认。]"
    )
    args_schema: type[BaseModel] = ClickInput

    async def _arun(
        self,
        x: int = 0,
        y: int = 0,
        button: str = "left",
        clicks: int = 1,
        tool_call_id: str = "",
    ) -> Command:
        return await off_thread(self._run_impl, x, y, button, clicks, tool_call_id)

    def _run_impl(
        self,
        x: int = 0,
        y: int = 0,
        button: str = "left",
        clicks: int = 1,
        tool_call_id: str = "",
    ) -> Command:
        if not (0 <= x <= screen.CANVAS_WIDTH and 0 <= y <= screen.CANVAS_HEIGHT):
            return _error_command(
                tool_call_id,
                f"坐标越界：x/y 必须在 0..{screen.CANVAS_WIDTH} / 0..{screen.CANVAS_HEIGHT} 之间",
            )

        try:
            width, height = screen.logical_screen_size()
            native_x, native_y = screen.canvas_to_screen(x, y, width, height)
            screen.real_click_at(native_x, native_y, button=button, clicks=clicks)
        except screen.ScreenError as exc:
            return _error_command(tool_call_id, str(exc))

        # 点击结束后等待 0.1s，再截取点击后的屏幕（不叠加标记、不落盘）
        time.sleep(0.1)

        try:
            canvas = screen.to_canvas_image(screen.capture_screen())
        except screen.ScreenError as exc:
            return _error_command(
                tool_call_id,
                f"点击已执行，但回读屏幕截图失败：{exc}",
            )

        data_url, png_bytes = screen.image_to_data_url(canvas)

        label = f"{_CLICKS_CN.get(clicks, clicks)}（{_BUTTON_CN.get(button, button)}键）"
        message = (
            f"已执行一次真实{label}：画布坐标 ({x}, {y})"
            f"（对应真实像素 {native_x}, {native_y}）。"
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "real_click",
                            "message": message,
                            "click_canvas": {"x": x, "y": y},
                            "click_screen": {"x": native_x, "y": native_y},
                            "button": button,
                            "clicks": clicks,
                            "screen_size": {"width": width, "height": height},
                            "image_bytes": len(png_bytes),
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": (
                                f"已完成一次真实{label}（画布坐标 {x}, {y}）。"
                                "以下为点击后的屏幕（未标注，供观察实际效果）："
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
