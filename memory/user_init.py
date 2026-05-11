"""首次运行初始化 — 从 example 文件复制用户自述。"""

import shutil
from pathlib import Path

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"


def ensure_user_md() -> None:
    """若 USER.md 不存在，从 USER.example.md 复制。"""
    user_md = PERSONAS_DIR / "USER.md"
    example_md = PERSONAS_DIR / "USER.example.md"
    if not user_md.exists() and example_md.exists():
        shutil.copy2(example_md, user_md)
