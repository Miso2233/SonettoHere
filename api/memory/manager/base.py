"""记忆管理器抽象基类。"""

import datetime
import secrets
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, TypedDict


def _now() -> str:
    """返回当前时间的格式化字符串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:
    """单条记忆的数据模型。不依赖具体存储后端。"""

    def __init__(
        self,
        description: str,
        theme: str,
        history: list[dict[str, str]] | None = None,
        latest_update_time: str | None = None,
        hit: int = 0,
    ) -> None:
        self.description = description
        self.theme = theme
        self.history = history if history is not None else []
        self.latest_update_time = latest_update_time if latest_update_time is not None else _now()
        self.hit = hit

    def update(
        self,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新记忆内容并记录历史。"""
        new_history: dict[str, str] = {"reason": reason}
        if new_description is not None:
            new_history["new_description"] = new_description
            new_history["old_description"] = self.description
            self.description = new_description
        if new_theme is not None:
            new_history["new_theme"] = new_theme
            new_history["old_theme"] = self.theme
            self.theme = new_theme
        new_history["old_time"] = self.latest_update_time
        self.latest_update_time = _now()
        self.history.append(new_history)

    def show_description_history(self) -> list[dict[str, str]]:
        """返回描述变更历史（从当前到最早）。"""
        result: list[dict[str, str]] = [
            {"description": self.description, "time": self.latest_update_time}
        ]
        for entry in reversed(self.history):
            if "old_description" in entry:
                result.append(
                    {
                        "description": entry["old_description"],
                        "time": entry["old_time"],
                    }
                )
        return result

    def merge(
        self,
        another: "MemoryItem",
        reason: str,
        merged_description: str,
        merged_theme: str,
    ) -> None:
        """合并另一条记忆的历史到本条。"""
        self.history += another.history
        self.update(reason, merged_description, merged_theme)


class SelfCheckReport(TypedDict):
    """``self_check()`` 的返回类型。"""

    status: str
    """``"OK"`` | ``"WARN"`` | ``"FAIL"``"""
    issues: list[str]
    """不可自动修复的问题列表。"""
    repaired: list[str]
    """已自动修复的问题描述列表。"""
    item_count: int
    """有效条目总数。"""


class BaseMemoryManager(ABC):
    """记忆管理器抽象接口。

    所有记忆存储后端（YAML、数据库等）均应继承此类。
    子类只需实现 _load_all()、_save_all()、_write_lock() 三个原语，
    即可继承 add / delete / update / merge 等公共方法。
    """

    # ── 抽象存储原语 ────────────────────────────────────────

    @abstractmethod
    def _load_all(self) -> dict[str, MemoryItem]:
        """读取全部条目。子类须自行保证并发安全。"""
        ...

    @abstractmethod
    def _save_all(self, items: dict[str, MemoryItem]) -> None:
        """覆写全部条目。子类须自行保证并发安全。"""
        ...

    @abstractmethod
    def _write_lock(self) -> AbstractContextManager[None]:
        """写操作的锁上下文。子类必须覆盖以实现并发控制。"""
        ...

    # ── 启动自检 ────────────────────────────────────────────

    @abstractmethod
    def self_check(self) -> SelfCheckReport:
        """启动自检，验证存储后端状态正常。

        子类应检查：
        - 后端存储介质是否可达、可读写
        - 所有数据条目字段是否完整（description / theme / history / latest_update_time / hit）
        - 必要时自动修复可修复的问题（如空字符串、类型异常）

        Returns:
            SelfCheckReport 包含 status（"OK" / "WARN" / "FAIL"）、
            issues（不可修复问题）、repaired（已修复问题）、item_count（有效条目数）。
        """
        ...

    def _validate_all_items(
        self, items: dict[str, MemoryItem]
    ) -> tuple[list[str], list[str]]:
        """校验所有条目的 MemoryItem 字段完整性，返回 (issues, repaired)。

        介质无关，子类的 self_check 可直接调用此方法以复用校验逻辑。
        """
        issues: list[str] = []
        repaired: list[str] = []
        for id, item in items.items():
            if not isinstance(item.description, str) or not item.description.strip():
                item.description = "(空)"
                repaired.append(f"条目 {id}: description 为空，已重置")

            if not isinstance(item.theme, str) or not item.theme.strip():
                item.theme = "(未分类)"
                repaired.append(f"条目 {id}: theme 为空，已重置")

            if not isinstance(item.history, list):
                item.history = []
                repaired.append(f"条目 {id}: history 非列表，已重置")

            if (
                not isinstance(item.latest_update_time, str)
                or not item.latest_update_time.strip()
            ):
                item.latest_update_time = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                repaired.append(f"条目 {id}: latest_update_time 无效，已重置")

            if not isinstance(item.hit, int) or item.hit < 0:
                item.hit = 0
                repaired.append(f"条目 {id}: hit 无效，已重置为 0")

        return issues, repaired

    # ── 默认 ID 生成 ────────────────────────────────────────

    def _generate_id(self) -> str:
        """生成唯一短 ID。子类可 override。"""
        return secrets.token_hex(4)

    # ── 公共查询方法（基于 _load_all） ───────────────────────

    def show(self) -> list[dict[str, Any]]:
        """返回所有记忆条目（大模型友好格式）。"""
        items = self._load_all()
        return [
            {"id": id, "description": item.description, "theme": item.theme}
            for id, item in items.items()
        ]

    def show_description_history(self, id: str) -> list[dict[str, str]]:
        """返回指定条目的描述变更历史（从当前到最早）。

        Raises:
            ValueError: ID 不存在时抛出。
        """
        items = self._load_all()
        if id not in items:
            raise ValueError(f"Memory item with ID {id} not found")
        return items[id].show_description_history()

    def get_memories_grouped(self) -> dict[str, Any]:
        """按 theme 分组返回记忆数据，用于 Vignette 前端瀑布流展示。"""
        items = self._load_all()
        groups: dict[str, list[dict]] = {}
        for id, item in items.items():
            theme = item.theme
            if theme not in groups:
                groups[theme] = []
            groups[theme].append(
                {
                    "id": id,
                    "description": item.description,
                    "history": item.show_description_history(),
                    "_sort_time": item.latest_update_time,
                }
            )
        # 每组内按更新时间倒序
        for theme in groups:
            groups[theme].sort(key=lambda x: x["_sort_time"], reverse=True)
            for entry in groups[theme]:
                del entry["_sort_time"]
        # 分区间按条目数降序
        sections = [
            {"theme": theme, "items": items}
            for theme, items in sorted(
                groups.items(), key=lambda x: len(x[1]), reverse=True
            )
        ]
        return {"sections": sections}

    # ── CRUD 方法（基于 _load_all / _save_all / _write_lock） ──

    def add(self, description: str, theme: str) -> str:
        """添加一条新的记忆条目。"""
        with self._write_lock():
            items = self._load_all()
            new_id = self._generate_id()
            items[new_id] = MemoryItem(description, theme)
            self._save_all(items)
        return new_id

    def delete(self, id: str) -> str:
        """删除指定 ID 的记忆条目，返回被删除条目的描述。"""
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            removed = items.pop(id)
            self._save_all(items)
        return removed.description

    def merge(
        self,
        id1: str,
        id2: str,
        merged_description: str,
        merged_theme: str,
        reason: str,
    ) -> None:
        """将两条记忆合并为一条，id1 保留，id2 被删除。"""
        with self._write_lock():
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(
                    f"Memory items with IDs {id1} and {id2} not found"
                )
            items[id1].merge(items[id2], reason, merged_description, merged_theme)
            items.pop(id2)
            self._save_all(items)

    def update(
        self,
        id: str,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新指定记忆条目的内容和/或主题。"""
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._save_all(items)

    def hit(self, id: str) -> int:
        """将指定记忆的 hit 计数加一，返回新的计数。"""
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            items[id].hit += 1
            self._save_all(items)
            return items[id].hit
