"""记忆管理器构造器 — 独立于具体后端。"""

from typing import Any

from api.memory.manager.base import BaseMemoryManager
from api.memory.manager.yaml import YamlMemoryManager


class MemoryManagerBuilder:
    """记忆管理器构造器。

    所有后端使用同一建造形式，确保替换子类时调用方无需调整语法。

    Usage::

        # YAML 后端
        mm = MemoryManagerBuilder() \\
            .with_backend(YamlMemoryManager) \\
            .with_args(yaml_file="path/to/memory.yaml") \\
            .build()

        # 自定义后端
        mm = MemoryManagerBuilder() \\
            .with_backend(MyCustomManager) \\
            .with_args(arg1=...) \\
            .build()

        # 注入 LongTermMemory
        ltm = LongTermMemory(
            MemoryManagerBuilder()
            .with_backend(YamlMemoryManager)
            .with_args(yaml_file="path/to/memory.yaml")
            .build()
        )
    """

    def __init__(self) -> None:
        self._cls: type[BaseMemoryManager] = YamlMemoryManager
        self._kwargs: dict[str, Any] = {}

    def with_backend(
        self, cls: type[BaseMemoryManager]
    ) -> "MemoryManagerBuilder":
        """指定 MemoryManager 子类。"""
        self._cls = cls
        self._kwargs = {}
        return self

    def with_args(self, **kwargs: object) -> "MemoryManagerBuilder":
        """指定后端构造参数。"""
        self._kwargs = kwargs
        return self

    def build(self) -> BaseMemoryManager:
        """构造并返回 MemoryManager 实例。"""
        return self._cls(**self._kwargs)