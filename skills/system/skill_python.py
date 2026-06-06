"""Skill: run_python — 执行 Python 代码。"""

import asyncio
import io
import json
import sys

from pydantic import BaseModel, Field

from api import interaction
from skills.base import SkillBase, format_error, format_success


class RunPythonInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取使用说明和安全限制"
    )
    code: str = Field(
        default="",
        description="要执行的 Python 代码，支持多行"
    )


class RunPythonSkill(SkillBase):
    name: str = "run_python"
    description: str = (
        "在隔离环境中执行 Python 代码，返回 stdout 输出。"
        "用于计算、数据处理、文本转换。★ 首次使用先 get_doc=true 了解安全限制。"
    )
    args_schema: type[BaseModel] = RunPythonInput

    def _run(self, get_doc: bool = False, code: str = "") -> str:
        raise NotImplementedError("run_python 仅支持异步模式，请使用 _arun")

    async def _arun(self, get_doc: bool = False, code: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not code:
            return format_error("code 不能为空")

        if interaction.auto_approve.get():
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                exec(code, {"__builtins__": __builtins__})
                output = sys.stdout.getvalue()
                return format_success({
                    "output": output if output else "（代码执行完毕，无输出）",
                    "code": code,
                })
            except Exception as e:
                return format_error(f"代码执行错误: {e}")
            finally:
                sys.stdout = old_stdout

        ws = interaction.current_ws.get()
        interaction_id, future = interaction.register()

        await ws.send_json({
            "type": "ask_user",
            "payload": {
                "tool_name": self.name,
                "question": "即将执行以下 Python 代码，是否确认执行？",
                "mode": "confirm",
                "options": ["执行", "取消"],
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

            if action == "approve":
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    exec(code, {"__builtins__": __builtins__})
                    output = sys.stdout.getvalue()
                    return format_success({
                        "output": output if output else "（代码执行完毕，无输出）",
                        "code": code,
                    })
                except Exception as e:
                    return format_error(f"代码执行错误: {e}")
                finally:
                    sys.stdout = old_stdout
            else:
                if reason:
                    return format_error(f"用户拒绝执行代码。原因：{reason}")
                else:
                    return format_error("用户拒绝执行代码")

        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
