"""memory/narrative.py 测试。"""

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import memory.narrative as narrative
from memory.memory_manager import MemoryManager
from memory.narrative import LongTermMemoryInterface


# ── 测试辅助 ──────────────────────────────────────────────────


def _fake_agent_factory(entries_setup=None):
    """构建 mock agent，其 ainvoke 会先执行 entries_setup 再返回。

    entries_setup 用于在"Agent 调用工具"后模拟 MemoryManager 的条目变化。
    """

    async def fake_ainvoke(_input, config=None):
        if entries_setup:
            entries_setup()
        return {"messages": []}

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return agent


def _assert_file_contains(path: Path, text: str):
    """断言 memory.yaml 文件包含指定文本。"""
    content = path.read_text(encoding="utf-8")
    assert text in content, f"文件中未找到 '{text}'，实际内容: {content}"


def _mm_from_path(path: Path) -> MemoryManager:
    """用指定路径创建并加载 MemoryManager。"""
    mm = MemoryManager(yaml_file=str(path))
    return mm


def _populate_mm(path: Path, items: list[tuple[str, str]]) -> None:
    """向指定路径的 yaml 文件写入记忆条目。每项为 (description, theme)。"""
    mm = MemoryManager(yaml_file=str(path))
    for desc, theme in items:
        mm.add(description=desc, theme=theme)


# ── TestFormatMessages ────────────────────────────────────────


class TestFormatMessages:
    """_format_messages 单元测试。"""

    def test_empty_list(self):
        result = narrative._format_messages([])
        assert result == ""

    def test_single_message(self):
        msgs = [{"role": "user", "content": "你好"}]
        result = narrative._format_messages(msgs)
        assert result == "[user]: 你好"

    def test_multiple_messages(self):
        msgs = [
            {"role": "user", "content": "查天气"},
            {"role": "assistant", "content": "今天晴"},
        ]
        result = narrative._format_messages(msgs)
        expected = "[user]: 查天气\n[assistant]: 今天晴"
        assert result == expected

    def test_missing_role_defaults_to_unknown(self):
        msgs = [{"content": "hello"}]
        result = narrative._format_messages(msgs)
        assert result == "[unknown]: hello"

    def test_tool_messages_filtered_out(self):
        """工具输出被过滤，避免幻觉。"""
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "tool", "content": "天气数据..."},
            {"role": "assistant", "content": "回复"},
        ]
        result = narrative._format_messages(msgs)
        assert "[tool]" not in result
        assert "[user]: 你好" in result
        assert "[assistant]: 回复" in result

    def test_non_string_content(self):
        msgs = [{"role": "user", "content": 42}]
        result = narrative._format_messages(msgs)
        assert result == "[user]: 42"


# ── TestFormatHelpers ─────────────────────────────────────────


class TestFormatNarrative:
    """_format_narrative 格式化测试。"""

    def test_empty_items(self):
        assert narrative._format_narrative([]) == ""

    def test_single_item(self):
        items = [{"id": "abc", "description": "用户叫Miso。", "theme": "身份"}]
        result = narrative._format_narrative(items)
        assert "# 长期记忆索引" in result
        assert "- [身份](#身份)" in result
        assert "---" in result
        assert "## 身份" in result
        assert "- 用户叫Miso。" in result

    def test_multi_theme(self):
        items = [
            {"id": "a", "description": "用户叫Miso。", "theme": "身份"},
            {"id": "b", "description": "用户喜欢洛天依。", "theme": "音乐"},
        ]
        result = narrative._format_narrative(items)
        assert "## 身份" in result
        assert "- 用户叫Miso。" in result
        assert "## 音乐" in result
        assert "- 用户喜欢洛天依。" in result
        # TOC contains both
        assert "- [身份](#身份)" in result
        assert "- [音乐](#音乐)" in result


class TestFormatEntriesForTool:
    """_format_entries_for_tool 格式化测试。"""

    def test_empty(self):
        assert narrative._format_entries_for_tool([]) == "（暂无记忆条目）"

    def test_with_entries(self):
        items = [
            {"id": "uuid-1", "description": "A", "theme": "身份"},
            {"id": "uuid-2", "description": "B", "theme": "音乐"},
        ]
        result = narrative._format_entries_for_tool(items)
        assert "## 身份" in result
        assert "  [uuid-1] A" in result
        assert "## 音乐" in result
        assert "  [uuid-2] B" in result

    def test_custom_theme(self):
        items = [
            {"id": "x", "description": "A", "theme": "健康"},
        ]
        result = narrative._format_entries_for_tool(items)
        assert "## 健康" in result
        assert "  [x] A" in result


# ── TestCrudTools ──────────────────────────────────────────────


class TestCrudTools:
    """CRUD 工具函数单元测试。"""

    def _make_mm(self, tmp_path: Path) -> MemoryManager:
        mm = MemoryManager(yaml_file=str(tmp_path / "memory.yaml"))
        narrative._set_current_mm(mm)
        return mm

    def test_create_memory(self, tmp_path):
        mm = self._make_mm(tmp_path)
        result = narrative.create_memory.invoke(
            {"content": "用户叫Miso。", "section": "身份"}
        )
        assert "已创建 [" in result
        assert "身份" in result
        items = mm.show()
        assert len(items) == 1
        assert items[0]["description"] == "用户叫Miso。"
        assert items[0]["theme"] == "身份"

    def test_create_memory_custom_section_preserved(self, tmp_path):
        mm = self._make_mm(tmp_path)
        result = narrative.create_memory.invoke(
            {"content": "用户叫Miso。", "section": "健康"}
        )
        assert "已创建 [" in result
        assert "健康" in result
        items = mm.show()
        assert items[0]["theme"] == "健康"

    def test_create_memory_empty_section_fallback(self, tmp_path):
        mm = self._make_mm(tmp_path)
        result = narrative.create_memory.invoke(
            {"content": "用户叫Miso。", "section": "   "}
        )
        assert "已创建 [" in result
        items = mm.show()
        assert items[0]["theme"] == "   "

    def test_create_memory_id_is_hex(self, tmp_path):
        self._make_mm(tmp_path)
        result = narrative.create_memory.invoke(
            {"content": "用户叫Miso。", "section": "身份"}
        )
        # Extract ID from result string
        match = re.search(r"\[([a-f0-9]+)\]", result)
        assert match is not None
        assert len(match.group(1)) == 8  # 8-char hex
        assert all(c in "0123456789abcdef" for c in match.group(1))

    def test_read_memories_empty(self, tmp_path):
        mm = MemoryManager(yaml_file=str(tmp_path / "memory.yaml"))
        narrative._set_current_mm(mm)
        result = narrative.read_memories.invoke({})
        assert "暂无记忆条目" in result

    def test_read_memories_with_entries(self, tmp_path):
        mm = self._make_mm(tmp_path)
        mm.add(description="A", theme="身份")
        mm.add(description="B", theme="音乐")
        result = narrative.read_memories.invoke({})
        assert "## 身份" in result
        assert "## 音乐" in result

    def test_update_memory_success(self, tmp_path):
        mm = self._make_mm(tmp_path)
        item_id = mm.add(description="旧内容", theme="身份")
        result = narrative.update_memory.invoke(
            {
                "id": item_id,
                "content": "新内容",
                "reason": "信息过时，需要更新",
                "origin_content": "旧内容",
            }
        )
        assert "已更新" in result
        items = mm.show()
        assert items[0]["description"] == "新内容"

    def test_update_memory_not_found(self, tmp_path):
        self._make_mm(tmp_path)
        result = narrative.update_memory.invoke(
            {
                "id": "nonexistent-id",
                "content": "x",
                "reason": "测试",
                "origin_content": "不存在",
            }
        )
        assert "错误" in result

    def test_delete_memory_success(self, tmp_path):
        mm = self._make_mm(tmp_path)
        item_id = mm.add(description="删除我", theme="身份")
        result = narrative.delete_memory.invoke(
            {
                "id": item_id,
                "reason": "信息已过时",
                "origin_content": "删除我",
            }
        )
        assert "已删除" in result
        assert mm.show() == []

    def test_delete_memory_not_found(self, tmp_path):
        self._make_mm(tmp_path)
        result = narrative.delete_memory.invoke(
            {
                "id": "nonexistent-id",
                "reason": "测试",
                "origin_content": "不存在",
            }
        )
        assert "错误" in result


# ── TestGetNarrative ──────────────────────────────────────────


class TestGetNarrative:
    """模块级 get_narrative 测试。"""

    def setup_method(self):
        """每个测试前清除 LRU 缓存，防止 monkeypatch 的 MEMORY_PATH 被缓存污染。"""
        narrative.get_narrative.cache_clear()

    def test_file_not_exists(self, monkeypatch, tmp_path):
        p = tmp_path / "memory.yaml"
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        assert narrative.get_narrative() == ""

    def test_file_exists(self, monkeypatch, tmp_path):
        p = tmp_path / "memory.yaml"
        _populate_mm(p, [("Miso 是学生。", "身份")])
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        result = narrative.get_narrative()
        assert "Miso 是学生。" in result
        assert "## 身份" in result

    def test_file_empty(self, monkeypatch, tmp_path):
        p = tmp_path / "memory.yaml"
        MemoryManager(yaml_file=str(p))  # creates empty file
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        assert narrative.get_narrative() == ""

    def test_multiple_themes(self, monkeypatch, tmp_path):
        p = tmp_path / "memory.yaml"
        _populate_mm(
            p,
            [
                ("用户叫Miso。", "身份"),
                ("用户喜欢洛天依。", "音乐"),
            ],
        )
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        result = narrative.get_narrative()
        assert "用户叫Miso。" in result
        assert "用户喜欢洛天依。" in result
        assert "# 长期记忆索引" in result
        assert "- [身份](#身份)" in result
        assert "- [音乐](#音乐)" in result


# ── TestLongTermMemoryInterface ────────────────────────────────


class TestLongTermMemoryInterface:
    """LongTermMemoryInterface 异步单元测试。"""

    def setup_method(self):
        narrative._set_current_mm(None)

    def teardown_method(self):
        narrative._set_current_mm(None)

    # ── get_narrative（实例方法） ──────────────────────────────

    def test_get_narrative_file_not_exists(self, tmp_path):
        path = tmp_path / "memory.yaml"
        ltm = LongTermMemoryInterface(path)
        assert ltm.get_narrative() == ""

    def test_get_narrative_file_exists(self, tmp_path):
        path = tmp_path / "memory.yaml"
        _populate_mm(path, [("Miso 是学生。", "身份")])
        ltm = LongTermMemoryInterface(path)
        result = ltm.get_narrative()
        assert "Miso 是学生。" in result

    def test_get_narrative_file_empty(self, tmp_path):
        path = tmp_path / "memory.yaml"
        MemoryManager(yaml_file=str(path))
        ltm = LongTermMemoryInterface(path)
        assert ltm.get_narrative() == ""

    # ── 生命周期安全 ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_send_history_before_start_is_noop(self, tmp_path):
        """未 start_listening 时 send_history 不抛异常。"""
        ltm = LongTermMemoryInterface(tmp_path / "memory.yaml")
        await ltm.send_history([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_send_history_after_stop_is_noop(self, tmp_path, monkeypatch):
        """stop_listening 后 send_history 应无操作。"""
        path = tmp_path / "memory.yaml"

        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "msg1"}])
        await ltm.stop_listening()
        await ltm.send_history([{"role": "user", "content": "msg2"}])

        assert fake_agent.ainvoke.call_count == 1

    # ── 空消息过滤 ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_messages_not_enqueued(self, tmp_path, monkeypatch):
        """空消息不放入队列，Agent 不被调用。"""
        path = tmp_path / "memory.yaml"

        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([])
        await ltm.stop_listening()

        fake_agent.ainvoke.assert_not_called()

    # ── 冷启动 ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cold_start_generates_file(self, tmp_path, monkeypatch):
        """冷启动：memory.yaml 不存在时 Agent 从零创建条目。"""
        path = tmp_path / "memory.yaml"

        def agent_populates_entries():
            narrative._current_mm.add(description="Miso 是一名学生。", theme="身份")

        fake_agent = _fake_agent_factory(entries_setup=agent_populates_entries)
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "我叫Miso"}])
        await ltm.stop_listening()

        assert path.exists()
        _assert_file_contains(path, "Miso 是一名学生。")

    @pytest.mark.asyncio
    async def test_cold_start_uses_correct_prompt(self, tmp_path, monkeypatch):
        """冷启动时 Agent 收到 COLD_START_SYSTEM。"""
        path = tmp_path / "memory.yaml"

        captured_prompt = []

        def capture_agent(**kwargs):
            captured_prompt.append(kwargs.get("prompt", ""))
            return _fake_agent_factory()

        monkeypatch.setattr(narrative, "create_react_agent", capture_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "你好"}])
        await ltm.stop_listening()

        assert len(captured_prompt) == 1
        assert "记忆叙事师" in captured_prompt[0]
        assert "冷启动" in captured_prompt[0]

    # ── 常态更新 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_normal_update_preserves_old_narrative(self, tmp_path, monkeypatch):
        """常态更新：已有 memory.yaml 被传入 Agent，Agent 修改后保存。"""
        path = tmp_path / "memory.yaml"
        _populate_mm(path, [("旧记忆。", "身份")])

        captured_prompt = []

        def capture_agent(**kwargs):
            captured_prompt.append(kwargs.get("prompt", ""))

            def update_entries():
                mm = narrative._current_mm
                for item in mm.show():
                    mm.delete(item["id"])
                mm.add(description="更新后的记忆内容。", theme="身份")

            return _fake_agent_factory(entries_setup=update_entries)

        monkeypatch.setattr(narrative, "create_react_agent", capture_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "新消息"}])
        await ltm.stop_listening()

        assert len(captured_prompt) == 1
        assert "记忆叙事师" in captured_prompt[0]
        _assert_file_contains(path, "更新后的记忆内容。")

    # ── 多轮累积 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_multiple_turns_accumulate(self, tmp_path, monkeypatch):
        """多轮对话后叙事内容累积。"""
        path = tmp_path / "memory.yaml"

        captured_prompts = []
        call_count = [0]

        def capture_agent(**kwargs):
            captured_prompts.append(kwargs.get("prompt", ""))
            call_count[0] += 1
            if call_count[0] == 1:

                def setup1():
                    narrative._current_mm.add(description="第一轮记忆。", theme="身份")

                return _fake_agent_factory(entries_setup=setup1)
            else:

                def setup2():
                    mm = narrative._current_mm
                    mm.add(description="第一轮记忆。", theme="身份")
                    mm.add(description="第二轮补充。", theme="身份")

                return _fake_agent_factory(entries_setup=setup2)

        monkeypatch.setattr(narrative, "create_react_agent", capture_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())

        await ltm.send_history([{"role": "user", "content": "我叫Miso"}])
        await asyncio.sleep(0.05)

        await ltm.send_history([{"role": "user", "content": "我住北京"}])
        await ltm.stop_listening()

        assert call_count[0] == 2
        _assert_file_contains(path, "第二轮补充")

    # ── 错误处理 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_agent_error_is_silent(self, tmp_path, monkeypatch):
        """Agent 调用失败时不抛异常。"""
        path = tmp_path / "memory.yaml"

        async def failing_ainvoke(_input):
            raise RuntimeError("API 错误")

        fake_agent = MagicMock()
        fake_agent.ainvoke = AsyncMock(side_effect=failing_ainvoke)
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        # File is created by start_listening → load_yaml, but agent errored
        # so no entries were added; file exists with empty content
        assert path.exists()
        mm = _mm_from_path(path)
        assert mm.show() == []

    @pytest.mark.asyncio
    async def test_agent_produces_no_entries_preserves_original(
        self, tmp_path, monkeypatch
    ):
        """Agent 未创建条目时文件为空。"""
        path = tmp_path / "memory.yaml"

        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        # File is created by start_listening, but agent didn't add entries
        assert path.exists()
        mm = _mm_from_path(path)
        assert mm.show() == []

    @pytest.mark.asyncio
    async def test_agent_keeps_entries_unchanged_on_update(self, tmp_path, monkeypatch):
        """更新模式下 Agent 不改动条目，原内容被保留。"""
        path = tmp_path / "memory.yaml"
        _populate_mm(path, [("原始记忆。", "身份")])

        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        _assert_file_contains(path, "原始记忆。")

    # ── 哨兵机制 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sentinel_stops_consumer(self, tmp_path, monkeypatch):
        """None 哨兵正确停止消费者，且所有入队消息均被处理。"""
        path = tmp_path / "memory.yaml"

        fake_agent = _fake_agent_factory(
            entries_setup=lambda: narrative._current_mm.add(
                description="记忆。", theme="身份"
            )
        )
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "msg1"}])
        await ltm.send_history([{"role": "user", "content": "msg2"}])
        await ltm.stop_listening()

        assert fake_agent.ainvoke.call_count == 2
        assert ltm._consumer_task is None
        assert ltm._queue is None
