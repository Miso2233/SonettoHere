"""computer use 系列：共享能力纯函数 + 两个工具流程的单测。

不在测试中真截屏 / 真移动鼠标 —— 屏幕相关入口一律 monkeypatch；
computer_virtual_click 是「虚拟点击」，须保证全程不触碰真实鼠标/系统点击。
"""

import base64
import io
import json

import pytest
from langchain_core.messages import ToolMessage
from PIL import Image

from tools.computer import _screen as screen
from tools.computer.tool_click import ClickTool
from tools.computer.tool_screenshot import ScreenshotTool
from tools.computer.tool_type import TypeTool
from tools.computer.tool_virtual_click import VirtualClickTool

# ── 共享能力：纯函数 ─────────────────────────────────────────


def test_canvas_to_screen_scaling_and_clamp() -> None:
    assert screen.canvas_to_screen(0, 0, 2560, 1600) == (0, 0)
    assert screen.canvas_to_screen(960, 540, 2560, 1600) == (1280, 800)
    assert screen.canvas_to_screen(1920, 1080, 2560, 1600) == (2559, 1599)
    # 与真实屏幕同尺寸时映射保持恒等
    assert screen.canvas_to_screen(100, 200, 1920, 1080) == (100, 200)


def test_canvas_to_screen_scales_in_both_axes() -> None:
    # 2560x1600 为 16:10：横纵缩放比不同也需各自线性正确
    nx, ny = screen.canvas_to_screen(1920, 540, 2560, 1600)
    assert nx == 2559
    assert ny == 800


def test_to_canvas_image_fixed_canvas_size() -> None:
    img = Image.new("RGB", (2560, 1600), "white")
    canvas = screen.to_canvas_image(img)
    assert canvas.size == (screen.CANVAS_WIDTH, screen.CANVAS_HEIGHT)


def test_draw_click_marker_paints_center_pixel() -> None:
    img = Image.new("RGB", (screen.CANVAS_WIDTH, screen.CANVAS_HEIGHT), "white")
    cx, cy = 100, 80
    screen.draw_click_marker(img, cx, cy)
    assert img.getpixel((cx, cy)) == screen.MARKER_COLOR
    assert img.getpixel((cx + screen.CANVAS_WIDTH // 2, cy)) == (255, 255, 255)


def test_image_to_data_url() -> None:
    img = Image.new("RGB", (8, 8), "white")
    data_url, png_bytes = screen.image_to_data_url(img)
    assert data_url.startswith("data:image/png;base64,")
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_new_filename_unique() -> None:
    names = {screen.new_filename("computer_click") for _ in range(100)}
    assert len(names) == 100
    assert all(n.startswith("computer_click_") and n.endswith(".png") for n in names)


def test_save_tmp_image_writes_file(tmp_path) -> None:
    img = Image.new("RGB", (32, 32), "white")
    screen._TMP_ROOT = tmp_path  # type: ignore[attr-defined]
    saved = screen.save_tmp_image(img, "computer_click_x.png")
    assert saved == (tmp_path / "computer_click_x.png").resolve()
    assert saved.exists()


# ── ScreenshotTool ──────────────────────────────────────────


def _command_tool_message(command) -> ToolMessage:
    for msg in (command.update or {}).get("messages", []):
        if isinstance(msg, ToolMessage):
            return msg
    raise AssertionError("Command 中缺少 ToolMessage")


def test_screenshot_tool_flows_image_to_model(monkeypatch) -> None:
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))

    command = ScreenshotTool()._run_impl("call-1")

    tool_msg = _command_tool_message(command)
    data = json.loads(tool_msg.content)
    assert data["success"] is True
    assert data["data"]["action"] == "screenshot"
    assert data["data"]["screen_size"] == {"width": 2560, "height": 1600}

    human = (command.update or {})["messages"][1]
    image_block = human.content[1]
    assert image_block["type"] == "image_url"
    assert image_block["image_url"]["url"].startswith("data:image/png;base64,")


def test_screenshot_tool_returns_error_when_capture_fails(monkeypatch) -> None:
    def boom():
        raise screen.ScreenError("全屏截图失败：no display")

    monkeypatch.setattr(screen, "capture_screen", boom)

    command = ScreenshotTool()._run_impl("call-1")
    tool_msg = _command_tool_message(command)
    parsed = json.loads(tool_msg.content)
    assert parsed["success"] is False
    assert "no display" in parsed["error"]


# ── VirtualClickTool（虚拟点击，不得有任何真实动作）───────────


def _forbid_pyautogui(*_args, **_kwargs):
    raise AssertionError("虚拟点击不应触碰 pyautogui（不得移动鼠标 / 触发系统点击）")


def test_virtual_click_annotates_without_physical_action(monkeypatch, tmp_path) -> None:
    # 虚拟点击不得触碰任何物理动作：pyautogui 与真实点击原语调用即失败
    monkeypatch.setattr(screen, "_pyautogui", _forbid_pyautogui)
    monkeypatch.setattr(screen, "real_click_at", _forbid_pyautogui)
    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(
        screen, "new_filename", lambda _p: "computer_virtual_click_ts.png"
    )
    saved = (tmp_path / "computer_virtual_click_ts.png").resolve()
    monkeypatch.setattr(screen, "save_tmp_image", lambda _img, _fn: saved)

    command = VirtualClickTool()._run_impl(x=960, y=800, tool_call_id="call-2")

    tool_msg = _command_tool_message(command)
    data = json.loads(tool_msg.content)
    assert data["success"] is True
    assert data["data"]["action"] == "virtual_click"
    assert data["data"]["click_canvas"] == {"x": 960, "y": 800}
    # click_screen 仅是映射回显，供后续真实执行参考，本身不触发任何动作
    assert data["data"]["click_screen"] == {"x": 1280, "y": 1185}
    assert data["data"]["saved_file"] == str(saved)
    assert "未执行任何真实鼠标操作" in data["data"]["message"]

    # 注入画面为 PNG data_url，画布层已画好标记（标记像素由
    # test_draw_click_marker_paints_center_pixel 单独覆盖）
    human = (command.update or {})["messages"][1]
    image_block = human.content[1]
    assert image_block["image_url"]["url"].startswith("data:image/png;base64,")


def test_virtual_click_rejects_out_of_canvas(monkeypatch) -> None:
    monkeypatch.setattr(screen, "_pyautogui", _forbid_pyautogui)
    monkeypatch.setattr(screen, "real_click_at", _forbid_pyautogui)

    command = VirtualClickTool()._run_impl(x=5000, y=10, tool_call_id="call-3")
    tool_msg = _command_tool_message(command)
    parsed = json.loads(tool_msg.content)
    assert parsed["success"] is False
    assert "越界" in parsed["error"]


# ── ClickTool（真实点击：会真正调用 real_click_at）────────


def test_real_click_performs_click_and_returns_plain_screenshot(
    monkeypatch, tmp_path
) -> None:
    clicks: list[tuple[int, int]] = []

    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))
    monkeypatch.setattr(
        screen, "real_click_at", lambda x, y: clicks.append((x, y)) or None
    )
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(
        screen, "new_filename", lambda _p: "computer_click_ts.png"
    )
    saved = (tmp_path / "computer_click_ts.png").resolve()
    monkeypatch.setattr(screen, "save_tmp_image", lambda _img, _fn: saved)

    command = ClickTool()._run_impl(x=960, y=800, tool_call_id="call-4")

    # 真实点击确实落到了映射后的真实像素
    assert clicks == [(1280, 1185)]

    tool_msg = _command_tool_message(command)
    data = json.loads(tool_msg.content)
    assert data["success"] is True
    assert data["data"]["action"] == "real_click"
    assert data["data"]["click_canvas"] == {"x": 960, "y": 800}
    assert data["data"]["click_screen"] == {"x": 1280, "y": 1185}
    assert data["data"]["saved_file"] == str(saved)

    human = (command.update or {})["messages"][1]
    image_block = human.content[1]
    data_url = image_block["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")

    # 真实点击画面为**未标注**的 1920x1080 原图：点击点颜色未被标记覆盖
    raw = base64.b64decode(data_url.split(",", 1)[1])
    decoded = Image.open(io.BytesIO(raw)).convert("RGB")
    assert decoded.size == (screen.CANVAS_WIDTH, screen.CANVAS_HEIGHT)
    assert decoded.getpixel((960, 800)) == (255, 255, 255)


def test_virtual_and_real_click_share_return_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))
    monkeypatch.setattr(screen, "real_click_at", lambda _x, _y: None)
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(screen, "new_filename", lambda p: f"{p}.png")
    monkeypatch.setattr(screen, "save_tmp_image", lambda _img, fn: tmp_path / fn)

    virt_data = json.loads(
        _command_tool_message(
            VirtualClickTool()._run_impl(x=10, y=10, tool_call_id="a")
        ).content
    )["data"]
    real_data = json.loads(
        _command_tool_message(
            ClickTool()._run_impl(x=10, y=10, tool_call_id="b")
        ).content
    )["data"]

    # 返回值结构完全一致（action / message 值不同，字段集合相同）
    assert set(real_data) == set(virt_data)
    assert real_data["action"] == "real_click"
    assert virt_data["action"] == "virtual_click"


# ── type_text / TypeTool（键盘输入，真实按键逐字符）───────────


class _FakeKeyboard:
    """记录逐字符 write 与特殊键 press 的假 pyautogui 键盘对象。"""

    def __init__(self) -> None:
        self.writes: list[str] = []
        self.presses: list[str] = []

    def write(self, char: str, interval: float = 0.0) -> None:
        self.writes.append(char)

    def press(self, key: str) -> None:
        self.presses.append(key)


def test_type_text_char_by_char_with_special_keys(monkeypatch) -> None:
    fake = _FakeKeyboard()
    monkeypatch.setattr(screen, "_pyautogui", lambda: fake)

    screen.type_text("Hi\n\t!")

    # ASCII 逐字符 write；换行/回车→enter、Tab→tab
    assert fake.writes == ["H", "i", "!"]
    assert fake.presses == ["enter", "tab"]


def test_type_text_rejects_non_ascii(monkeypatch) -> None:
    monkeypatch.setattr(screen, "_pyautogui", lambda: object())

    with pytest.raises(screen.ScreenError, match="不支持字符"):
        screen.type_text("中文 hello")


def test_type_tool_types_text_then_returns_plain_screenshot(
    monkeypatch, tmp_path
) -> None:
    typed: list[str] = []

    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))
    monkeypatch.setattr(screen, "type_text", lambda text: typed.append(text))
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(screen, "new_filename", lambda _p: "computer_type_ts.png")
    saved = (tmp_path / "computer_type_ts.png").resolve()
    monkeypatch.setattr(screen, "save_tmp_image", lambda _img, _fn: saved)

    command = TypeTool()._run_impl(text="hello", tool_call_id="call-5")
    assert typed == ["hello"]

    tool_msg = _command_tool_message(command)
    data = json.loads(tool_msg.content)
    assert data["success"] is True
    assert data["data"]["action"] == "type"
    assert data["data"]["text"] == "hello"
    assert data["data"]["char_count"] == 5
    assert data["data"]["saved_file"] == str(saved)

    human = (command.update or {})["messages"][1]
    image_block = human.content[1]
    data_url = image_block["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")

    # 输入后回传**未标注**原图：中心点未被标记覆盖
    raw = base64.b64decode(data_url.split(",", 1)[1])
    decoded = Image.open(io.BytesIO(raw)).convert("RGB")
    assert decoded.size == (screen.CANVAS_WIDTH, screen.CANVAS_HEIGHT)
    assert decoded.getpixel((960, 800)) == (255, 255, 255)


def test_type_tool_rejects_empty_text() -> None:
    command = TypeTool()._run_impl(text="", tool_call_id="call-6")
    tool_msg = _command_tool_message(command)
    parsed = json.loads(tool_msg.content)
    assert parsed["success"] is False
    assert "不能为空" in parsed["error"]
