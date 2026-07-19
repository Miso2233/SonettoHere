"""YAML 文件后端的记忆管理器实现。"""

from pathlib import Path

import portalocker
import yaml

from api.memory.manager.base import BaseMemoryManager, MemoryItem

MAX_DESC_LENGTH = 75
"""记忆描述最大字数限制，超过此长度的创建/更新/合并请求将被驳回。"""


class YamlMemoryManager(BaseMemoryManager):
    def __init__(self, yaml_file: str):
        self._yaml_file = yaml_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        yaml_path = Path(self._yaml_file)
        dir_path = yaml_path.parent
        if str(dir_path):
            dir_path.mkdir(parents=True, exist_ok=True)
        if not yaml_path.exists():
            with yaml_path.open("w", encoding="utf-8") as f:
                yaml.dump({}, f, default_flow_style=False, allow_unicode=True)

    def _load_all(self) -> dict[str, MemoryItem]:
        """读取完整文件。调用方必须已持有文件锁。"""
        yaml_path = Path(self._yaml_file)
        with yaml_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {id: MemoryItem(**data[id]) for id in data}

    def _save_all(self, items: dict[str, MemoryItem]) -> None:
        """覆写完整文件。调用方必须已持有文件锁。"""
        data_dict = {id: item.__dict__ for id, item in items.items()}
        yaml_path = Path(self._yaml_file)
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.dump(data_dict, f, default_flow_style=False, allow_unicode=True)

    @property
    def _lock_path(self) -> str:
        return self._yaml_file + ".lock"

    def add(self, description: str, theme: str) -> str:
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            new_id = self._generate_id()
            items[new_id] = MemoryItem(description, theme)
            self._save_all(items)
        return new_id

    def delete(self, id: str) -> str:
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id not in items:
                raise ValueError(f"YamlMemoryManager: Memory item with ID {id} not found")
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
    ):
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(
                    f"YamlMemoryManager: Memory items with IDs {id1} and {id2} not found"
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
    ):
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id not in items:
                raise ValueError(f"YamlMemoryManager: Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._save_all(items)


class MemoryManagerBuilder:
    """记忆管理器构造器。

    所有后端使用同一建造形式，确保替换子类时调用方无需调整语法。

    Usage::

        # YAML 后端
        mm = MemoryManagerBuilder() \\
            .with_backend(YamlMemoryManager, yaml_file="path/to/memory.yaml") \\
            .build()

        # 自定义后端
        mm = MemoryManagerBuilder() \\
            .with_backend(MyCustomManager, arg1=...) \\
            .build()

        # 注入 LongTermMemory
        ltm = LongTermMemory(
            MemoryManagerBuilder()
            .with_backend(YamlMemoryManager, yaml_file="path/to/memory.yaml")
            .build()
        )
    """

    def __init__(self) -> None:
        self._cls: type[BaseMemoryManager] = YamlMemoryManager
        self._kwargs: dict = {}

    def with_backend(
        self, cls: type[BaseMemoryManager], **kwargs: object
    ) -> "MemoryManagerBuilder":
        """指定 MemoryManager 子类及其构造参数。"""
        self._cls = cls
        self._kwargs = kwargs
        return self

    def build(self) -> BaseMemoryManager:
        """构造并返回 MemoryManager 实例。"""
        return self._cls(**self._kwargs)
