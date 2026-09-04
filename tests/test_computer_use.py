"""computer use 系列：共享能力纯函数 + 两个工具流程的单测。

不在测试中真截屏 / 真移动鼠标 —— 屏幕相关入口一律 monkeypatch；
computer_click 是「虚拟点击」，须保证全程不触碰真实鼠标/系统点击。
"""

import json

from langchain_core.messages import ToolMessage
from PIL import Image

from tools.computer import _screen as screen
from tools.computer.tool_click import ComputerClickTool
from tools.computer.tool_screenshot import ScreenshotTool

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


# ── ComputerClickTool（虚拟点击，不得有任何真实动作）───────────


def _forbid_pyautogui(*_args, **_kwargs):
    raise AssertionError("虚拟点击不应触碰 pyautogui（不得移动鼠标 / 触发系统点击）")


def test_virtual_click_annotates_without_physical_action(monkeypatch, tmp_path) -> None:
    # 只要工具内部走任何 pyautogui 路径（截图/点击皆同源），此断言立即失败
    monkeypatch.setattr(screen, "_pyautogui", _forbid_pyautogui)
    monkeypatch.setattr(screen, "logical_screen_size", lambda: (2560, 1600))
    monkeypatch.setattr(
        screen, "capture_screen", lambda: Image.new("RGB", (2560, 1600), "white")
    )
    monkeypatch.setattr(screen, "new_filename", lambda _p: "computer_click_ts.png")
    saved = (tmp_path / "computer_click_ts.png").resolve()
    monkeypatch.setattr(screen, "save_tmp_image", lambda _img, _fn: saved)

    command = ComputerClickTool()._run_impl(x=960, y=800, tool_call_id="call-2")

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

    command = ComputerClickTool()._run_impl(x=5000, y=10, tool_call_id="call-3")
    tool_msg = _command_tool_message(command)
    parsed = json.loads(tool_msg.content)
    assert parsed["success"] is False
    assert "越界" in parsed["error"]
