"""run_python 子进程执行器 — 被 tool_python 以独立子进程方式拉起。

从 stdin 读取待执行代码，以安全 builtins 执行并实时输出到 stdout/stderr。
作为普通脚本运行（``python -u <此文件>``），不参与任何包导出。

异常约定：
- ``SystemExit`` 透传退出码；
- 其他异常打印 ``__RUN_PYTHON_ERROR__::<Type>: <msg>`` 标记后以退出码 1
  结束，父进程据此解析出结构化错误消息。
"""

import sys


def _main() -> None:
    # 延迟导入：仅子进程运行此脚本时才加载 tools.base，避免拖慢父进程导入
    from tools.base import get_safe_builtins

    # 关闭 Windows 上 text 模式的 \n→\r\n 翻译，使管道输出与进程内
    # io.StringIO 捕获保持一致（同段代码两种路径产出完全相同的文本）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(newline="\n")
        except (ValueError, OSError):
            pass  # 非常规流对象（如已关闭）时保持原样

    code = sys.stdin.read()
    if not code:
        sys.exit(0)

    safe = get_safe_builtins()
    try:
        exec(compile(code, "<run_python>", "exec"), {"__builtins__": safe})
    except SystemExit as e:
        code_value = e.code if isinstance(e.code, int) else 1
        sys.exit(code_value)
    except BaseException as e:  # noqa: BLE001 — 交给父进程解析为错误结果
        sys.stderr.write(f"__RUN_PYTHON_ERROR__::{type(e).__name__}: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    _main()
