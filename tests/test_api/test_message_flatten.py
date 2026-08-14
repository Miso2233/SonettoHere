"""消息 content 展平回归测试 — 修复 Anthropic blocks list 在前端渲染为 [object Object]。

Anthropic 的 ``AIMessage.content`` 是 blocks list（``[{"type":"text","text":...}, ...]``），
直接返回给前端会被 ``messagesToTurns`` 当作数组赋给 ``finalAnswer`` 渲染成 ``[object Object]``。
本测试锁定 GET /sessions/{id}/messages 与轮末 answer 的展平行为。
"""

from langchain_core.messages import AIMessage, HumanMessage

from api.agent.turn import _get_final_answer
from api.session.const_store import flatten_content

# Anthropic 风格 blocks content（含 tool_use 块，模拟带工具 agent 的输出）
ANTHROPIC_BLOCKS = [
    {"type": "text", "text": "你好"},
    {
        "type": "tool_use",
        "id": "toolu_01",
        "name": "search",
        "input": {"query": "Sonetto"},
    },
    {"type": "text", "text": "，这是答案。"},
]


class TestFlattenContent:
    def test_anthropic_blocks_extract_text_only(self) -> None:
        # tool_use 块被忽略，text 块按序拼接
        assert flatten_content(ANTHROPIC_BLOCKS) == "你好\n，这是答案。"

    def test_single_text_block(self) -> None:
        assert flatten_content([{"type": "text", "text": "Hello"}]) == "Hello"

    def test_plain_string_passthrough(self) -> None:
        assert flatten_content("Hello") == "Hello"

    def test_empty_list(self) -> None:
        assert flatten_content([]) == ""

    def test_openai_style_content_unchanged(self) -> None:
        # OpenAI/DeepSeek 的 content 是纯字符串，flatten 后必须原样返回
        assert flatten_content("正常回答") == "正常回答"


class TestGetFinalAnswerFlatten:
    def test_anthropic_blocks_flattened_to_text(self) -> None:
        event = {
            "data": {"output": {"messages": [AIMessage(content=ANTHROPIC_BLOCKS)]}}
        }
        assert _get_final_answer(event) == "你好\n，这是答案。"

    def test_openai_string_content_passthrough(self) -> None:
        event = {
            "data": {"output": {"messages": [AIMessage(content="正常回答")]}}
        }
        assert _get_final_answer(event) == "正常回答"

    def test_no_messages_returns_empty(self) -> None:
        assert _get_final_answer({"data": {"output": {"messages": []}}}) == ""


class TestMessagesEndpointSerialization:
    """GET /sessions/{id}/messages 必须返回展平后的字符串 content。"""

    def _call(self, monkeypatch, msgs: list) -> list:
        import api.routes.sessions as sessions_module

        class _FakeSession:
            def __init__(self, msgs):
                self._msgs = msgs

            async def get_messages(self) -> list:
                return self._msgs

        fake_manager = type("FakeManager", (), {"get": lambda self, sid: _FakeSession(msgs)})()
        monkeypatch.setattr(sessions_module, "session_manager", fake_manager)

        import asyncio

        result = asyncio.run(sessions_module.get_messages("sid-1", request=None))
        return result["messages"]

    def test_anthropic_content_flattened(self, monkeypatch) -> None:
        msgs = [
            HumanMessage(content="用户问题"),
            AIMessage(content=ANTHROPIC_BLOCKS),
        ]
        messages = self._call(monkeypatch, msgs)
        assert messages[1]["content"] == "你好\n，这是答案。"
        assert not isinstance(messages[1]["content"], list)

    def test_openai_string_content_preserved(self, monkeypatch) -> None:
        msgs = [
            HumanMessage(content="用户问题"),
            AIMessage(content="正常回答"),
        ]
        messages = self._call(monkeypatch, msgs)
        assert messages[1]["content"] == "正常回答"
