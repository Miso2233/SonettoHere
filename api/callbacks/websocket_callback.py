"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import ast
import json
import time
from typing import Any

from fastapi import WebSocket
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


def _extract_content(output: Any) -> str:
    """从工具输出中提取字符串内容。

    LangChain ToolMessage 的 __str__ 会返回 "content='...' name='...' tool_call_id='...'"
    这种无法解析的格式，需要取其 .content 属性获取真正的 JSON。
    """
    if hasattr(output, 'content'):
        return str(output.content)
    if not isinstance(output, str):
        return str(output)
    return output


class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}

    @staticmethod
    def _extract_tool_data(tool_name: str, output: Any, tool_input: str | None = None) -> dict[str, Any] | None:
        """从工具输出中提取前端专属气泡所需的结构化数据。"""
        out_str = _extract_content(output)
        try:
            parsed = json.loads(out_str)
        except (json.JSONDecodeError, TypeError):
            return None

        if tool_name == "bilibili_download":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            cover_path = data.get("cover_path", "")
            return {
                "video_title": data.get("title"),
                "cover_url": f"/api/file?path={cover_path}" if cover_path else None,
                "file_path": data.get("file_path"),
                "quality": data.get("quality"),
            }

        # ── Todo 系列工具 ──
        if tool_name.startswith("todo_"):
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None

            if tool_name == "todo_list":
                tool_type = "task_list"
            elif tool_name == "todo_list_projects":
                tool_type = "project_list"
            else:
                tool_type = "single_task"

            result: dict[str, Any] = {"tool_type": tool_type}
            if tool_type == "task_list":
                result["total"] = data.get("total")
                tasks = data.get("tasks", [])
                if isinstance(tasks, list):
                    result["tasks"] = tasks
            elif tool_type == "project_list":
                result["total"] = data.get("total")
                projects = data.get("projects", [])
                if isinstance(projects, list):
                    result["projects"] = projects
            else:
                for field in ("task_id", "content", "due_date", "priority",
                              "project", "message", "is_completed"):
                    if field in data:
                        result[field] = data[field]
            return result

        # ── Task Tracker ──
        if tool_name == "task_tracker":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            result: dict[str, Any] = {
                "tool_type": "task_tracker",
                "status": data.get("status"),
                "total_steps": data.get("total_steps"),
                "current_step": data.get("current_step"),
                "current_task": data.get("current_task"),
            }
            tasks = data.get("tasks")
            if isinstance(tasks, list):
                result["tasks"] = tasks
            if "message" in data:
                result["message"] = data["message"]
            return result

        # ── Python 执行 ──
        if tool_name == "run_python":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            result: dict[str, Any] = {
                "tool_type": "run_python",
                "stdout": data.get("output", ""),
            }
            # 从输入端提取代码（LangChain 传入的是 Python repr 格式，非 JSON）
            if tool_input:
                try:
                    input_parsed = ast.literal_eval(tool_input)
                except (ValueError, SyntaxError, TypeError):
                    pass
                else:
                    if isinstance(input_parsed, dict):
                        code = input_parsed.get("code", "")
                        if isinstance(code, str) and code:
                            result["code"] = code
            return result

        return None

    async def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._thinking_started = True
        await self._ws.send_json({
            "type": "thinking_start",
            "payload": {"timestamp": time.time()},
        })

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        await self._ws.send_json({
            "type": "token",
            "payload": {"token": token},
        })

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self._thinking_started:
            self._thinking_started = False
            await self._ws.send_json({
                "type": "thinking_end",
                "payload": {"timestamp": time.time()},
            })

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name
        self._tool_inputs[run_id] = input_str

        await self._ws.send_json({
            "type": "tool_start",
            "payload": {
                "tool_name": tool_name,
                "input": input_str[:500] if len(input_str) > 500 else input_str,
            },
        })

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")
        tool_input = self._tool_inputs.pop(run_id, None)

        out_str = _extract_content(output)

        # 提取工具专属结构化数据
        tool_data = self._extract_tool_data(tool_name, output, tool_input)

        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._ws.send_json({
            "type": "tool_end",
            "payload": {
                "tool_name": tool_name,
                "output": out_str,
                "elapsed": round(elapsed, 2),
                "tool_data": tool_data,
            },
        })

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        self._tool_inputs.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._ws.send_json({
            "type": "tool_error",
            "payload": {
                "tool_name": tool_name,
                "error": str(error),
            },
        })
