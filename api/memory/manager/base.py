"""记忆管理器抽象基类。"""

from abc import ABC, abstractmethod
from typing import Any


class BaseMemoryManager(ABC):
    """记忆管理器抽象接口。

    所有记忆存储后端（YAML、数据库等）均应继承此类并实现以下方法。
    """

    @abstractmethod
    def add(self, description: str, theme: str) -> str:
        """添加一条新记忆。

        Args:
            description: 记忆描述文本。
            theme: 记忆分区名。

        Returns:
            新条目的 ID。
        """
        ...

    @abstractmethod
    def delete(self, id: str) -> str:
        """删除指定 ID 的记忆条目。

        Args:
            id: 条目 ID。

        Returns:
            被删除条目的 description。

        Raises:
            ValueError: ID 不存在时抛出。
        """
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
        """将两条记忆合并为一条。

        Args:
            id1: 保留的条目 ID。
            id2: 被合并（删除）的条目 ID。
            merged_description: 合并后的描述。
            merged_theme: 合并后的分区。
            reason: 合并原因。

        Raises:
            ValueError: 任一 ID 不存在时抛出。
        """
        ...

    @abstractmethod
    def update(
        self,
        id: str,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新指定 ID 的记忆条目。

        Args:
            id: 条目 ID。
            reason: 更新原因。
            new_description: 新描述（不传则不更新）。
            new_theme: 新分区（不传则不更新）。

        Raises:
            ValueError: ID 不存在时抛出。
        """
        ...

    @abstractmethod
    def show(self) -> list[dict[str, Any]]:
        """返回所有记忆条目（大模型友好格式）。

        Returns:
            [{"id": str, "description": str, "theme": str}, ...]
        """
        ...

    @abstractmethod
    def get_memories_grouped(self) -> dict:
        """按 theme 分组返回记忆数据，用于前端展示。

        Returns:
            {"sections": [{"theme": str, "items": [...]}, ...]}
        """
        ...

    @abstractmethod
    def show_description_history(self, id: str) -> list[dict]:
        """返回指定条目的描述变更历史（从当前到最早）。

        Args:
            id: 条目 ID。

        Returns:
            [{"description": str, "time": str}, ...]

        Raises:
            ValueError: ID 不存在时抛出。
        """
        ...
