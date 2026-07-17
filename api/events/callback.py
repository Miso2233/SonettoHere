"""CallbackSender — LangChain 回调事件发送封装。

供 WebSocketCallback 使用，替代原有的裸 self._ws.send_json() 调用。
"""

from __future__ import annotations

from api.events.transport import WsTransport


class CallbackSender(WsTransport):
    """LangChain 回调事件发送器。

    负责推送 LLM 思考流（thinking_start/token/thinking_end）
    以及工具调用生命周期（tool_start/tool_end/tool_error）。
    """

    async def thinking_start(self, timestamp: float) -> None:
        """推送 LLM 开始思考。"""
        await self._send("thinking_start", {"timestamp": timestamp})

    async def token(self, token: str) -> None:
        """推送 LLM 流式输出 token。"""
        await self._send("token", {"token": token})

    async def thinking_end(self, timestamp: float) -> None:
        """推送 LLM 思考结束。"""
        await self._send("thinking_end", {"timestamp": timestamp})

    async def tool_start(self, call_id: str, tool_name: str, input: str) -> None:
        """推送工具开始执行。input 建议在调用前截断。"""
        await self._send("tool_start", {
            "call_id": call_id,
            "tool_name": tool_name,
            "input": input,
        })

    async def tool_end(
        self,
        call_id: str,
        tool_name: str,
        output: str,
        elapsed: float,
        tool_data: dict | None = None,
    ) -> None:
        """推送工具执行完毕。"""
        payload: dict = {
            "call_id": call_id,
            "tool_name": tool_name,
            "output": output,
            "elapsed": elapsed,
        }
        if tool_data is not None:
            payload["tool_data"] = tool_data
        await self._send("tool_end", payload)

    async def tool_error(self, call_id: str, tool_name: str, error: str) -> None:
        """推送工具执行错误。"""
        await self._send("tool_error", {
            "call_id": call_id,
            "tool_name": tool_name,
            "error": error,
        })
