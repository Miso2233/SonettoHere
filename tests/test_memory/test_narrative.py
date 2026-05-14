"""memory/narrative.py 测试。"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import memory.narrative as narrative
from memory.narrative import LongTermMemoryInterface


# ── 测试辅助 ──────────────────────────────────────────────────

def _fake_agent_factory(entries_setup=None):
    """构建 mock agent，其 ainvoke 会先执行 entries_setup 再返回。

    entries_setup 用于在"Agent 调用工具"后模拟 _current_entries 的变化。
    """
    async def fake_ainvoke(_input, config=None):
        if entries_setup:
            entries_setup()
        return {"messages": []}

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return agent


def _assert_file_contains(path: Path, text: str):
    """断言 MEMORY.md 文件包含指定文本。"""
    content = path.read_text(encoding="utf-8")
    assert text in content, f"文件中未找到 '{text}'，实际内容: {content}"


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


# ── TestParseSerialize ────────────────────────────────────────


class TestParseSerialize:
    """MemorySerializer 分区格式 单元测试。"""

    def test_parse_empty(self):
        entries, next_id = narrative.MemorySerializer.parse("")
        assert entries == {}
        assert next_id == 1

    def test_parse_single_section_single_entry(self):
        content = "## 身份\n- 用户叫Miso。\n"
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {"1": {"section": "身份", "content": "用户叫Miso。"}}
        assert next_id == 2

    def test_parse_multi_section(self):
        content = (
            "## 身份\n"
            "- 用户叫Miso。\n"
            "\n"
            "## 音乐\n"
            "- 用户喜欢洛天依。\n"
            "- 用户关注TUNO桐音。\n"
        )
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {
            "1": {"section": "身份", "content": "用户叫Miso。"},
            "2": {"section": "音乐", "content": "用户喜欢洛天依。"},
            "3": {"section": "音乐", "content": "用户关注TUNO桐音。"},
        }
        assert next_id == 4

    def test_parse_skips_toc_and_separators(self):
        content = (
            "# 长期记忆索引\n"
            "- [身份](#身份)\n"
            "\n"
            "---\n"
            "\n"
            "## 身份\n"
            "- 用户叫Miso。\n"
        )
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {"1": {"section": "身份", "content": "用户叫Miso。"}}
        assert next_id == 2

    def test_parse_skips_html_comments(self):
        content = "## 身份 <!-- stable -->\n- 用户叫Miso。\n"
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {"1": {"section": "身份", "content": "用户叫Miso。"}}
        assert next_id == 2

    def test_parse_subsections_dont_change_section(self):
        content = (
            "## 音乐\n"
            "### 虚拟歌手\n"
            "- 用户喜欢洛天依。\n"
            "### 歌曲\n"
            "- 用户最喜欢《海边城》。\n"
        )
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {
            "1": {"section": "音乐", "content": "用户喜欢洛天依。"},
            "2": {"section": "音乐", "content": "用户最喜欢《海边城》。"},
        }

    def test_parse_accepts_custom_section(self):
        content = "## 未知分区\n- 这条应被保留。\n## 身份\n- 用户叫Miso。\n"
        entries, next_id = narrative.MemorySerializer.parse(content)
        assert entries == {
            "1": {"section": "未知分区", "content": "这条应被保留。"},
            "2": {"section": "身份", "content": "用户叫Miso。"},
        }
        assert next_id == 3

    def test_serialize_empty(self):
        result = narrative.MemorySerializer.serialize({})
        assert result == "\n"

    def test_serialize_with_entries(self):
        entries = {
            "1": {"section": "身份", "content": "用户叫Miso。"},
            "2": {"section": "音乐", "content": "用户喜欢洛天依。"},
        }
        result = narrative.MemorySerializer.serialize(entries)
        assert "# 长期记忆索引" in result
        assert "- [身份](#身份)" in result
        assert "- [音乐](#音乐)" in result
        assert "---" in result
        assert "## 身份" in result
        assert "- 用户叫Miso。" in result
        assert "## 音乐" in result
        assert "- 用户喜欢洛天依。" in result

    def test_serialize_omits_empty_sections(self):
        entries = {"1": {"section": "身份", "content": "用户叫Miso。"}}
        result = narrative.MemorySerializer.serialize(entries)
        assert "## 音乐" not in result
        assert "## 品味" not in result

    def test_roundtrip(self):
        """分区格式序列化后解析应得到相同条目。"""
        original = (
            "## 身份\n"
            "- 用户叫Miso。\n"
            "\n"
            "## 音乐\n"
            "- 用户喜欢洛天依。\n"
        )
        entries, _ = narrative.MemorySerializer.parse(original)
        serialized = narrative.MemorySerializer.serialize(entries)
        entries2, _ = narrative.MemorySerializer.parse(serialized)
        assert entries == entries2

    def test_serialize_includes_custom_sections(self):
        entries = {
            "1": {"section": "身份", "content": "用户叫Miso。"},
            "2": {"section": "健康", "content": "用户有季节性过敏。"},
        }
        result = narrative.MemorySerializer.serialize(entries)
        assert "## 身份" in result
        assert "## 健康" in result
        assert "- [身份](#身份)" in result
        assert "- [健康](#健康)" in result

    def test_roundtrip_with_custom_sections(self):
        original = (
            "## 身份\n"
            "- 用户叫Miso。\n"
            "\n"
            "## 健康\n"
            "- 用户有过敏。\n"
        )
        entries, _ = narrative.MemorySerializer.parse(original)
        serialized = narrative.MemorySerializer.serialize(entries)
        entries2, _ = narrative.MemorySerializer.parse(serialized)
        assert entries == entries2

    def test_serialize_section_order_by_first_appearance(self):
        entries = {
            "2": {"section": "音乐", "content": "B"},
            "1": {"section": "身份", "content": "A"},
            "3": {"section": "音乐", "content": "C"},
        }
        result = narrative.MemorySerializer.serialize(entries)
        pos_yinyue = result.index("## 音乐")
        pos_shenfen = result.index("## 身份")
        assert pos_shenfen < pos_yinyue  # 身份(ID=1) appears before 音乐(ID=2)


# ── TestCrudTools ──────────────────────────────────────────────


class TestCrudTools:
    """CRUD 工具函数单元测试。"""

    def setup_method(self):
        narrative.MemoryStore().reset()

    def teardown_method(self):
        narrative.MemoryStore().reset()

    def test_create_memory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        result = narrative.create_memory.invoke({"content": "用户叫Miso。", "section": "身份"})
        assert "已创建 [1]" in result
        assert "身份" in result
        assert narrative.MemoryStore().entries["1"] == {"section": "身份", "content": "用户叫Miso。"}
        assert narrative.MemoryStore().next_id == 2

    def test_create_memory_custom_section_preserved(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        result = narrative.create_memory.invoke({"content": "用户叫Miso。", "section": "健康"})
        assert "已创建 [1]" in result
        assert "健康" in result
        assert narrative.MemoryStore().entries["1"]["section"] == "健康"

    def test_create_memory_empty_section_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        result = narrative.create_memory.invoke({"content": "用户叫Miso。", "section": "   "})
        assert "已创建 [1]" in result
        assert narrative.MemoryStore().entries["1"]["section"] == "身份"

    def test_read_memories_empty(self):
        result = narrative.read_memories.invoke({})
        assert "暂无记忆条目" in result

    def test_read_memories_with_entries(self):
        narrative.MemoryStore().entries = {
            "1": {"section": "身份", "content": "A"},
            "2": {"section": "音乐", "content": "B"},
        }
        result = narrative.read_memories.invoke({})
        assert "## 身份" in result
        assert "[1] A" in result
        assert "## 音乐" in result
        assert "[2] B" in result

    def test_read_memories_with_custom_sections(self):
        narrative.MemoryStore().entries = {
            "1": {"section": "身份", "content": "A"},
            "2": {"section": "健康", "content": "B"},
        }
        result = narrative.read_memories.invoke({})
        assert "## 身份" in result
        assert "[1] A" in result
        assert "## 健康" in result
        assert "[2] B" in result

    def test_update_memory_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        narrative.MemoryStore().entries = {"1": {"section": "身份", "content": "旧内容"}}
        result = narrative.update_memory.invoke({
            "id": "1", "content": "新内容",
            "reason": "信息过时，需要更新",
            "origin_content": "旧内容",
        })
        assert "已更新 [1]" in result
        assert narrative.MemoryStore().entries["1"] == {"section": "身份", "content": "新内容"}

    def test_update_memory_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        result = narrative.update_memory.invoke({
            "id": "99", "content": "x",
            "reason": "测试", "origin_content": "不存在",
        })
        assert "错误" in result

    def test_delete_memory_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        narrative.MemoryStore().entries = {"1": {"section": "身份", "content": "删除我"}}
        result = narrative.delete_memory.invoke({
            "id": "1", "reason": "信息已过时", "origin_content": "删除我",
        })
        assert "已删除 [1]" in result
        assert "1" not in narrative.MemoryStore().entries

    def test_delete_memory_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setattr(narrative, "LOG_PATH", tmp_path / "ops.yaml")
        result = narrative.delete_memory.invoke({
            "id": "99", "reason": "测试", "origin_content": "不存在",
        })
        assert "错误" in result

    # ── 日志测试 ──────────────────────────────────────────────

    def test_log_created_on_create(self, monkeypatch, tmp_path):
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.create_memory.invoke({"content": "用户叫Miso。", "section": "身份"})
        assert log_path.exists()
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["operation"] == "create_memory"
        assert data[0]["params"]["content"] == "用户叫Miso。"
        assert data[0]["params"]["section"] == "身份"
        assert "id" not in data[0]["params"]

    def test_log_created_on_update(self, monkeypatch, tmp_path):
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.MemoryStore().entries = {"1": {"section": "身份", "content": "旧内容"}}
        narrative.update_memory.invoke({
            "id": "1", "content": "新内容",
            "reason": "信息过时", "origin_content": "旧内容",
        })
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["operation"] == "update_memory"
        assert data[0]["params"]["content"] == "新内容"
        assert data[0]["params"]["reason"] == "信息过时"
        assert data[0]["params"]["origin_content"] == "旧内容"
        assert "id" not in data[0]["params"]

    def test_log_created_on_delete(self, monkeypatch, tmp_path):
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.MemoryStore().entries = {"1": {"section": "身份", "content": "删除我"}}
        narrative.delete_memory.invoke({
            "id": "1", "reason": "已过时", "origin_content": "删除我",
        })
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["operation"] == "delete_memory"
        assert data[0]["params"]["reason"] == "已过时"
        assert data[0]["params"]["origin_content"] == "删除我"
        assert "id" not in data[0]["params"]

    def test_log_not_created_on_error(self, monkeypatch, tmp_path):
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.update_memory.invoke({
            "id": "99", "content": "x",
            "reason": "测试", "origin_content": "不存在",
        })
        assert not log_path.exists()

    def test_log_appends_multiple_entries(self, monkeypatch, tmp_path):
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.create_memory.invoke({"content": "第一条。", "section": "身份"})
        narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "第一条。"}
        narrative.update_memory.invoke({
            "id": "1", "content": "第一条已改。",
            "reason": "修正", "origin_content": "第一条。",
        })
        narrative.delete_memory.invoke({
            "id": "1", "reason": "不再需要", "origin_content": "第一条已改。",
        })
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 3
        assert data[0]["operation"] == "create_memory"
        assert data[1]["operation"] == "update_memory"
        assert data[2]["operation"] == "delete_memory"

    def test_multiline_content_is_sanitized(self, monkeypatch, tmp_path):
        """含换行符的内容在写入 YAML 日志前被折叠为单行。"""
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.create_memory.invoke({
            "content": "用户是广东人。\n会让他回想起小时候在家乡的夏天。",
            "section": "身份",
        })
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        content = data[0]["params"]["content"]
        assert "\n" not in content
        assert "\r" not in content
        assert "用户是广东人。 会让他回想起小时候在家乡的夏天。" in content

    def test_multiline_in_update_and_delete_is_sanitized(self, monkeypatch, tmp_path):
        """update/delete 中的 reason/origin_content 含换行也被清理。"""
        log_path = tmp_path / "ops.yaml"
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "旧内容没有换行"}
        narrative.update_memory.invoke({
            "id": "1", "content": "新内容也没有换行",
            "reason": "用户提供了\n更准确的信息",
            "origin_content": "旧内容没有换行",
        })
        narrative.delete_memory.invoke({
            "id": "1",
            "reason": "信息已\n过时",
            "origin_content": "新内容也没有换行",
        })
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert "\n" not in data[0]["params"]["reason"]
        assert "\n" not in data[1]["params"]["reason"]

    def test_corrupted_yaml_is_recovered(self, monkeypatch, tmp_path):
        """已被破坏的 YAML 文件不会导致 log() 崩溃。"""
        log_path = tmp_path / "ops.yaml"
        log_path.write_text("::: invalid yaml :::\n  - dangling", encoding="utf-8")
        monkeypatch.setattr(narrative, "LOG_PATH", log_path)
        narrative.create_memory.invoke({"content": "一条新记忆。", "section": "身份"})
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["operation"] == "create_memory"


# ── TestGetNarrative ──────────────────────────────────────────


class TestGetNarrative:
    """模块级 get_narrative 向后兼容测试。"""

    def test_file_not_exists(self, monkeypatch, tmp_path):
        p = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        assert narrative.get_narrative() == ""

    def test_file_exists(self, monkeypatch, tmp_path):
        p = tmp_path / "MEMORY.md"
        p.write_text("  Miso 是学生。  ", encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        assert narrative.get_narrative() == "Miso 是学生。"

    def test_file_empty(self, monkeypatch, tmp_path):
        p = tmp_path / "MEMORY.md"
        p.write_text("   \n", encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", p)
        assert narrative.get_narrative() == ""


# ── TestLongTermMemoryInterface ────────────────────────────────


class TestLongTermMemoryInterface:
    """LongTermMemoryInterface 异步单元测试。"""

    def setup_method(self):
        """每个测试前重置模块级状态。"""
        narrative.MemoryStore().reset()

    def teardown_method(self):
        """每个测试后清理模块级状态。"""
        narrative.MemoryStore().reset()

    # ── get_narrative（实例方法） ──────────────────────────────

    def test_get_narrative_file_not_exists(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        ltm = LongTermMemoryInterface(path)
        assert ltm.get_narrative() == ""

    def test_get_narrative_file_exists(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("  Miso 是学生。  ", encoding="utf-8")
        ltm = LongTermMemoryInterface(path)
        assert ltm.get_narrative() == "Miso 是学生。"

    def test_get_narrative_file_empty(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("   \n", encoding="utf-8")
        ltm = LongTermMemoryInterface(path)
        assert ltm.get_narrative() == ""

    # ── 生命周期安全 ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_send_history_before_start_is_noop(self, tmp_path):
        """未 start_listening 时 send_history 不抛异常。"""
        ltm = LongTermMemoryInterface(tmp_path / "MEMORY.md")
        await ltm.send_history([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_send_history_after_stop_is_noop(self, tmp_path, monkeypatch):
        """stop_listening 后 send_history 应无操作。"""
        path = tmp_path / "MEMORY.md"

        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())  # llm 不再被直接调用
        await ltm.send_history([{"role": "user", "content": "msg1"}])
        await ltm.stop_listening()
        await ltm.send_history([{"role": "user", "content": "msg2"}])

        assert fake_agent.ainvoke.call_count == 1

    # ── 空消息过滤 ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_messages_not_enqueued(self, tmp_path, monkeypatch):
        """空消息不放入队列，Agent 不被调用。"""
        path = tmp_path / "MEMORY.md"

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
        """冷启动：MEMORY.md 不存在时 Agent 从零创建条目。"""
        path = tmp_path / "MEMORY.md"

        def agent_populates_entries():
            narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "Miso 是一名学生。"}

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
        path = tmp_path / "MEMORY.md"

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
        """常态更新：已有 MEMORY.md 被传入 Agent，Agent 修改后保存。"""
        path = tmp_path / "MEMORY.md"
        path.write_text("## 身份\n- 旧记忆。\n", encoding="utf-8")

        captured_prompt = []
        def capture_agent(**kwargs):
            captured_prompt.append(kwargs.get("prompt", ""))
            # 模拟 Agent 更新了一条记忆
            def update_entries():
                narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "更新后的记忆内容。"}
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
        path = tmp_path / "MEMORY.md"

        captured_prompts = []
        call_count = [0]

        def capture_agent(**kwargs):
            captured_prompts.append(kwargs.get("prompt", ""))
            call_count[0] += 1
            if call_count[0] == 1:
                def setup1():
                    narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "第一轮记忆。"}
                return _fake_agent_factory(entries_setup=setup1)
            else:
                def setup2():
                    narrative.MemoryStore().entries["1"] = {"section": "身份", "content": "第一轮记忆。"}
                    narrative.MemoryStore().entries["2"] = {"section": "身份", "content": "第二轮补充。"}
                return _fake_agent_factory(entries_setup=setup2)

        monkeypatch.setattr(narrative, "create_react_agent", capture_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())

        await ltm.send_history([{"role": "user", "content": "我叫Miso"}])
        # 等待第一轮完成——因为 consumer 是后台协程，send_history 是非阻塞的
        await asyncio.sleep(0.05)

        await ltm.send_history([{"role": "user", "content": "我住北京"}])
        await ltm.stop_listening()

        assert call_count[0] == 2
        _assert_file_contains(path, "第二轮补充")

    # ── 错误处理 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_agent_error_is_silent(self, tmp_path, monkeypatch):
        """Agent 调用失败时不抛异常，不写文件。"""
        path = tmp_path / "MEMORY.md"

        async def failing_ainvoke(_input):
            raise RuntimeError("API 错误")

        fake_agent = MagicMock()
        fake_agent.ainvoke = AsyncMock(side_effect=failing_ainvoke)
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        assert not path.exists()

    @pytest.mark.asyncio
    async def test_agent_produces_no_entries_preserves_original(self, tmp_path, monkeypatch):
        """Agent 未创建条目（_current_entries 为空）时不覆盖文件。"""
        path = tmp_path / "MEMORY.md"

        # 无 entries_setup → _current_entries 保持为空
        fake_agent = _fake_agent_factory()
        monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(MagicMock())
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        # 冷启动 + 空条目 → 不写文件
        assert not path.exists()

    @pytest.mark.asyncio
    async def test_agent_keeps_entries_unchanged_on_update(self, tmp_path, monkeypatch):
        """更新模式下 Agent 不改动条目，原内容被保留（幂等重写）。"""
        path = tmp_path / "MEMORY.md"
        original = "## 身份\n- 原始记忆。\n"
        path.write_text(original, encoding="utf-8")

        # 无 entries_setup → parse 出的条目保持不变
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
        path = tmp_path / "MEMORY.md"

        fake_agent = _fake_agent_factory(
            entries_setup=lambda: narrative.MemoryStore().entries.update({"1": {"section": "身份", "content": "记忆。"}})
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
