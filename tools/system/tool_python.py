"""Tool: run_python — 在子进程中执行 Python 代码，支持实时流式推送与中途停止。

执行模型：
- 以 ``python -u _python_runner.py`` 拉起独立子进程，stdin 传入代码，
  父进程增量读取 stdout（stderr 合并入同一管道）按行推送 ``tool_stream``。
- 子进程隔离使中途停止可以 ``proc.kill()`` 彻底终止执行（含 ``time.sleep``
  等阻塞 C 调用），这正是线程内 exec 做不到的。
- 每个运行注册进 ``_exec_runs`` 注册表，前端 ``run_python_interrupt`` 消息
  通过 ``interrupt_run()`` 定位并终止对应子进程。
"""

import asyncio
import codecs
import contextlib
import io
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from api.events import ToolSender
from tools.base import ToolBase, format_error, format_success, get_safe_builtins
from tools.confirm import confirm_execution

# 模块级常量：安全 builtins 只构造一次
_SAFE_BUILTINS = get_safe_builtins()

# 子进程执行器路径与项目根目录（供子进程 import tools.base）
_PYTHON_RUNNER = Path(__file__).resolve().parent / "_python_runner.py"
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# 子进程 stderr 上的错误标记：runner 打印 `__RUN_PYTHON_ERROR__::<Type>: <msg>`
_ERROR_MARKER = "__RUN_PYTHON_ERROR__::"


@dataclass
class _ExecHandle:
    """单次 run_python 执行的句柄，供 interrupt_run 定位并终止子进程。"""

    proc: asyncio.subprocess.Process | None = None
    interrupted: bool = False
    user_message: str = ""
    exit_code: int | None = None

    def request_stop(self, message: str = "") -> None:
        """请求停止执行：幂等；记录截止信息并（若子进程已启动）立即 kill。"""
        if self.interrupted:
            return
        self.interrupted = True
        if message:
            self.user_message = message
        proc = self.proc
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass


# 运行中 run_python 注册表：run_id → 执行句柄。
# 全部操作都发生在同一事件循环线程（ws handler / agent task），无需加锁。
_exec_runs: dict[str, _ExecHandle] = {}


def interrupt_run(call_id: str, message: str = "") -> bool:
    """请求停止指定 run_id 的 python 子进程。返回是否找到该运行。

    ``call_id`` 即 tool_stream 的 call_id（run_id），与 tool_start/tool_end 一致。
    停止后工具返回带 ``interrupted`` 与 ``user_message`` 的结果，Agent 继续回应。
    """
    handle = _exec_runs.get(call_id)
    if handle is None:
        return False
    handle.request_stop(message)
    return True


def interrupt_all_runs() -> int:
    """停止全部运行中的 python 子进程（Agent 整轮取消时的兜底）。返回数量。"""
    handles = list(_exec_runs.values())
    for h in handles:
        h.request_stop("Agent 轮次已取消")
    return len(handles)


def _parse_python_error(output: str) -> str:
    """从子进程输出中提取 ``__RUN_PYTHON_ERROR__::`` 标记的错误消息。"""
    for line in output.splitlines():
        idx = line.find(_ERROR_MARKER)
        if idx != -1:
            return line[idx + len(_ERROR_MARKER):].strip()
    return ""


async def _push_chunk(
    sender: ToolSender | None, run_id: str, tool_name: str, chunk: str
) -> None:
    """推送一条 tool_stream；发送失败（如 WS 断开）时静默跳过，不中断 drain。"""
    if sender is None:
        return
    try:
        await sender.tool_stream(call_id=run_id, tool_name=tool_name, chunk=chunk)
    except Exception:
        pass


async def _drain_output(
    reader: asyncio.StreamReader,
    sender: ToolSender | None,
    run_id: str,
    tool_name: str,
) -> str:
    """增量读取子进程输出：按行/阈值切块实时推送 tool_stream，并累积完整输出。

    使用增量 UTF-8 解码器，多字节字符跨 ``read()`` 拆分时不会抛 UnicodeDecodeError。
    按 ``\\n`` / ``\\r`` 或 4096 字节阈值切块——`print` 一次调用恰好一整行，
    前端看到的粒度和实时性接近旧版进程内逐条推送。
    """
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buf: list[str] = []
    pending = ""
    while True:
        data = await reader.read(4096)
        if not data:
            break
        pending += decoder.decode(data)
        # 取最早出现的行分隔符，避免 \r\n 与纯 \n 混用导致切块漂移
        while True:
            idx = -1
            for sep in ("\n", "\r"):
                pos = pending.find(sep)
                if pos != -1 and (idx == -1 or pos < idx):
                    idx = pos
            if idx == -1:
                break
            line = pending[: idx + 1]
            pending = pending[idx + 1:]
            buf.append(line)
            await _push_chunk(sender, run_id, tool_name, line)
        if len(pending) >= 4096:
            buf.append(pending)
            await _push_chunk(sender, run_id, tool_name, pending)
            pending = ""
    pending += decoder.decode(b"", final=True)
    if pending:
        buf.append(pending)
        await _push_chunk(sender, run_id, tool_name, pending)
    return "".join(buf)


async def _exec_code_streaming(
    code: str, tool_name: str, run_id: str, sender: ToolSender
) -> tuple[str, _ExecHandle]:
    """在子进程中执行代码，实时向前端推送输出，支持中途停止。

    Args:
        code: 要执行的 Python 代码。
        tool_name: 工具名（用于 tool_stream 事件）。
        run_id: 当前工具调用的 run_id（注册表键 + tool_stream call_id）。
        sender: WebSocket 发送器，用于推送流式事件。

    Returns:
        (完整输出文本, 执行句柄)。句柄携带 interrupted / user_message / exit_code，
        调用方据此构造成功或中断结果。
    """
    handle = _ExecHandle()
    _exec_runs[run_id] = handle
    proc: asyncio.subprocess.Process | None = None
    drain_task: asyncio.Task[str] | None = None
    output = ""

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"  # 子进程 stdio 强制 UTF-8（不设 PYTHONUTF8，保持 open() 编码与进程内一致）
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # 子进程不写 __pycache__ 进仓库
    existing_pypath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _PROJECT_ROOT + (
        os.pathsep + existing_pypath if existing_pypath else ""
    )
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "-B", str(_PYTHON_RUNNER),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=_PROJECT_ROOT,
            env=env,
            limit=1 << 20,
            creationflags=creationflags,
        )
        handle.proc = proc
        # 竞态兜底：interrupt_run 可能在进程创建完成前已置 interrupted
        if handle.interrupted:
            proc.kill()

        drain_task = asyncio.create_task(
            _drain_output(proc.stdout, sender, run_id, tool_name)
        )

        if proc.stdin is not None:
            try:
                proc.stdin.write(code.encode("utf-8"))
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                proc.stdin.close()

        handle.exit_code = await proc.wait()
        output = await drain_task
    finally:
        # 任何路径（正常/中断/取消）都确保子进程终止、drain 收尾、注册表清理
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
        if drain_task is not None and not drain_task.done():
            drain_task.cancel()
        if drain_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(drain_task, return_exceptions=True)
        if proc is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await proc.wait()
        _exec_runs.pop(run_id, None)

    return output, handle


def _exec_code(code: str) -> str:
    """在进程内一次性捕获执行代码。返回输出文本。

    无 WebSocket 连接或 run_id 缺失时的回退路径（不推送流式事件、不支持停止）。
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


async def _run_code(code: str, run_id: str, sender: ToolSender | None) -> str:
    """执行代码并返回统一成功/错误响应。

    sender 与 run_id 均可用时以子进程流式执行（支持中途停止）；
    否则退化为进程内一次性捕获。
    """
    try:
        if sender is not None and run_id:
            output, handle = await _exec_code_streaming(
                code, "run_python", run_id, sender
            )
            if handle.interrupted:
                return format_success({
                    "output": output,
                    "code": code,
                    "interrupted": True,
                    "user_message": handle.user_message or "用户中途停止执行",
                })
            if handle.exit_code != 0:
                error = _parse_python_error(output) or f"执行失败，退出码 {handle.exit_code}"
                return format_error(error)
            return format_success({"output": output, "code": code})
        else:
            output = await asyncio.to_thread(_exec_code, code)
            return format_success({"output": output, "code": code})
    except Exception as e:
        return format_error(str(e))


class RunPythonInput(BaseModel):
    code: str = Field(default="", description="要执行的 Python 代码，支持多行")


@confirm_execution(
    question="即将执行以下 Python 代码，是否确认执行？",
    approve_text="执行",
    reject_text="取消",
    reject_message="用户拒绝执行代码",
)
class RunPythonTool(ToolBase):
    name: str = "run_python"
    description: str = (
        "在隔离环境中执行 Python 代码，返回 stdout 输出。"
        "用于计算、数据处理、文本转换。[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = RunPythonInput

    def _run(self, code: str = "") -> str:
        raise NotImplementedError("run_python 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        code: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """（用户确认放行后）LangChain 异步入口：校验并执行。

        本方法经类装饰器 confirm_execution 包装：确认门控在方法体之外先执行，
        auto_approve 或用户 approve 之后才进入本方法体。

        ``run_manager`` 在此取出 run_id（流式推送与中途停止需要）。confirm
        会把 run_manager 等**技术参数**从确认气泡载荷中剔除、批准后仍原样透传
        进本方法；LangChain 仅在 ``_arun`` 签名声明 run_manager 时才注入，其
        run_id 与 WebSocket 回调 ``on_tool_start`` 收到的 run_id 一致，用作
        ``tool_stream`` 的 call_id（前端据此精确匹配气泡）与中断注册表键。
        """
        if not code:
            return format_error("code 不能为空")
        run_id = str(run_manager.run_id) if run_manager and run_manager.run_id else ""
        # 有 run_id 时经 ToolSender 实时流式推送；无 run_id（未声明 run_manager
        # 或直接调用未传）时退化为进程内一次性捕获。
        sender = ToolSender.from_context() if run_id else None
        return await _run_code(code, run_id, sender)
