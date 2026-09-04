"""Computer-use 底层能力：屏幕捕获、逻辑画布映射、标注与临时落盘。

与 read_image 同思路 —— 把"当前屏幕"以 base64 图片流注入 LLM 上下文；
区别仅是图片来源从本地文件换成实时截屏。截屏 / 画布坐标映射 / 画标注 / 落盘
均为无副作用能力；唯一会产生真实系统动作的是 ``real_click_at``（移动光标并
点击），它**仅供**独立的「真实点击」工具（``computer_click``）调用 ——
纯截屏（``computer_screenshot``）与虚拟点击（``computer_virtual_click``，
仅标注坐标、不做真实操作）绝不触碰它。

坐标约定
--------
交给 LLM 的截图一律缩放为 1920x1080 的「逻辑画布」；LLM 只需基于该画布
输出整数坐标（x ∈ [0, 1920]，y ∈ [0, 1080]）。真实屏幕像素通过
``canvas_to_screen`` 做一次线性映射得到，因此画布是否等比拉伸不影响
标注落点与图片上模型所见像素的一致性（变换可逆）。
"""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

# 逻辑画布：交给 LLM 的统一坐标空间
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080

# 标注截图的落盘目录：工程根下的 .computer_use/（git 不跟踪，见 .gitignore）
_TMP_ROOT = Path(__file__).resolve().parents[2] / ".computer_use"

# 点击标注的准星颜色（RGB）
MARKER_COLOR = (237, 28, 36)


class ScreenError(RuntimeError):
    """屏幕操作失败（依赖缺失 / 捕获出错等），message 面向 LLM 展示。"""


def _pyautogui() -> Any:
    """惰性导入 pyautogui，缺失或平台不可用时抛出 ScreenError。

    整机注册工具时不应因本能力缺失而失败 —— pyautogui 只在真正操作屏幕时引入。
    """
    try:
        import pyautogui
    except Exception as exc:  # pragma: no cover - 依赖缺失时才会走到
        raise ScreenError(
            "屏幕控制依赖 pyautogui 不可用，无法执行屏幕捕获/读取尺寸。"
            "请先安装：pip install pyautogui"
        ) from exc
    return pyautogui


def capture_screen() -> Image.Image:
    """捕获当前屏幕（主显示器全屏），返回原始像素尺寸的 RGB 截图。

    截图像素与 pyautogui 报告的逻辑屏幕尺寸处于同一坐标系（进程级 DPI
    一致性），因此画布坐标可直接经 ``logical_screen_size`` 线性映射回真实像素。
    """
    pg = _pyautogui()
    try:
        img = pg.screenshot()
    except Exception as exc:
        raise ScreenError(f"全屏截图失败：{exc}") from exc
    return img.convert("RGB")


def logical_screen_size() -> tuple[int, int]:
    """返回真实屏幕（物理像素坐标空间）的宽高像素。"""
    pg = _pyautogui()
    try:
        width, height = pg.size()
    except Exception as exc:
        raise ScreenError(f"读取屏幕尺寸失败：{exc}") from exc
    return int(width), int(height)


def real_click_at(x: int, y: int) -> None:
    """在真实屏幕像素 (x, y) 处执行一次真实左键点击（移动光标并按下）。

    仅供独立的「真实点击」工具（``computer_click``）调用；虚拟点击
    （``computer_virtual_click``）绝不调用本函数，以保持其零副作用语义。
    """
    pg = _pyautogui()
    try:
        pg.moveTo(x, y, duration=0.15)
        pg.click()
    except Exception as exc:
        raise ScreenError(f"真实点击 ({x}, {y}) 失败：{exc}") from exc


def to_canvas_image(img: Image.Image) -> Image.Image:
    """把截图线性缩放到 1920x1080 逻辑画布 —— 像素即模型坐标空间。"""
    return img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.LANCZOS)


def canvas_to_screen(
    x: int, y: int, screen_w: int, screen_h: int
) -> tuple[int, int]:
    """把画布坐标 (x, y) 线性映射为真实屏幕像素，越界就近截断到有效区间。"""
    screen_w = max(1, int(screen_w))
    screen_h = max(1, int(screen_h))
    native_x = round(x * screen_w / CANVAS_WIDTH)
    native_y = round(y * screen_h / CANVAS_HEIGHT)
    native_x = min(max(native_x, 0), screen_w - 1)
    native_y = min(max(native_y, 0), screen_h - 1)
    return native_x, native_y


def image_to_data_url(img: Image.Image) -> tuple[str, bytes]:
    """把图片 PNG 编码为 data URL，返回 ``(data_url, png_bytes)``。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}", data


def draw_click_marker(img: Image.Image, cx: int, cy: int) -> Image.Image:
    """在画布坐标 (cx, cy) 叠加红色准星（外环 + 十字 + 中心点），原地修改后返回。"""
    draw = ImageDraw.Draw(img)
    radius = 18
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline=MARKER_COLOR,
        width=4,
    )
    arm = radius + 8
    draw.line((cx - arm, cy, cx + arm, cy), fill=MARKER_COLOR, width=2)
    draw.line((cx, cy - arm, cx, cy + arm), fill=MARKER_COLOR, width=2)
    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=MARKER_COLOR)
    return img


def new_filename(prefix: str) -> str:
    """生成形如 ``{prefix}_YYYYmmdd_HHMMSS_ffffff.png`` 的唯一文件名（本地时间）。"""
    stamp = datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{stamp}.png"


def save_tmp_image(img: Image.Image, filename: str) -> Path:
    """把标注截图写入工程内 git 不跟踪目录，返回绝对路径；目录不存在则创建。"""
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TMP_ROOT / filename
    img.save(path, format="PNG")
    return path.resolve()