"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 memory_v6.yaml。"""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path

from api.memory.consumer import MemoryConsumer, set_current_mm
from api.memory.manager import BaseMemoryManager
from api.memory.theme import theme_display
from api.providers.manager import get_manager
from api.session.manager import SessionState
from api.utils.logger import get_logger

_log = get_logger("ltm")


# 记忆注入标记 — retrieve_memory 节点注入的 HumanMessage 以此开头
MEMORY_INJECTION_MARKER = "【相关记忆】"


PERSONAS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "personas"
MEMORY_FILE_NAME = "memory_v6.yaml"  # V6 记忆文件；V5 的 memory.yaml 已不再读取
MEMORY_PATH = PERSONAS_DIR / MEMORY_FILE_NAME


# ── 格式化辅助 ──────────────────────────────────────────────


def _format_narrative(items: list[dict[str, str]]) -> str:
    """将 MemoryManager.show() 的输出格式化为人类可读的长记忆叙事文本。"""
    if not items:
        return ""
    by_theme: dict[str, list[dict]] = {}
    theme_order: list[str] = []
    for item in items:
        theme = item["theme"]
        by_theme.setdefault(theme, []).append(item)
        if theme not in theme_order:
            theme_order.append(theme)
    lines = ["# 长期记忆索引"]
    for theme in theme_order:
        lines.append(f"- [{theme_display(theme)}](#{theme})")
    lines.extend(["", "---", ""])
    for theme in theme_order:
        lines.append(f"## {theme_display(theme)}")
        for item in by_theme[theme]:
            lines.append(f"- {item['description']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


@functools.lru_cache(maxsize=1)
def get_narrative() -> str:
    """读取当前记忆叙事，不存在则返回空字符串。"""
    if not MEMORY_PATH.exists():
        return ""
    from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager  # noqa: PLC0415 — 避免循环导入

    mm = MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(MEMORY_PATH)).build()
    return _format_narrative(mm.show())


# ── LongTermMemory ──────────────────────────────────────────


class LongTermMemory:
    """长期记忆（LTM）核心编排器 — 后台持久化管线。

    职责：
    - **持久化** — 通过 ``start()`` / ``send_history()`` / ``stop()``
      管线将逐轮对话异步消费、提炼并写入记忆后端。

    V6 起长期记忆的**读取**不再由图内自动检索：模型按需调用 ``memory_search``
    工具（见 :mod:`api.memory.search`），本类只负责写入。

    用法::

        from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager

        ltm = LongTermMemory(
            MemoryManagerBuilder()
            .with_backend(YamlMemoryManager)
            .with_args(yaml_file="path/to/memory_v6.yaml")
            .build() # 传入选用的记忆管理器
        )

        ltm.start() # 生命周期开始

        # 持久化
        await ltm.send_history(messages)

        await ltm.stop() # 生命周期结束
    """

    def __init__(
        self,
        memory_manager: BaseMemoryManager,
    ) -> None:
        self._mm = memory_manager
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        """后台消费者协程是否正在运行。"""
        return self._consumer_task is not None and not self._consumer_task.done()

    def get_narrative(self) -> str:
        """读取当前记忆叙事，不存在则返回空字符串。"""
        items = self._mm.show()
        if not items:
            return ""
        return _format_narrative(items)

    def delete_memory(self, id: str) -> str:
        """删除指定 ID 的单条记忆，返回被删除条目的描述。"""
        return self._mm.delete(id)

    def start(self) -> None:
        """创建 asyncio.Queue、注入 _current_mm 并启动后台消费者协程。

        必须在运行中的事件循环内调用。
        内部通过 get_manager().get_default_llm() 获取 LLM，无需外部传入。
        """
        set_current_mm(self._mm)
        self._queue = asyncio.Queue()
        self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def send_history(
        self,
        turn_messages: list[dict[str, str]],
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """生产者：将本轮对话消息放入队列（非阻塞）。

        可附带 session_id 和 turn_id，供后台消费者关联到前端对话轮次。
        """
        if not turn_messages:
            return
        if self._queue is not None:
            await self._queue.put((session_id, turn_id, list(turn_messages)))
            _log.debug("queue.put session=%s turn_id=%s queue_size≈%d", session_id, turn_id, self._queue.qsize())
        else:
            _log.warning("queue is None, dropping history")

    @staticmethod
    async def _extract_session_messages(session: SessionState) -> list[dict[str, str]]:
        """从短期记忆提取全量会话消息并映射为记忆 Agent 格式。

        自动跳过以 :data:`MEMORY_INJECTION_MARKER` 开头的 HumanMessage
        （即 retrieve_memory 节点注入的【相关记忆】），避免 LTM consumer
        将记忆注入内容当作真实用户对话写入 memory_v6.yaml。
        """
        try:
            raw = await session.get_messages()
            if not raw:
                return []
        except Exception:
            return []

        role_map = {"human": "user", "ai": "assistant", "tool": "tool"}
        result: list[dict[str, str]] = []
        for m in raw:
            # 跳过注入的记忆 HumanMessage
            if (
                m.type == "human"
                and isinstance(m.content, str)
                and m.content.startswith(MEMORY_INJECTION_MARKER)
            ):
                continue
            role = role_map.get(m.type)
            if role is None:
                continue
            content = m.content
            if isinstance(content, list):
                # 多模态消息：仅提取文本，丢弃 image_url 的 base64 数据
                parts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                content = " ".join(parts) if parts else "[图片]"
            elif not isinstance(content, str):
                content = str(content)
            result.append({"role": role, "content": content})
        return result

    async def send_history_from_session(
        self,
        session: SessionState,
        turn_id: str = "",
        *,
        user_message: str = "",
        final_answer: str = "",
    ) -> None:
        """从 session 的 checkpointer 提取消息并投递到记忆队列。

        若 checkpointer 中无有效消息（如首轮对话），降级使用 user_message + final_answer。
        """
        messages = await self._extract_session_messages(session)
        if not messages and user_message and final_answer:
            messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_answer},
            ]
        await self.send_history(messages, session_id=session.session_id, turn_id=turn_id)

    async def stop(self) -> None:
        """发送 None 哨兵并等待消费者排空队列。"""
        if self._queue is not None:
            await self._queue.put(None)
            await self._consumer_task
            self._queue = None
            self._consumer_task = None

    async def _consumer_loop(self) -> None:
        """后台消费者协程：从队列取消息，交给 MemoryConsumer 处理。"""
        mgr = get_manager()
        llm = mgr.get_default_llm() if mgr is not None else None
        consumer = MemoryConsumer(llm)
        while True:
            item = await self._queue.get()
            if item is None:
                break
            session_id, turn_id, turn_messages = item
            await consumer.consume(session_id, turn_id, turn_messages)
