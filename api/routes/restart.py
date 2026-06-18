"""REST API — 重启后端进程。"""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MAIN_PY = _PROJECT_ROOT / "main.py"


@router.post("/restart")
async def restart_server():
    """重启后端进程。

    启动一个新后端进程后退出当前进程。
    前端检测到服务恢复后应自动刷新页面。
    """
    subprocess.Popen(
        [sys.executable, str(_MAIN_PY)],
        cwd=str(_PROJECT_ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )
    os._exit(0)
