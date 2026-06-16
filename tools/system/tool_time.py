"""Tool: time_tool — 获取当前日期和时间。"""

from datetime import datetime

from pydantic import BaseModel

from tools.base import ToolBase, format_success


class TimeInput(BaseModel):
    """time_tool 无参数，直接调用即可。"""


class TimeTool(ToolBase):
    name: str = "time_tool"
    description: str = "获取当前日期和时间。直接调用即可，无需先读文档。[调用积极性: 不推荐调用] [get_doc: 无 get_doc 选项]"
    args_schema: type[BaseModel] = TimeInput

    def _run(self) -> str:
        now = datetime.now()
        return format_success({
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": "Asia/Shanghai",
        })
