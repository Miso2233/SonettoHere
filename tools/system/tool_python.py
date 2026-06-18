"""Tool: run_python — 执行 Python 代码。"""

import asyncio
import io
import sys

from pydantic import BaseModel, Field

from api import interaction
from api.code_permission_store import add_permission, check_permission, code_hash
from api.session_manager import SessionState
from tools.base import ToolBase, format_error, format_success, get_safe_builtins

# 模块级常量：安全 builtins 只构造一次
_SAFE_BUILTINS = get_safe_builtins()


def _exec_code(code: str) -> str:
    """在线程中执行代码并捕获 stdout。返回输出文本。"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, {"__builtins__": _SAFE_BUILTINS})
        return sys.stdout.getvalue() or "（代码执行完毕，无输出）"
    except Exception as e:
        raise RuntimeError(f"代码执行错误: {e}") from e
    finally:
        sys.stdout = old_stdout


async def _get_session() -> SessionState | None:
    """从当前 interaction 上下文获取 SessionState（通过 WebSocket 的 app.state）。"""
    try:
        ws = interaction.current_ws.get()
        session_id = ws.scope["path"].rsplit("/", 1)[-1]
        return ws.app.state.session_manager.get(session_id)
    except Exception:
        return None


class RunPythonInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取使用说明和安全限制"
    )
    code: str = Field(
        default="",
        description="要执行的 Python 代码，支持多行"
    )


class RunPythonTool(ToolBase):
    name: str = "run_python"
    description: str = (
        "在隔离环境中执行 Python 代码，返回 stdout 输出。"
        "用于计算、数据处理、文本转换。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = RunPythonInput

    def _run(self, get_doc: bool = False, code: str = "") -> str:
        raise NotImplementedError("run_python 仅支持异步模式，请使用 _arun")

    async def _exec_with_approval(self, code: str) -> str:
        try:
            output = await asyncio.to_thread(_exec_code, code)
            return format_success({"output": output, "code": code})
        except Exception as e:
            return format_error(str(e))

    async def _arun(self, get_doc: bool = False, code: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not code:
            return format_error("code 不能为空")

        # ── 自动批准模式：跳过所有确认 ──
        if interaction.auto_approve.get():
            return await self._exec_with_approval(code)

        # ── 权限检查 ──
        h = code_hash(code)

        # 1. 检查永久权限
        permanent = check_permission(code)
        if permanent == "allow":
            return await self._exec_with_approval(code)
        if permanent == "deny":
            return format_error("该代码已被永久拒绝执行")

        # 2. 检查会话级权限
        session = await _get_session()
        if session is not None:
            if h in session.approved_code_hashes:
                return await self._exec_with_approval(code)
            if h in session.denied_code_hashes:
                return format_error("该代码已在本会话中被拒绝执行")

        # ── 用户交互确认 ──
        ws = interaction.current_ws.get()
        interaction_id, future = interaction.register()

        await ws.send_json({
            "type": "ask_user",
            "payload": {
                "tool_name": self.name,
                "question": "即将执行以下 Python 代码，请选择操作：",
                "mode": "confirm",
                "options": ["本次允许", "永久允许", "本次拒绝", "永久拒绝"],
                "interaction_id": interaction_id,
                "code": code,
            },
        })

        try:
            answer = await future

            action = answer
            reason = ""
            if isinstance(answer, dict):
                action = answer.get("action", "")
                reason = answer.get("reason", "")

            match action:
                case "approve_session":
                    if session is not None:
                        session.approved_code_hashes.add(h)
                    return await self._exec_with_approval(code)

                case "approve_permanent":
                    add_permission(code, "allow", "用户永久允许")
                    return await self._exec_with_approval(code)

                case "reject_session":
                    if session is not None:
                        session.denied_code_hashes.add(h)
                    if reason:
                        return format_error(f"用户拒绝执行代码。原因：{reason}")
                    return format_error("用户拒绝执行代码")

                case "reject_permanent":
                    add_permission(code, "deny", "用户永久拒绝")
                    return format_error("该代码已被永久拒绝执行")

                case _:
                    if reason:
                        return format_error(f"用户拒绝执行代码。原因：{reason}")
                    return format_error("用户拒绝执行代码")

        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
