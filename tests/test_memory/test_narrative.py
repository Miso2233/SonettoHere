"""memory/narrative.py 测试。"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import memory.narrative as narrative
from memory.narrative import LongTermMemoryInterface


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


class TestLongTermMemoryInterface:
    """LongTermMemoryInterface 异步单元测试。"""

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
    async def test_send_history_after_stop_is_noop(self, tmp_path):
        """stop_listening 后 send_history 应无操作。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="记忆。"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "msg1"}])
        await ltm.stop_listening()
        await ltm.send_history([{"role": "user", "content": "msg2"}])

        assert llm.ainvoke.call_count == 1

    # ── 空消息过滤 ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_messages_not_enqueued(self, tmp_path):
        """空消息不放入队列，LLM 不被调用。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock()

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([])
        await ltm.stop_listening()

        llm.ainvoke.assert_not_called()

    # ── 冷启动 ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cold_start_generates_file(self, tmp_path):
        """冷启动：MEMORY.md 不存在时从零生成。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="Miso 是一名学生。"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "我叫Miso"}])
        await ltm.stop_listening()

        assert path.exists()
        assert "Miso" in path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_cold_start_uses_correct_prompt(self, tmp_path):
        """冷启动时 LLM 收到裸消息（不带旧叙事）。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="OK"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "你好"}])
        await ltm.stop_listening()

        call_args = llm.ainvoke.call_args[0][0]
        system_msg = call_args[0].content
        user_msg = call_args[1].content

        assert "记忆叙事师" in system_msg
        assert "[user]: 你好" in user_msg
        assert "当前记忆" not in user_msg

    # ── 常态更新 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_normal_update_preserves_old_narrative(self, tmp_path):
        """常态更新：LLM 收到旧叙事 + 新消息。"""
        path = tmp_path / "MEMORY.md"
        path.write_text("旧记忆内容。", encoding="utf-8")

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="更新后的记忆。"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "新消息"}])
        await ltm.stop_listening()

        call_args = llm.ainvoke.call_args[0][0]
        user_msg = call_args[1].content

        assert "旧记忆内容" in user_msg
        assert "当前记忆" in user_msg
        assert "新消息" in user_msg
        assert "新一轮对话" in user_msg
        assert "更新后的记忆" in path.read_text(encoding="utf-8")

    # ── 多轮累积 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_multiple_turns_accumulate(self, tmp_path):
        """多轮对话后叙事内容累积。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)

        llm.ainvoke = AsyncMock(return_value=MagicMock(content="第一轮记忆。"))
        await ltm.send_history([{"role": "user", "content": "我叫Miso"}])

        llm.ainvoke = AsyncMock(return_value=MagicMock(content="第一轮记忆。第二轮补充。"))
        await ltm.send_history([{"role": "user", "content": "我住北京"}])

        await ltm.stop_listening()

        call_args = llm.ainvoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "第一轮记忆" in user_msg
        assert "我住北京" in user_msg

        assert "第二轮补充" in path.read_text(encoding="utf-8")

    # ── 错误处理 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_llm_error_is_silent(self, tmp_path):
        """LLM 调用失败时不抛异常，不写文件。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("API 错误"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        assert not path.exists()

    @pytest.mark.asyncio
    async def test_llm_returns_empty_content_preserves_original(self, tmp_path):
        """LLM 返回空内容时不覆盖文件。"""
        path = tmp_path / "MEMORY.md"
        original = "原始记忆。"
        path.write_text(original, encoding="utf-8")

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="   "))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "测试"}])
        await ltm.stop_listening()

        assert path.read_text(encoding="utf-8") == original

    # ── 哨兵机制 ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sentinel_stops_consumer(self, tmp_path):
        """None 哨兵正确停止消费者，且所有入队消息均被处理。"""
        path = tmp_path / "MEMORY.md"
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="记忆。"))

        ltm = LongTermMemoryInterface(path)
        ltm.start_listening(llm)
        await ltm.send_history([{"role": "user", "content": "msg1"}])
        await ltm.send_history([{"role": "user", "content": "msg2"}])
        await ltm.stop_listening()

        assert llm.ainvoke.call_count == 2
        assert ltm._consumer_task is None
        assert ltm._queue is None
