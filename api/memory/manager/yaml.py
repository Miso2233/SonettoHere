"""YAML 文件后端的记忆管理器实现。"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import portalocker
import yaml

from api.memory.manager.base import BaseMemoryManager, SelfCheckReport
from api.memory.manager.item import MemoryItem

MAX_DESC_LENGTH = 75
"""记忆描述最大字数限制，超过此长度的创建/更新/合并请求将被驳回。"""


class YamlMemoryManager(BaseMemoryManager):
    def __init__(self, yaml_file: str) -> None:
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

    @contextmanager
    def _write_lock(self) -> Generator[None, None, None]:
        with portalocker.Lock(self._lock_path, timeout=5):
            yield

    def self_check(self) -> SelfCheckReport:
        with portalocker.Lock(self._lock_path, timeout=5):
            yaml_path = Path(self._yaml_file)

            # 1. 文件是否可达
            if not yaml_path.exists():
                return SelfCheckReport(
                    status="FAIL",
                    issues=[f"YAML 文件不存在: {self._yaml_file}"],
                    repaired=[],
                    item_count=0,
                )

            # 2. 加载全部条目（含 YAML 解析校验）
            try:
                items = self._load_all()
            except Exception as e:
                return SelfCheckReport(
                    status="FAIL",
                    issues=[f"YAML 加载失败: {e}"],
                    repaired=[],
                    item_count=0,
                )

            # 3. 逐条校验字段完整性（介质无关）
            issues, repaired = self._validate_all_items(items)

            # 4. 有修复则写回
            if repaired:
                self._save_all(items)

            status = "FAIL" if issues else ("WARN" if repaired else "OK")

            return SelfCheckReport(
                status=status,
                issues=issues,
                repaired=repaired,
                item_count=len(items),
            )


