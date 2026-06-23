import datetime
import os
import re
import secrets
from typing import Optional

import portalocker
import yaml

MAX_DESC_LENGTH = 75
"""记忆描述最大字数限制，超过此长度的创建/更新/合并请求将被驳回。"""


def NOW() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:
    def __init__(self, description, theme, **kwargs):
        self.description = description
        self.theme = theme
        self.history = kwargs.get("history", [])
        self.latest_update_time = kwargs.get("latest_update_time", NOW())

    def update(
        self,
        reason: str,
        new_description: Optional[str] = None,
        new_theme: Optional[str] = None,
    ):
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

    def show_description_history(self) -> list[dict]:
        """返回描述历史记录及时间（从当前到最早）。

        第一项为当前 description 和 latest_update_time，
        随后从 history 中逆序取有 old_description 的条目。
        """
        result = [{"description": self.description, "time": self.latest_update_time}]
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
    ):
        self.history += another.history
        self.update(reason, merged_description, merged_theme)


class MemoryManager:
    def __init__(self, yaml_file: str = "memory.yaml"):
        self._yaml_file = yaml_file
        self._ensure_file_exists()

    _UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    def _ensure_file_exists(self) -> None:
        dir_path = os.path.dirname(self._yaml_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(self._yaml_file):
            with open(self._yaml_file, "w") as f:
                yaml.dump({}, f, default_flow_style=False, allow_unicode=True)

    def _maybe_migrate_old_ids(self) -> None:
        """将 YAML 中旧版 UUID key 原地迁移为短十六进制 ID。调用方必须已持有文件锁。"""
        with open(self._yaml_file, "r") as f:
            data = yaml.safe_load(f) or {}
        old_keys = [k for k in data if self._UUID_PATTERN.match(k)]
        if not old_keys:
            return
        new_data = {}
        for old_key in old_keys:
            new_key = self._generate_id()
            while new_key in new_data:
                new_key = self._generate_id()
            new_data[new_key] = data[old_key]
        for k, v in data.items():
            if k not in old_keys:
                new_data[k] = v
        with open(self._yaml_file, "w") as f:
            yaml.dump(new_data, f, default_flow_style=False, allow_unicode=True)
        print(f"[memory] migrated {len(old_keys)} UUID keys to short hex IDs")

    def _read_all(self) -> dict[str, "MemoryItem"]:
        """读取完整文件。调用方必须已持有文件锁。"""
        self._maybe_migrate_old_ids()
        with open(self._yaml_file, "r") as f:
            data = yaml.safe_load(f) or {}
        return {id: MemoryItem(**data[id]) for id in data}

    def _write_all(self, items: dict[str, "MemoryItem"]) -> None:
        """覆写完整文件。调用方必须已持有文件锁。"""
        data_dict = {id: item.__dict__ for id, item in items.items()}
        with open(self._yaml_file, "w") as f:
            yaml.dump(data_dict, f, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def _generate_id() -> str:
        return secrets.token_hex(4)

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

    def merge(
        self,
        id1: str,
        id2: str,
        merged_description: str,
        merged_theme: str,
        reason: str,
    ):
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            if id1 not in items or id2 not in items:
                raise ValueError(
                    f"MemoryManager: Memory items with IDs {id1} and {id2} not found"
                )
            items[id1].merge(items[id2], reason, merged_description, merged_theme)
            items.pop(id2)
            self._write_all(items)

    def update(
        self,
        id: str,
        reason: str,
        new_description: Optional[str] = None,
        new_theme: Optional[str] = None,
    ):
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

    def get_memories_grouped(self) -> dict:
        """按 theme 分组返回记忆数据，用于 Vignette 前端瀑布流展示。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
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

    def show_description_history(self, id: str) -> list[dict]:
        """返回指定条目的描述变更历史（从当前到最早）。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._read_all()
            if id not in items:
                raise ValueError(f"MemoryManager: Memory item with ID {id} not found")
            return items[id].show_description_history()
