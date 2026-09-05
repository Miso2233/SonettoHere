"""屏幕边缘灯覆盖层 — PySide6 子进程入口。

由后端 :mod:`api.edge_light` 以子进程方式启动，通过 **stdin 读取 JSON 行指令**：

    {"state": "off"}      关闭（不显示）
    {"state": "steady"}   白灯静止常亮
    {"state": "blink"}    白灯呼吸闪烁
    {"quit": true}        退出进程

视觉实现要点：
- 全屏、无边框、置顶、**点击穿透**（WindowTransparentForInput），不拦截用户任何操作；
- 辉光环只预渲染一次到离屏 QPixmap（沿屏幕边界多层层叠描边，向内柔化、四角无缝），
  常亮/闪烁通过 ``setWindowOpacity`` 以很低代价调节整体亮度——闪烁无需逐帧重绘；
- stdin 在后台线程读取，EOF 视为退出信号，父进程消亡时本进程自动结束。

本文件为独立入口，只依赖标准库与 PySide6，禁止 import 后端模块。
"""

import json
import math
import sys
import threading
from collections import deque

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

# 状态亮度
STEADY_BRIGHTNESS = 0.5        # 静止常亮
BLINK_MIN = 0.10               # 闪烁谷底
BLINK_MAX = 0.90               # 闪烁峰值
TIMER_MS = 50                  # 亮度刷新周期

# 白灯辉光（沿屏幕边缘柔化）
_BASE_ALPHA = 220              # 贴边最亮层的像素 alpha
_GLOW_WIDTH = 34               # 向内柔化的总宽度（px）
_LAYERS = 40                   # 描边层数，越多过渡越平滑


def _brightness_for(state: str, phase: int) -> float:
    """把状态映射为窗口整体亮度（0.0 ~ 1.0）。"""
    if state == "steady":
        return STEADY_BRIGHTNESS
    if state == "blink":
        pulse = (math.sin(math.radians(phase)) + 1) / 2  # 0.0 ~ 1.0
        return BLINK_MIN + (BLINK_MAX - BLINK_MIN) * pulse
    return 0.0


class BorderGlow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._state = "off"
        self._phase = 0
        self._glow: QPixmap | None = None
        self._cmds: deque[dict] = deque()
        self.setVisible(False)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TIMER_MS)

        threading.Thread(target=self._read_stdin, daemon=True).start()
        self.showFullScreen()

    # ── 指令入口：后台线程读取 stdin ────────────────────────
    def _read_stdin(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                self._cmds.append(json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
        self._cmds.append({"quit": True})  # stdin EOF → 父进程退出，跟随结束

    def _drain_cmds(self) -> None:
        while self._cmds:
            cmd = self._cmds.popleft()
            if cmd.get("quit"):
                QApplication.instance().quit()
                return
            state = cmd.get("state")
            if state in ("off", "steady", "blink"):
                self._state = state
                self._phase = 0
                if state == "off":
                    self.setVisible(False)
                elif not self.isVisible():
                    self.showFullScreen()
        # blink 推进相位
        if self._state == "blink":
            self._phase = (self._phase + 4) % 360

    def _tick(self) -> None:
        self._drain_cmds()
        if self._state == "off":
            return
        # 常亮/闪烁都只改整体不透明度，GPU 合成，不触发像素级重绘
        self.setWindowOpacity(_brightness_for(self._state, self._phase))

    # ── 辉光环：仅首次/尺寸变化时渲染一次 ──────────────────
    def _render_glow(self) -> None:
        pm = QPixmap(self.size())
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(0xFF, 0xFF, 0xFF, _BASE_ALPHA)

        # 屏幕边界矩形路径（绘制中心线正好压在边缘上，外半侧被裁剪、只向内柔化）
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))

        for i in range(1, _LAYERS + 1):
            t = i / _LAYERS                                  # 0 贴边 -> 1 最内侧
            stroke_width = 2.0 * _GLOW_WIDTH * t
            alpha = int(_BASE_ALPHA * (1.0 - t) ** 2)        # 越靠内圈越亮
            pen = QPen(QColor(color.red(), color.green(), color.blue(), alpha), stroke_width)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        painter.end()
        self._glow = pm
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._render_glow()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        if self._glow is not None and self._state != "off":
            painter.drawPixmap(0, 0, self._glow)


def main() -> None:
    app = QApplication(sys.argv)
    # 捕获顶层异常，避免异常弹窗卡死子进程；异常即退出（父进程会捕获进程结束）
    sys.excepthook = lambda *_a: QApplication.instance().quit()  # type: ignore[assignment]
    # 必须持有 Python 引用（挂在 QApplication 上贯穿事件循环），
    # 否则无父的 QWidget 包装对象被 GC 后 QTimer/窗口随之销毁
    app._overlay_window = BorderGlow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
