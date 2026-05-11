"""memory/narrative.py 测试。"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import memory.narrative as narrative


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

    def test_non_string_content(self):
        msgs = [{"role": "tool", "content": 42}]
        result = narrative._format_messages(msgs)
        assert result == "[tool]: 42"


class TestGetNarrative:
    """get_narrative 单元测试。"""

    def test_file_not_exists(self, monkeypatch, tmp_path):
        """MEMORY.md 不存在时返回空字符串。"""
        monkeypatch.setattr(narrative, "MEMORY_PATH", tmp_path / "MEMORY.md")
        assert narrative.get_narrative() == ""

    def test_file_exists(self, monkeypatch, tmp_path):
        """MEMORY.md 存在时返回其内容。"""
        path = tmp_path / "MEMORY.md"
        path.write_text("  Miso 是学生。  ", encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)
        assert narrative.get_narrative() == "Miso 是学生。"

    def test_file_empty(self, monkeypatch, tmp_path):
        """MEMORY.md 为空时返回空字符串。"""
        path = tmp_path / "MEMORY.md"
        path.write_text("   \n", encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)
        assert narrative.get_narrative() == ""


class TestUpdateNarrative:
    """update_narrative 测试。"""

    def test_empty_messages_returns_early(self, monkeypatch, tmp_path):
        """空消息列表不触发 LLM 调用。"""
        path = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)
        llm = MagicMock()
        narrative.update_narrative(llm, [])
        llm.invoke.assert_not_called()

    def test_cold_start_generates_new_file(self, monkeypatch, tmp_path):
        """冷启动：MEMORY.md 不存在时从零生成。"""
        path = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        response = MagicMock()
        response.content = "Miso 是一名学生。"
        llm.invoke.return_value = response

        narrative.update_narrative(llm, [{"role": "user", "content": "我叫Miso"}])

        assert path.exists()
        assert "Miso" in path.read_text(encoding="utf-8")

    def test_cold_start_calls_llm_with_correct_prompt(self, monkeypatch, tmp_path):
        """冷启动时 LLM 收到裸消息（不带旧叙事）。"""
        path = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        response = MagicMock()
        response.content = "OK"
        llm.invoke.return_value = response

        narrative.update_narrative(llm, [{"role": "user", "content": "你好"}])

        call_args = llm.invoke.call_args[0][0]
        system_msg = call_args[0].content
        user_msg = call_args[1].content

        assert "记忆叙事师" in system_msg
        assert "[user]: 你好" in user_msg
        assert "当前记忆" not in user_msg  # 冷启动没有旧叙事

    def test_normal_update_preserves_old_narrative(self, monkeypatch, tmp_path):
        """常态更新：LLM 收到旧叙事 + 新消息。"""
        path = tmp_path / "MEMORY.md"
        path.write_text("旧记忆内容。", encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        response = MagicMock()
        response.content = "更新后的记忆。"
        llm.invoke.return_value = response

        narrative.update_narrative(llm, [{"role": "user", "content": "新消息"}])

        call_args = llm.invoke.call_args[0][0]
        user_msg = call_args[1].content

        assert "旧记忆内容" in user_msg
        assert "当前记忆" in user_msg
        assert "新消息" in user_msg
        assert "新一轮对话" in user_msg

        assert "更新后的记忆" in path.read_text(encoding="utf-8")

    def test_llm_error_is_silent(self, monkeypatch, tmp_path):
        """LLM 调用失败时不抛异常，不写文件。"""
        path = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("API 错误")

        # 不应抛异常
        narrative.update_narrative(llm, [{"role": "user", "content": "测试"}])
        # 文件未写入（冷启动路径，文件不存在→不应创建）
        assert not path.exists()

    def test_llm_returns_empty_content(self, monkeypatch, tmp_path):
        """LLM 返回空内容时不覆盖文件。"""
        path = tmp_path / "MEMORY.md"
        original = "原始记忆。"
        path.write_text(original, encoding="utf-8")
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        response = MagicMock()
        response.content = "   "  # 只有空白
        llm.invoke.return_value = response

        narrative.update_narrative(llm, [{"role": "user", "content": "测试"}])
        # 文件内容不变
        assert path.read_text(encoding="utf-8") == original

    def test_multiple_turns_accumulate(self, monkeypatch, tmp_path):
        """多轮对话后叙事内容累积。"""
        path = tmp_path / "MEMORY.md"
        monkeypatch.setattr(narrative, "MEMORY_PATH", path)

        llm = MagicMock()
        # 第一轮 — 冷启动
        llm.invoke.return_value = MagicMock(content="第一轮记忆。")
        narrative.update_narrative(llm, [{"role": "user", "content": "我叫Miso"}])

        # 第二轮 — 更新
        llm.invoke.return_value = MagicMock(content="第一轮记忆。第二轮补充。")
        narrative.update_narrative(llm, [{"role": "user", "content": "我住北京"}])

        # 检查第二轮调用时收到了第一轮的记忆
        call_args = llm.invoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "第一轮记忆" in user_msg
        assert "我住北京" in user_msg

        final = path.read_text(encoding="utf-8")
        assert "第二轮补充" in final
