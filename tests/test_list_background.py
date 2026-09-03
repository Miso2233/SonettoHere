"""测试 list_background 工具（tools/task/tool_list.py）。

覆盖列表内容、空注册表，以及提取器对列表信封的结构化输出。
"""

import json
import time

import pytest

from api.agent import background as bg
from api.agent import interaction
from tools.task.tool_list import ListBackgroundTool


def _setup_session() -> str:
    sid = f"bglist-test-{time.time_ns()}"
    interaction.current_session_id.set(sid)
    return sid


def _spawn(registry: bg.BackgroundTaskRegistry, delay: float, value: str) -> int:
    async def slow() -> str:
        import asyncio

        await asyncio.sleep(delay)
        return value

    return registry.register(slow(), tool_name="probe", args_summary='{"q": 1}').index


@pytest.mark.asyncio
async def test_lists_all_tasks_with_status() -> None:
    """列出全部任务：索引、工具名、状态、耗时；running 计数正确。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        first = _spawn(registry, 0, "done-1")
        _spawn(registry, 30, "never")  # 不会在测试内完成
        await registry.await_result(first, 5)

        result = await ListBackgroundTool().arun({})
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["count"] == 2
        assert parsed["data"]["running"] == 1
        statuses = {t["status"] for t in parsed["data"]["tasks"]}
        assert statuses == {"completed", "running"}
        assert parsed["data"]["tasks"][0]["tool_name"] == "probe"
        assert parsed["data"]["tasks"][0]["index"] == first
        assert parsed["data"]["tasks"][0]["args_summary"]
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_empty_registry_returns_empty_list() -> None:
    """从未 spawn 过：成功返回空列表（非错误，查看本身是合法操作）。"""
    interaction.current_session_id.set("")
    result = await ListBackgroundTool().arun({})
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["data"] == {"tasks": [], "count": 0, "running": 0}


def test_extractor_shapes_list_envelope() -> None:
    """提取器把列表信封转为 tool_type=background_list + tasks。"""
    from api.callbacks.tool_extractors import _dispatch

    parsed = {
        "success": True,
        "data": {
            "tasks": [
                {"index": 1, "tool_name": "tavily_search", "status": "running",
                 "elapsed_s": 1.2, "args_summary": "{}"},
            ],
            "count": 1,
            "running": 1,
        },
    }
    out = _dispatch("list_background", parsed)
    assert out == {
        "tool_type": "background_list",
        "total": 1,
        "running": 1,
        "tasks": parsed["data"]["tasks"],
    }
