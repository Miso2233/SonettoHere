"""迁移 memory.yaml：将旧版 UUID key 原地迁移为短十六进制 ID。

背景：MemoryManager 早期版本用 UUID（如 a1b2c3d4-e5f6-...）作为记忆条目
的键，后改为 secrets.token_hex(4) 生成的 8 字符十六进制 ID。
_maybe_migrate_old_ids 之前在每次读取文件时内联执行，现抽离为一次性的
迁移脚本，由 upgrade.py 统一管理。

升级方式：
  python upgrade.py
  或直接：python scripts/migrations/uuid-to-hex-id.py
"""

import re
import secrets
from pathlib import Path

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_PATH = PROJECT_ROOT / "config" / "personas" / "memory.yaml"


def _generate_id() -> str:
    return secrets.token_hex(4)


def migrate() -> None:
    if not MEMORY_PATH.exists():
        print("[migrate uuid→hex] memory.yaml 不存在，跳过")
        return

    import yaml

    with MEMORY_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    old_keys = [k for k in data if UUID_PATTERN.match(k)]
    if not old_keys:
        print("[migrate uuid→hex] 幂等，无需变更")
        return

    new_data = {}
    for old_key in old_keys:
        new_key = _generate_id()
        while new_key in new_data:
            new_key = _generate_id()
        new_data[new_key] = data[old_key]

    for k, v in data.items():
        if k not in old_keys:
            new_data[k] = v

    with MEMORY_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(new_data, f, default_flow_style=False, allow_unicode=True)

    print(f"[migrate uuid→hex] 已迁移 {len(old_keys)} 个 UUID key → 短十六进制 ID")


if __name__ == "__main__":
    migrate()