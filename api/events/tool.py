"""ToolSender — 工具层事件发送封装。

供 ask_user 系列交互工具和 call_sub_agent 工具使用。
"""

from __future__ import annotations

from typing import Any

from api.events.transport import WsTransport


class ToolSender(WsTransport):
    """工具层事件发送器。

    负责推送前端交互请求（ask_user）和子会话创建通知（sub_session_created）。
    """

    async def ask_user(
        self,
        tool_name: str,
        question: str,
        mode: str,
        interaction_id: str,
        options: list[str] | None = None,
        **extra: Any,
    ) -> None:
        """向用户提问并等待响应。

        ``options`` 仅供「采集输入」模式（single_choice / multi_choice）携带
        候选答案；confirm 模式不使用，按钮文案改由 ``extra`` 中的
        ``approve_text`` / ``reject_text`` 指定。``extra`` 其余字段为确认载荷:
        run_python 的 ``code``、文件工具的 ``file_path`` / ``content`` /
        ``edits`` / ``directory_path`` 等,前端据此渲染确认气泡内容。
        """
        payload: dict = {
            "tool_name": tool_name,
            "question": question,
            "mode": mode,
            "interaction_id": interaction_id,
        }
        if options:
            payload["options"] = options
        payload.update(extra)
        await self._send("ask_user", payload)

    async def tool_stream(self, call_id: str, tool_name: str, chunk: str) -> None:
        """推送工具执行过程中的实时输出片段（如 run_python 的逐条 print）。

        ``call_id`` 与 tool_start/tool_end 事件一致（均为 LangChain run_id），
        前端据此精确匹配到对应的工具气泡。
        """
        await self._send("tool_stream", {
            "call_id": call_id,
            "tool_name": tool_name,
            "chunk": chunk,
        })

    async def sub_session_created(
        self,
        sub_session_id: str,
        parent_session_id: str | None,
        task: str,
        name: str,
    ) -> None:
        """通知前端子会话已创建（sub-agent）。"""
        await self._send("sub_session_created", {
            "sub_session_id": sub_session_id,
            "parent_session_id": parent_session_id,
            "task": task,
            "name": name,
        })

    async def background_update(
        self,
        index: int,
        status: str,
        tool_name: str,
        result_preview: str = "",
        elapsed_s: float = 0.0,
    ) -> None:
        """推送后台任务状态变化（@background 工具返回索引之后的终态）。

        ``index`` 为 spawn 时返回给 LLM 的任务索引，前端据此匹配发起调用的
        工具气泡上的后台徽章；``result_preview`` 为截断的结果预览。
        """
        await self._send("background_update", {
            "index": index,
            "status": status,
            "tool_name": tool_name,
            "result_preview": result_preview,
            "elapsed_s": round(elapsed_s, 1),
        })
