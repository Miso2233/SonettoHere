"""短��记忆测试 — 直接使用 LangChain 内置 InMemoryChatMessageHistory。"""

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage


class TestInMemoryChatMessageHistory:
    """验证 InMemoryChatMessageHistory 基本行为。"""

    def test_initial_state(self):
        m = InMemoryChatMessageHistory()
        assert m.messages == []

    def test_add_message(self):
        m = InMemoryChatMessageHistory()
        m.add_message(HumanMessage(content="你好"))
        assert len(m.messages) == 1
        assert m.messages[0].content == "你好"
        assert m.messages[0].type == "human"

    def test_add_messages(self):
        m = InMemoryChatMessageHistory()
        m.add_messages([
            HumanMessage(content="你好"),
            AIMessage(content="你好！"),
        ])
        assert len(m.messages) == 2

    def test_clear(self):
        m = InMemoryChatMessageHistory()
        m.add_message(HumanMessage(content="你好"))
        m.clear()
        assert m.messages == []

    def test_messages_preserved_without_trimming(self):
        """1M 上下文窗口下不做 token 裁剪，消息应完整保留。"""
        m = InMemoryChatMessageHistory()
        msgs = [HumanMessage(content=f"消息{i}") for i in range(100)]
        m.add_messages(msgs)
        assert len(m.messages) == 100
