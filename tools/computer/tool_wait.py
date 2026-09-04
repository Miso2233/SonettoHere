"""Tool: computer_wait — 等待：暂停若干秒后再继续。

不做任何真实操作，仅按 *duration* 秒等待（常用于等界面动画/加载完成）。
只返回文字确认，不截屏。
"""

import time
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.get_doc import get_doc


class WaitInput(BaseModel):
    duration: float = Field(
        gt=0,
        le=60,
        description="等待时长（秒），0 到 60 之间，如 0.5、2、3.5",
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
class WaitTool(ToolBase):
    name: str = "computer_wait"
    description: str = (
        "等待：暂停 *duration* 秒后再继续，不执行任何其它操作。常用于等待界面"
        "动画、加载、对话框出现或截图需要留白等场景；duration 单位为秒（0<值≤60）。"
        "若只是想观察当前画面，等待后调用 computer_screenshot 查看。"
        "[调用积极性: 需要给页面动画/加载留时间、或确认操作已生效后再继续时使用。]"
    )
    args_schema: type[BaseModel] = WaitInput

    async def _arun(self, duration: float = 1.0, tool_call_id: str = "") -> Command:
        return await off_thread(self._run_impl, duration, tool_call_id)

    def _run_impl(self, duration: float = 1.0, tool_call_id: str = "") -> Command:
        if duration <= 0:
            return _error_command(tool_call_id, "duration 必须大于 0")

        time.sleep(duration)

        message = f"已等待 {duration:g} 秒。"

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "action": "wait",
                            "message": message,
                            "duration": duration,
                        }),
                        tool_call_id=tool_call_id,
                    ),
                ],
            },
        )
