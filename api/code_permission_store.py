"""代码执行权限 — YAML 持久化存储。

管理"永久允许/拒绝"的代码执行权限。
权限根据代码内容的 SHA256 哈希进行匹配。
"""

import hashlib
from pathlib import Path

import yaml

_PERMISSION_PATH = (
    Path(__file__).resolve().parent / "data" / "code_permissions.yaml"
)


def _ensure_file():
    _PERMISSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _PERMISSION_PATH.exists():
        _write([])


def _write(entries: list[dict]):
    with open(_PERMISSION_PATH, "w", encoding="utf-8") as f:
        f.write("# 代码执行权限（永久允许/拒绝）\n")
        f.write("# 编辑此文件以管理永久性权限规则。\n")
        yaml.dump({"code_permissions": entries}, f, allow_unicode=True, default_flow_style=False)


def _load() -> list[dict]:
    _ensure_file()
    try:
        with open(_PERMISSION_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("code_permissions", [])
        if not isinstance(entries, list):
            return []
        return entries
    except Exception:
        return []


def code_hash(code: str) -> str:
    """计算代码内容的 SHA256 哈希。"""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def check_permission(code: str) -> str | None:
    """检查代码是否有永久权限设置。

    Returns:
        "allow" — 永久允许
        "deny"  — 永久拒绝
        None    — 无永久设置，需用户确认
    """
    h = code_hash(code)
    for entry in _load():
        if entry.get("hash") == h:
            return entry.get("action")
    return None


def add_permission(code: str, action: str, description: str = "") -> dict:
    """添加一条永久权限记录。

    Args:
        code: 代码内容
        action: "allow" 或 "deny"
        description: 描述（可选）
    """
    _ensure_file()
    entries = _load()
    h = code_hash(code)

    for entry in entries:
        if entry.get("hash") == h:
            entry["action"] = action
            if description:
                entry["description"] = description
            _write(entries)
            return entry

    entry = {
        "hash": h,
        "code_preview": code[:200],
        "action": action,
        "description": description or "",
    }
    entries.append(entry)
    _write(entries)
    return entry


def remove_permission(index: int) -> bool:
    """按索引删除权限记录。"""
    entries = _load()
    if index < 0 or index >= len(entries):
        return False
    entries.pop(index)
    _write(entries)
    return True


def list_permissions() -> list[dict]:
    """列出所有永久权限记录。"""
    return _load()
