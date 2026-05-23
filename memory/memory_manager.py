import datetime
import os
import uuid
from typing import Optional

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
        self._memory_items: dict[str, MemoryItem] = {}

    def load_yaml(self) -> None:
        if not os.path.exists(self._yaml_file):
            with open(self._yaml_file, "w") as f:
                yaml.dump({}, f, default_flow_style=False, allow_unicode=True)
        with open(self._yaml_file, "r") as f:
            data = yaml.safe_load(f)
            if not data:
                return
            self._memory_items = {id: MemoryItem(**data[id]) for id in data}

    def save_yaml(self) -> None:
        with open(self._yaml_file, "w") as f:
            data_dict = {id: data.__dict__ for id, data in self._memory_items.items()}
            yaml.dump(data_dict, f, default_flow_style=False, allow_unicode=True)

    def __enter__(self):
        self.load_yaml()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_yaml()

    @staticmethod
    def _generate_id() -> str:
        return str(uuid.uuid4())

    def add(self, description: str, theme: str) -> str:
        new_id = self._generate_id()
        self._memory_items[new_id] = MemoryItem(description, theme)
        return new_id

    def delete(self, id: str) -> str:
        if id not in self._memory_items:
            raise ValueError(f"MemoryManager: Memory item with ID {id} not found")
        removed = self._memory_items.pop(id)
        return removed.description

    def update(self, id: str, reason: str, new_description: Optional[str] = None, new_theme: Optional[str] = None):
        if id not in self._memory_items:
            raise ValueError(f"MemoryManager: Memory item with ID {id} not found")
        self._memory_items[id].update(reason, new_description, new_theme)

    def show(self):
        """整理为大模型易于理解的形式"""
        out = [
            {
                "id": id,
                "description": item.description,
                "theme": item.theme
            }
            for id, item in
            self._memory_items.items()
        ]
        return out
