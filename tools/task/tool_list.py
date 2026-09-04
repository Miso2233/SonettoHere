"""Tool: list_background — 列出当前会话的全部后台任务及其状态。"""

from pydantic import BaseModel

from api.agent import background, interaction
from tools.base import ToolBase, format_success


class ListBackgroundInput(BaseModel):
    """list_background 输入参数（无需入参）"""


class ListBackgroundTool(ToolBase):
    """查看当前会话全部后台任务（@background 工具 spawn）的索引与状态。"""

    name: str = "list_background"
    description: str = (
        "列出当前全部后台运行中的任务（配合支持 background 参数的工具使用）。"
        "返回每个任务的索引、来源工具、状态（running/completed/failed）与耗时。"
        "需要取回某个任务的真实结果时，用 await_background 工具传入其索引。"
        "[调用积极性: 不确定有哪些后台任务时调用]"
    )
    args_schema: type[BaseModel] = ListBackgroundInput

    async def _arun(self) -> str:
        """返回全部后台任务概要（供 agent 发现索引与查看进度）。"""
        session_id = interaction.current_session_id.get()
        registry = background.find_registry(session_id) if session_id else None
        tasks = registry.describe() if registry else []
        running = sum(1 for t in tasks if t["status"] == "running")
        return format_success({"tasks": tasks, "count": len(tasks), "running": running})
