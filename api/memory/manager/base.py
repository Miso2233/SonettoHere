"""记忆管理器抽象基类。"""

import datetime
import secrets
from abc import ABC, abstractmethod
from typing import Any


def _now() -> str:
    """返回当前时间的格式化字符串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:
    """单条记忆的数据模型。不依赖具体存储后端。"""

    def __init__(self, description: str, theme: str, **kwargs: Any) -> None:
        self.description = description
        self.theme = theme
        self.history: list[dict] = kwargs.get("history", [])
        self.latest_update_time: str = kwargs.get("latest_update_time", _now())

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


class BaseMemoryManager(ABC):
    """记忆管理器抽象接口。

    所有记忆存储后端（YAML、数据库等）均应继承此类。
    子类只需实现 _load_all() 和 _save_all() 两个原语，
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

    def get_memories_grouped(self) -> dict:
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

    # ── 抽象 CRUD 方法（子类可 override 以优化） ─────────────

    @abstractmethod
    def add(self, description: str, theme: str) -> str:
        ...

    @abstractmethod
    def delete(self, id: str) -> str:
        ...

    @abstractmethod
    def merge(
        self,
        id1: str,
        id2: str,
        merged_description: str,
        merged_theme: str,
        reason: str,
    ) -> None:
        ...

    @abstractmethod
    def update(
        self,
        id: str,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        ...
