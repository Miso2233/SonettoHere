"""Tool: run_python — 执行 Python 代码（实时流式推送 stdout）。"""

import asyncio
import io
import sys
from collections.abc import Callable

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from api.agent import interaction
from api.events import ToolSender
from tools.base import ToolBase, format_error, format_success, get_safe_builtins

# 模块级常量：安全 builtins 只构造一次
_SAFE_BUILTINS = get_safe_builtins()

# 流式队列结束哨兵：worker 执行完毕后（finally）入队，消费侧据此停止
_DONE: object = object()


class _StreamToQueue(io.TextIOBase):
    """自定义 stdout/stderr 流：每次 write() 触发一次 emit（实时转发）。

    替代原一次性捕获的 ``io.StringIO``：exec 中每调用一次 print 就推送一次。
    同时把片段累积到 ``buf``，供执行结束后返回完整输出。
    """

    def __init__(self, buf: list[str], emit: Callable[[str], None]) -> None:
        self._buf = buf
        self._emit = emit

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:
        if s:
            self._buf.append(s)
            self._emit(s)
        return len(s)

    def flush(self) -> None:
        pass


def _exec_code(code: str) -> str:
    """在线程中执行代码并一次性捕获 stdout。返回输出文本。

    无 WebSocket 连接或 run_id 缺失时的回退路径（不推送流式事件）。
    """
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, {"__builtins__": _SAFE_BUILTINS})
        return sys.stdout.getvalue() or "（代码执行完毕，无输出）"
    except Exception as e:
        raise RuntimeError(f"代码执行错误: {e}") from e
    finally:
        sys.stdout = old_stdout


async def _exec_code_streaming(
    code: str, tool_name: str, run_id: str, sender: ToolSender
) -> str:
    """流式执行代码：每产生一段输出就推送一条 ``tool_stream`` 事件。

    线程→异步桥接：exec 跑在 ``asyncio.to_thread`` 工作线程，自定义流把每段
    输出通过 ``loop.call_soon_threadsafe`` 塞进 ``asyncio.Queue``，主协程并发
    消费队列逐条推送。执行完毕（含异常，由 finally）入队结束哨兵。

    Args:
        code: 要执行的 Python 代码。
        tool_name: 工具名（用于 tool_stream 事件）。
        run_id: 当前工具调用的 run_id（作为 tool_stream 的 call_id，
            与 tool_start/tool_end 事件一致，前端据此精确匹配气泡）。
        sender: WebSocket 发送器，用于推送流式事件。

    Returns:
        累积的完整输出文本（供 LLM 与 tool_data 使用）。
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | object] = asyncio.Queue()

    def emit(chunk: str | object) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, chunk)

    def worker() -> str:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        buf: list[str] = []
        stream = _StreamToQueue(buf, emit)
        sys.stdout = stream
        sys.stderr = stream
        try:
            exec(code, {"__builtins__": _SAFE_BUILTINS})
            return "".join(buf)
        except Exception as e:
            raise RuntimeError(f"代码执行错误: {e}") from e
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            emit(_DONE)  # 结束哨兵：保证即使异常也发出，消费侧不会悬挂

    exec_task = asyncio.create_task(asyncio.to_thread(worker))

    async def drain() -> None:
        while True:
            chunk = await queue.get()
            if chunk is _DONE:
                return
            if isinstance(chunk, str):
                await sender.tool_stream(call_id=run_id, tool_name=tool_name, chunk=chunk)

    drain_task = asyncio.create_task(drain())

    try:
        output = await exec_task
    finally:
        await drain_task
    return output or "（代码执行完毕，无输出）"


async def _run_code(code: str, run_id: str, sender: ToolSender | None) -> str:
    """执行代码并返回统一成功/错误响应。

    sender 与 run_id 均可用时流式推送；否则退化为一次性捕获。
    """
    try:
        if sender is not None and run_id:
            output = await _exec_code_streaming(code, "run_python", run_id, sender)
        else:
            output = await asyncio.to_thread(_exec_code, code)
        return format_success({"output": output, "code": code})
    except Exception as e:
        return format_error(str(e))


class RunPythonInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和安全限制"
    )
    code: str = Field(default="", description="要执行的 Python 代码，支持多行")


class RunPythonTool(ToolBase):
    name: str = "run_python"
    description: str = (
        "在隔离环境中执行 Python 代码，返回 stdout 输出。"
        "用于计算、数据处理、文本转换。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = RunPythonInput

    def _run(self, get_doc: bool = False, code: str = "") -> str:
        raise NotImplementedError("run_python 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        get_doc: bool = False,
        code: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """执行代码，实时向前端推送每条 stdout。

        ``run_manager`` 由 LangChain 自动注入（``BaseTool.arun`` 检测到
        ``_arun`` 声明该形参即注入当前调用的 run manager），其 ``run_id``
        与 WebSocket 回调 ``on_tool_start`` 收到的 run_id 完全一致，用作
        ``tool_stream`` 事件的 call_id，前端据此与工具气泡精确匹配
        （不依赖 tool_name，并行调用也不会串流）。
        """
        if get_doc:
            return self._load_doc()
        if not code:
            return format_error("code 不能为空")

        run_id = str(run_manager.run_id) if run_manager and run_manager.run_id else ""

        session_id = interaction.current_session_id.get()
        if session_id and interaction.get_session_auto_approve(session_id):
            # 仅当有 run_id 时才获取 sender 尝试流式；否则保持原一次性捕获，
            # 避免无 run_id 场景（如直接调用）无谓地依赖 WebSocket 上下文。
            sender = ToolSender.from_context() if run_id else None
            return await _run_code(code, run_id, sender)

        sender = ToolSender.from_context()
        if sender is None:
            return format_error("WebSocket 连接不可用")

        interaction_id, future = interaction.register()

        await sender.ask_user(
            tool_name=self.name,
            question="即将执行以下 Python 代码，是否确认执行？",
            mode="confirm",
            options=["执行", "取消"],
            interaction_id=interaction_id,
            code=code,
        )

        try:
            answer = await future

            action = answer
            reason = ""
            if isinstance(answer, dict):
                action = answer.get("action", "")
                reason = answer.get("reason", "")

            if action == "approve":
                return await _run_code(code, run_id, sender)
            else:
                if reason:
                    return format_error(f"用户拒绝执行代码。原因：{reason}")
                return format_error("用户拒绝执行代码")

        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
