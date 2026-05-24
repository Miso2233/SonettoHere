import datetime
import os
import uuid
from typing import Optional

import portalocker
import yaml


def NOW() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:

    def __init__(self, description, theme, **kwargs):
        self.description = description
        self.theme = theme
        self.history = kwargs.get("history", [])
        self.latest_update_time = kwargs.get("latest_update_time", NOW())

    def update(self, reason: str, new_description: Optional[str] = None, new_theme: Optional[str] = None):
        new_history = {"reason": reason}
        if new_description is not None:
            new_history["new_description"] = new_description
            new_history["old_description"] = self.description
            self.description = new_description
        if new_theme is not None:
            new_history["new_theme"] = new_theme
            new_history["old_theme"] = self.theme
            self.theme = new_theme
        new_history["old_time"] = self.latest_update_time
        self.latest_update_time = NOW()
        self.history.append(new_history)


class MemoryManager:

    def __init__(self, yaml_file: str = "memory.yaml"):
        self._yaml_file = yaml_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        dir_path = os.path.dirname(self._yaml_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(self._yaml_file):
            with open(self._yaml_file, "w") as f:
                yaml.dump({}, f, default_flow_style=False, allow_unicode=True)

    def _read_all(self) -> dict[str, 'MemoryItem']:
        """读取完整文件。调用方必须已持有文件锁。"""
        with open(self._yaml_file, "r") as f:
            data = yaml.safe_load(f) or {}
        return {id: MemoryItem(**data[id]) for id in data}

    def _write_all(self, items: dict[str, 'MemoryItem']) -> None:
        """覆写完整文件。调用方必须已持有文件锁。"""
        data_dict = {id: item.__dict__ for id, item in items.items()}
        with open(self._yaml_file, "w") as f:
            yaml.dump(data_dict, f, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def _generate_id() -> str:
        return str(uuid.uuid4())

    @property
    def _lock_path(self) -> str:
        return self._yaml_file + ".lock"

    def add(self, description: str, theme: str) -> str:
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            new_id = self._generate_id()
            items[new_id] = MemoryItem(description, theme)
            self._write_all(items)
        return new_id

    def delete(self, id: str) -> str:
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            if id not in items:
                raise ValueError(f"MemoryManager: Memory item with ID {id} not found")
            removed = items.pop(id)
            self._write_all(items)
        return removed.description

    def update(self, id: str, reason: str, new_description: Optional[str] = None, new_theme: Optional[str] = None):
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            if id not in items:
                raise ValueError(f"MemoryManager: Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._write_all(items)

    def show(self):
        """整理为大模型易于理解的形式"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            return [
                {"id": id, "description": item.description, "theme": item.theme}
                for id, item in items.items()
            ]
