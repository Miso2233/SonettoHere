"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 memory.yaml。"""

from __future__ import annotations

import asyncio
import functools
from enum import Enum
from pathlib import Path

from api.memory.consumer import MemoryConsumer, set_current_mm
from api.memory.llm_retriever import LLMRetriever
from api.memory.manager import BaseMemoryManager
from api.memory.mechanical_retriever import MechanicalRetriever
from api.providers.manager import get_manager
from api.session.manager import SessionState, session_manager
from api.utils.logger import get_logger

_log = get_logger("ltm")


# 记忆注入标记 — retrieve_memory 节点注入的 HumanMessage 以此开头
MEMORY_INJECTION_MARKER = "【相关记忆】"


PERSONAS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "memory.yaml"


# ── 检索模式枚举 ─────────────────────────────────────


class RetrievalMode(Enum):
    """记忆检索模式。

    Attributes:
        LLM:        LLM 语义检索（默认，当前生产方案）
        MECHANICAL: BM25 机械检索（零 LLM 调用，毫秒级）
    """
    LLM = "llm"
    MECHANICAL = "mech"


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
        lines.append(f"- [{theme}](#{theme})")
    lines.extend(["", "---", ""])
    for theme in theme_order:
        lines.append(f"## {theme}")
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
    """长期记忆（LTM）核心编排器 — 检索 + 后台持久化管线。

    职责：
    - **检索** — 通过 :meth:`get_related_memory_from` 按模式（LLM 语义 / BM25 机械）
      从记忆库中召回相关条目。
    - **持久化** — 通过 ``start()`` / ``send_history()`` / ``stop()``
      管线将逐轮对话异步消费、提炼并写入记忆后端。

    用法::

        from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager

        ltm = LongTermMemory(
            MemoryManagerBuilder()
            .with_backend(YamlMemoryManager)
            .with_args(yaml_file="path/to/memory.yaml")
            .build() # 传入选用的记忆管理器
        )

        ltm.start() # 生命周期开始

        # 检索
        results = ltm.get_related_memory_from("塔罗牌重构", mode=RetrievalMode.LLM)

        # 持久化
        await ltm.send_history(messages)

        await ltm.stop() # 生命周期结束
    """

    def __init__(
        self,
        memory_manager: BaseMemoryManager,
    ) -> None:
        self._mm = memory_manager
        self._llm_retriever = LLMRetriever(memory_manager)
        self._mechanical_retriever = MechanicalRetriever()
        self._mechanical_retriever.build_index(self._mm.show())
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

    def get_related_memory_from(
        self, prompt: str, mode: RetrievalMode = RetrievalMode.LLM
    ) -> list[dict[str, str]]:
        """根据查询提示检索相关记忆条目。

        通过 ``mode`` 参数选择检索策略：

        - ``RetrievalMode.LLM`` → :meth:`_retrieve_llm`（LLM 语义检索）
        - ``RetrievalMode.MECHANICAL`` → :meth:`_retrieve_mechanical`（BM25 机械检索）

        两种路径的返回格式均为 ``[{id, description, theme}, ...]``。

        Args:
            prompt: 用户查询文本。
            mode: 检索模式，默认 LLM 语义检索。
        """
        match mode:
            case RetrievalMode.MECHANICAL:
                return self._retrieve_mechanical(prompt)
            case RetrievalMode.LLM:
                return self._retrieve_llm(prompt)
            case _:
                raise ValueError("未定义的记忆提取模式")

    def _retrieve_llm(self, prompt: str) -> list[dict[str, str]]:
        """LLM 语义检索：委托给 LLMRetriever。"""
        return self._llm_retriever.retrieve(prompt)

    def _retrieve_mechanical(self, prompt: str) -> list[dict[str, str]]:
        """BM25 机械检索：零 LLM 调用，毫秒级匹配。"""
        if self._mechanical_retriever.dirty:
            self._mechanical_retriever.build_index(self._mm.show())
        return self._mechanical_retriever.get_related_memory_from(prompt)

    async def get_related_memory_from_async(
        self, prompt: str, mode: RetrievalMode = RetrievalMode.LLM
    ) -> list[dict[str, str]]:
        """异步检索相关记忆条目（可取消）。

        与 :meth:`get_related_memory_from` 功能相同，但：
        - LLM 模式使用 ``ainvoke``，支持 ``asyncio.Task.cancel()`` 中断
        - 机械模式仍为同步（BM25 毫秒级，无需取消）
        """
        match mode:
            case RetrievalMode.LLM:
                return await self._llm_retriever.aretrieve(prompt)
            case RetrievalMode.MECHANICAL:
                return self._retrieve_mechanical(prompt)
            case _:
                raise ValueError("未定义的记忆提取模式")

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
        将记忆注入内容当作真实用户对话写入 memory.yaml。
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
