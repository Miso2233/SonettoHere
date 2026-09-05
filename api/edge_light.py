"""Computer Use 屏幕边缘灯控制器 — 管理原生 PySide6 覆盖层子进程。

职责：
- 把「各会话的 Computer Use 开关 + 模型思考/流式活动」汇聚成单一状态
  ``off | steady | blink`` 写入覆盖层子进程 stdin；
- 惰性启动子进程；PySide6 缺失或启动失败时自动禁用，不影响主服务（退化为无提示）；
- 主服务关闭时随进程退出（stdin EOF 后覆盖层自动结束），并显式 terminate 兜底。

覆盖层不拦截任何输入（点击穿透），状态语义见 ``edge_light/overlay.py``。
"""

import json
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

from api.utils.logger import get_logger

_log = get_logger("edge_light")

# 覆盖层子进程脚本：edge_light/overlay.py（相对本文件两层的仓库根）
_OVERLAY_SCRIPT = Path(__file__).resolve().parent.parent / "edge_light" / "overlay.py"


class EdgeLightController:
    """汇聚并驱动边缘灯覆盖层。每个方法幂等；调用方无需关心子进程生命周期。"""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._current: str | None = None   # 已写出的状态
        self._enabled: bool | None = None  # None=尚未尝试 / True / False
        self._sessions: set[str] = set()   # 已开启 Computer Use 的会话
        self._streaming: set[str] = set()  # 正在思考/流式输出的会话

    # ── 对外状态入口 ──────────────────────────────────────
    def session_on(self, session_id: str, enabled: bool) -> None:
        """会话 Computer Use 开关：True → 常亮基准；False → 关闭该会话贡献。"""
        (self._sessions.add(session_id) if enabled else self._sessions.discard(session_id))
        self._streaming.discard(session_id)
        self._recompute()

    def session_activity(self, session_id: str, active: bool) -> None:
        """模型思考/流式活动：仅当该会话已开启 Computer Use 时生效（闪烁）。"""
        if session_id not in self._sessions:
            self._streaming.discard(session_id)
            return
        (self._streaming.add(session_id) if active else self._streaming.discard(session_id))
        self._recompute()

    def _recompute(self) -> None:
        """聚合：任一开启的会话在流式 → blink；有会话开启 → steady；否则 off。"""
        if not self._sessions:
            state = "off"
        elif self._sessions & self._streaming:
            state = "blink"
        else:
            state = "steady"
        self._write(state)

    # ── 子进程管理 ────────────────────────────────────────
    def _write(self, state: str) -> None:
        if self._enabled is False:
            return
        if not self._spawn():
            return
        if state == self._current:
            return
        try:
            assert self._proc is not None and self._proc.stdin is not None
            self._proc.stdin.write(json.dumps({"state": state}) + "\n")
            self._proc.stdin.flush()
            self._current = state
        except (BrokenPipeError, OSError):
            _log.warning("边缘灯子进程写入失败，已禁用")
            self._proc = None
            self._enabled = False

    def _spawn(self) -> bool:
        if self._enabled is True:
            return self._proc is not None and self._proc.poll() is None
        if self._enabled is False:
            return False
        # 首次使用才尝试启动：PySide6 缺失或脚本不可运行 → 禁用
        if find_spec("PySide6") is None or not _OVERLAY_SCRIPT.exists():
            _log.warning("PySide6 不可用，边缘灯覆盖层已禁用（Computer Use 将无光效提示）")
            self._enabled = False
            return False
        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(_OVERLAY_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            self._enabled = True
            self._current = None  # 强制重发当前状态
            _log.info("边缘灯覆盖层子进程已启动 (pid=%s)", self._proc.pid)
            return True
        except (OSError, ValueError) as e:
            _log.warning("边缘灯覆盖层启动失败，已禁用: %s", e)
            self._proc = None
            self._enabled = False
            return False

    def shutdown(self) -> None:
        """关闭：通知退出并回收子进程（幂等，服务停止时调用）。"""
        proc = self._proc
        self._proc = None
        self._enabled = False
        self._sessions.clear()
        self._streaming.clear()
        if proc is None or proc.poll() is not None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.write(json.dumps({"quit": True}) + "\n")
                proc.stdin.flush()
                proc.stdin.close()
            proc.wait(timeout=3)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


# ── 进程内单例访问（供 create_app 装配与回调无 app 引用的场景）─────────

_active: EdgeLightController | None = None


def set_active_controller(controller: EdgeLightController | None) -> None:
    """由 FastAPI 生命周期装配时注册；为 None 则停用。"""
    global _active
    _active = controller


def edge_light_session_on(session_id: str, enabled: bool) -> None:
    """便捷入口：通知控制器某会话 Computer Use 开关变化（无控制器时 no-op）。"""
    if _active is not None:
        _active.session_on(session_id, enabled)


def edge_light_activity(session_id: str, active: bool) -> None:
    """便捷入口：通知控制器某会话模型思考/流式活动（无控制器时 no-op）。"""
    if _active is not None:
        _active.session_activity(session_id, active)
