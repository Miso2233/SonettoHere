"""Computer-use 底层能力：屏幕捕获、逻辑画布映射、图像标注与按键原语。

与 read_image 同思路 —— 把"当前屏幕"以 base64 图片流注入 LLM 上下文；截图按需
即时生成，**不落盘保存**（调试期结束，不再产生截图文件）。

能力分两类：
- 无副作用：截屏、画布坐标映射、画标注、PNG 编码；
- 真实系统动作：``real_click_at``（物理点击）、``type_text``（剪贴板粘贴输入）、
  ``press_keys``（按键/快捷键）—— 仅供对应的真实操作工具调用；
  纯截屏 / 虚拟点击等零副作用路径绝不触碰它们。

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
import sys
import time
from typing import Any

from PIL import Image, ImageDraw

# 逻辑画布：交给 LLM 的统一坐标空间
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080

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


def real_click_at(
    x: int, y: int, button: str = "left", clicks: int = 1
) -> None:
    """在真实屏幕像素 (x, y) 处执行一次真实点击（移动光标并按下）。

    *button*: left / middle / right；*clicks*: 1 单击、2 双击、3 三击。
    仅供独立的「真实点击」工具（``computer_click``）调用；虚拟点击
    （``computer_virtual_click``）绝不调用本函数，以保持其零副作用语义。
    """
    pg = _pyautogui()
    try:
        pg.moveTo(x, y, duration=0.15)
        pg.click(clicks=clicks, interval=0.1, button=button)
    except Exception as exc:
        raise ScreenError(f"真实点击 ({x}, {y}) 失败：{exc}") from exc


def _clipboard_get_text() -> str | None:
    """读取系统剪贴板文本；读不到（剪贴板为空 / 非文本 / 异常）返回 None。"""
    try:
        import pyperclip
    except Exception as exc:  # pragma: no cover - 依赖缺失时才会走到
        raise ScreenError(
            "剪贴板依赖 pyperclip 不可用，无法粘贴输入。请安装：pip install pyperclip"
        ) from exc
    try:
        return pyperclip.paste()
    except Exception:  # noqa: BLE001 - 读取剪贴板是尽力而为：失败即视为无旧内容
        return None


def _clipboard_set_text(text: str) -> None:
    """把 *text* 写入系统剪贴板。"""
    try:
        import pyperclip
    except Exception as exc:  # pragma: no cover - 依赖缺失时才会走到
        raise ScreenError(
            "剪贴板依赖 pyperclip 不可用，无法粘贴输入。请安装：pip install pyperclip"
        ) from exc
    try:
        pyperclip.copy(text)
    except Exception as exc:
        raise ScreenError(f"写入剪贴板失败：{exc}") from exc


def _paste_via_clipboard(text: str) -> None:
    """统一剪贴板输入：写入剪贴板 → Ctrl/Cmd+V 粘贴 → 尽力还原原剪贴板。

    整段文本（含中文等任意字符）一律经剪贴板粘贴，内容按字面写入：`\\n`/`\\r`
    会作为字面换行/回车粘入，不触发独立的回车键。
    """
    previous = _clipboard_get_text()
    _clipboard_set_text(text)
    try:
        pg = _pyautogui()
        modifier = "command" if sys.platform == "darwin" else "ctrl"
        pg.hotkey(modifier, "v")
        # 留出时间让目标应用消费粘贴内容后再还原剪贴板，避免其读到被还原的旧值
        time.sleep(0.3)
    finally:
        if previous is not None:
            _clipboard_set_text(previous)


def type_text(text: str) -> None:
    """把 *text* 整段经剪贴板粘贴到当前聚焦控件（支持任意文本含中文）。"""
    _paste_via_clipboard(text)


# 键名别名：统一常见大小写/叫法到 pyautogui 的键名（不含平台相关的 meta 键，
# 后者在 _parse_combo 内按平台再归一）
_KEY_ALIASES: dict[str, str] = {
    "control": "ctrl",
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "break": "pause",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
}


def _parse_combo(combo: str, valid_keys: frozenset[str]) -> list[str]:
    """把 "Return" / "ctrl+s" / "alt+Tab" 拆成 pyautogui 可识别的键序。"""
    keys: list[str] = []
    for raw in combo.split("+"):
        token = raw.strip().lower()
        if not token:
            raise ScreenError(f"按键表达式 {combo!r} 含空的片段（+ 两侧都要有键名）")
        token = _KEY_ALIASES.get(token, token)
        if token in {"cmd", "command", "super", "meta"}:
            # 平台修饰键：mac 用 Command，其余（Win/Linux）用 Win
            token = "command" if sys.platform == "darwin" else "win"
        if token not in valid_keys:
            raise ScreenError(
                f"不支持的键名 {raw!r}（位于 {combo!r}）。支持单个键名（如 Return/"
                "Esc/F5/Space）或 + 连接的快捷键（如 ctrl+s、alt+Tab、"
                "ctrl+shift+esc）"
            )
        keys.append(token)
    return keys


def press_keys(combo: str) -> None:
    """对当前聚焦窗口执行一次真实按键/快捷键。

    *combo* 形如：
      - 单个键名："Return"、"Esc"、"F5"、"Space"；
      - 组合快捷键：用 ``+`` 连接，如 "ctrl+s"、"alt+Tab"、"ctrl+shift+esc"。
    按键顺序/释放顺序由 pyautogui.hotkey 保证（先按下各键、再逐个释放）。
    """
    pg = _pyautogui()
    try:
        keys = _parse_combo(combo, frozenset(pg.KEYBOARD_KEYS))
        pg.hotkey(*keys)
    except ScreenError:
        raise
    except Exception as exc:
        raise ScreenError(f"按键 {combo!r} 失败：{exc}") from exc


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