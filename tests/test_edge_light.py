"""测试边缘灯控制器状态汇聚（不启动 GUI 子进程）。

仅验证 EdgeLightController 把「会话开关 + 思考/流式活动」汇聚为
off / steady / blink 的幂等逻辑；覆盖层子进程真实启动留待手工冒烟。
"""

import json
from types import SimpleNamespace

from api.edge_light import EdgeLightController


class _FakeStdin:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, s: str) -> None:
        self.lines.append(s)

    def flush(self) -> None:
        pass


class _NoSpawnController(EdgeLightController):
    """已"启用"的替身控制器：不启动子进程，_spawn 恒真，写入进假 stdin。"""

    def __init__(self, fake_in: _FakeStdin) -> None:
        super().__init__()
        self._enabled = True
        self._current = None
        self._proc = SimpleNamespace(stdin=fake_in)

    def _spawn(self) -> bool:
        return True


def _controller() -> tuple[_NoSpawnController, _FakeStdin]:
    fake_in = _FakeStdin()
    return _NoSpawnController(fake_in), fake_in


def _states(lines: list[str]) -> list[str]:
    return [json.loads(line)["state"] for line in lines]


def test_off_until_session_enabled() -> None:
    c, fake = _controller()
    c.session_activity("s1", True)  # 未开启会话，活动被忽略 → 无任何写入
    assert fake.lines == []

    c.session_on("s1", True)  # 开启 → steady（常亮）
    assert _states(fake.lines) == ["steady"]


def test_steady_blink_transitions() -> None:
    c, fake = _controller()
    c.session_on("s1", True)
    c.session_activity("s1", True)  # 思考/流式 → blink
    c.session_activity("s1", False)  # 结束 → 回到 steady
    c.session_on("s1", False)  # 关闭 → off
    assert _states(fake.lines) == ["steady", "blink", "steady", "off"]


def test_activity_only_counts_for_enabled_session() -> None:
    c, fake = _controller()
    c.session_on("s1", True)
    assert _states(fake.lines) == ["steady"]
    c.session_activity("other", True)  # 非开启会话 → 不闪烁
    assert len(fake.lines) == 1
    c.session_activity("s1", True)
    assert _states(fake.lines) == ["steady", "blink"]


def test_multiple_sessions_or_any_blink() -> None:
    c, fake = _controller()
    c.session_on("s1", True)
    c.session_on("s2", True)  # 任一开启 → steady
    assert _states(fake.lines) == ["steady"]
    c.session_activity("s2", True)  # 任一在流式 → blink
    assert _states(fake.lines) == ["steady", "blink"]
    c.session_on("s1", False)  # 仍剩 s2 开启 → 保持 blink
    assert _states(fake.lines) == ["steady", "blink"]


def test_idempotent_no_duplicate_write() -> None:
    c, fake = _controller()
    c.session_on("s1", True)
    c.session_on("s1", True)  # 状态未变 → 不重复写入
    c.session_activity("s1", True)
    c.session_activity("s1", True)
    assert _states(fake.lines) == ["steady", "blink"]
