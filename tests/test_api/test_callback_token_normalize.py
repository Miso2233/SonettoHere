"""WebSocketCallback token 归一化测试 — 块式 token（Kimi K3 等 Anthropic 适配模型）。

部分模型把 content blocks（thinking/text）原样透传为 ``on_llm_new_token`` 的 token，
本测试锁定：text 块 → token 事件、thinking 块 → thinking_token 计数、普通字符串原样转发。
"""

# 先经 app 正常入口初始化导入顺序，避免 api.events 循环导入
import api.agent.turn  # noqa: F401

from api.callbacks.websocket_callback import WebSocketCallback, _extract_block_token

KIMI_THINKING = '[{"thinking":"用","type":"thinking","index":0}]'
KIMI_TEXT = '[{"text":"晚上好！","type":"text","index":1}]'
KIMI_TEXT_LIST = [{"text": "你好", "type": "text", "index": 1}]


class TestExtractBlockToken:
    def test_thinking_block_extracts_thinking(self) -> None:
        assert _extract_block_token(KIMI_THINKING) == ("", "用")

    def test_text_block_extracts_text(self) -> None:
        assert _extract_block_token(KIMI_TEXT) == ("晚上好！", "")

    def test_mixed_blocks_extract_both(self) -> None:
        tok = '[{"thinking":"用","type":"thinking","index":0},{"text":"你好","type":"text","index":1}]'
        assert _extract_block_token(tok) == ("你好", "用")

    def test_list_input_extracts_text(self) -> None:
        assert _extract_block_token(KIMI_TEXT_LIST) == ("你好", "")

    def test_plain_string_returns_empty(self) -> None:
        # 普通文本 token 非块式 → 返回空，走原有逻辑
        assert _extract_block_token("普通文本") == ("", "")
        assert _extract_block_token("") == ("", "")

    def test_invalid_json_returns_empty(self) -> None:
        assert _extract_block_token("not json [") == ("", "")


class TestOnLlmNewToken:
    class _FakeSender:
        def __init__(self) -> None:
            self.tokens: list[str] = []
            self.thinking_counts: list[int] = []

        async def token(self, token: str) -> None:
            self.tokens.append(token)

        async def thinking_token(self, count: int) -> None:
            self.thinking_counts.append(count)

    async def _run(self, token: str) -> tuple[list[str], list[int]]:
        cb = WebSocketCallback(self._FakeSender())
        sender = cb._sender
        await cb.on_llm_new_token(token)
        return sender.tokens, sender.thinking_counts

    def test_text_block_emits_clean_token(self) -> None:
        import asyncio

        tokens, counts = asyncio.run(self._run(KIMI_TEXT))
        assert tokens == ["晚上好！"]
        assert counts == []

    def test_thinking_block_emits_count_only(self) -> None:
        import asyncio

        tokens, counts = asyncio.run(self._run(KIMI_THINKING))
        assert tokens == []
        assert counts == [1]

    def test_plain_string_emits_token(self) -> None:
        import asyncio

        tokens, counts = asyncio.run(self._run("你好"))
        assert tokens == ["你好"]
        assert counts == []

    def test_empty_token_emits_thinking_count(self) -> None:
        import asyncio

        tokens, counts = asyncio.run(self._run(""))
        assert tokens == []
        assert counts == [1]

    def test_thinking_count_accumulates(self) -> None:
        import asyncio

        cb = WebSocketCallback(self._FakeSender())
        sender = cb._sender
        asyncio.run(cb.on_llm_new_token(KIMI_THINKING))
        asyncio.run(cb.on_llm_new_token(KIMI_THINKING))
        asyncio.run(cb.on_llm_new_token(KIMI_THINKING))
        assert sender.thinking_counts == [1, 2, 3]
