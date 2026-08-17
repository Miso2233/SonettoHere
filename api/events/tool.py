"""ToolSender — 工具层事件发送封装。

供 ask_user 系列交互工具和 call_sub_agent 工具使用。
"""

from __future__ import annotations

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
        options: list[str],
        interaction_id: str,
        code: str | None = None,
    ) -> None:
        """向用户提问并等待响应。"""
        payload: dict = {
            "tool_name": tool_name,
            "question": question,
            "mode": mode,
            "options": options,
            "interaction_id": interaction_id,
        }
        if code is not None:
            payload["code"] = code
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
