"""Tool: await_background — 按索引等待/取回后台任务的真实结果。"""

import asyncio

from pydantic import BaseModel, Field

from api.agent import background, interaction
from tools.base import ToolBase, format_error, format_success


class AwaitBackgroundInput(BaseModel):
    """await_background 输入参数"""

    index: int = Field(
        ge=1,
        description="要等待的后台任务索引（@background 调用返回的 task_index）",
    )
    timeout_seconds: int = Field(
        default=180,
        ge=1,
        le=1800,
        description="最长等待秒数；任务仍未完成时返回 running 状态，可稍后再次调用",
    )


class AwaitBackgroundTool(ToolBase):
    """等待后台任务完成并取回其真实返回值（配合 @background 工具使用）。"""

    name: str = "await_background"
    description: str = (
        "等待一个后台运行的任务并取回其真实结果。"
        "配合支持 background 参数的工具使用：先以 background=true 调用获得任务索引，"
        "再用本工具传入该索引等待结果完成。"
        "任务尚未完成且超过 timeout_seconds 时返回 running 状态（不无限阻塞），"
        "可稍后再次调用。不确定有哪些后台任务时，先用 list_background 查看。"
        "[调用积极性: 需要取回后台结果时调用]"
    )
    args_schema: type[BaseModel] = AwaitBackgroundInput

    async def _arun(self, index: int, timeout_seconds: int = 180) -> str:
        """等待后台任务并返回其真实输出。

        - 已完成：原样返回后台任务存储的真实工具输出（不套第二层信封，
          避免 LLM 语境被双层 JSON 污染；存储的是 format_error 时自然被
          WebSocket 回调路由为 tool_error）。
        - 超时仍在运行：返回 running 状态让 agent 自行决定稍后重试，
          不无限阻塞 agent 循环。
        """
        session_id = interaction.current_session_id.get()
        registry = background.find_registry(session_id) if session_id else None
        if registry is None or not registry.has_tasks():
            return format_error("当前没有任何后台任务（可用 list_background 查看）")

        bt = registry.get(index)
        if bt is None:
            return format_error(
                f"后台任务 #{index} 不存在（可能已完成并被淘汰，或服务重启后丢失）。"
                "可用 list_background 查看当前全部后台任务"
            )

        if bt.status == "running":
            try:
                await registry.await_result(index, timeout_seconds)
            except asyncio.CancelledError:
                return format_error("用户取消了回复")

        if bt.status == "failed":
            return bt.result
        if bt.status == "completed":
            return bt.result

        # 超时仍在运行：返回状态让 agent 决策（稍后再 await）
        return format_success(
            {
                "task_index": bt.index,
                "tool_name": bt.tool_name,
                "status": "running",
                "elapsed_s": round(bt.elapsed(), 1),
                "hint": "任务仍在后台运行，稍后可再次调用 await_background 等待",
            }
        )
