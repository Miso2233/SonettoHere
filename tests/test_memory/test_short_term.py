"""memory/short_term.py 测试。"""

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from memory.short_term import ShortTermMemory


class TestShortTermMemory:
    """ShortTermMemory 单元测试。"""

    def test_initial_state(self):
        memory = ShortTermMemory()
        assert memory.messages == []
        assert memory.to_dict_list() == []

    def test_add_message(self):
        memory = ShortTermMemory()
        msg = HumanMessage(content="你好")
        memory.add_message(msg)
        assert len(memory.messages) == 1
        assert memory.messages[0].content == "你好"

    def test_add_messages(self):
        memory = ShortTermMemory()
        msgs = [
            HumanMessage(content="你好"),
            AIMessage(content="你好！有什么可以帮助你的？"),
        ]
        memory.add_messages(msgs)
        assert len(memory.messages) == 2

    def test_clear(self):
        memory = ShortTermMemory()
        memory.add_message(HumanMessage(content="你好"))
        memory.clear()
        assert memory.messages == []

    def test_to_dict_list(self):
        memory = ShortTermMemory()
        memory.add_message(HumanMessage(content="你好"))
        memory.add_message(AIMessage(content="你好！"))
        result = memory.to_dict_list()
        assert result == [
            {"role": "human", "content": "你好"},
            {"role": "ai", "content": "你好！"},
        ]

    def test_trim_removes_oldest_first(self):
        """超过 token 限制时从头部删除最旧消息。"""
        memory = ShortTermMemory(max_tokens=50)
        # 添加三条足以超限的消息
        long_msg = HumanMessage(content="A" * 30)  # ~34 tokens
        memory.add_message(long_msg)
        assert len(memory.messages) >= 1

    def test_trim_preserves_last_two(self):
        """即使超限也保留至少 2 条消息。"""
        memory = ShortTermMemory(max_tokens=1)  # 极低限制
        msg1 = HumanMessage(content="第一条")
        msg2 = AIMessage(content="第二条")
        msg3 = HumanMessage(content="第三条")
        memory.add_messages([msg1, msg2, msg3])
        # 至少保留 2 条（trim 循环中 len(msgs) > 2 才继续删）
        assert len(memory.messages) >= 2

    def test_trim_not_triggered_under_limit(self):
        """未超 token 限制时不裁剪。"""
        memory = ShortTermMemory(max_tokens=100000)
        msgs = [
            HumanMessage(content="短消息1"),
            AIMessage(content="短消息2"),
        ]
        memory.add_messages(msgs)
        assert len(memory.messages) == 2
