"""系统提示词组装。"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from memory.narrative import get_narrative
from memory.user_init import ensure_user_md

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"


@lru_cache(maxsize=3)
def _read_persona(filename: str) -> str:
    path = PERSONAS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _read_if_exists(filename: str) -> str:
    """读取 personas 文件，不存在返回空字符串（不走缓存）。"""
    path = PERSONAS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_system_prompt() -> str:
    """组装完整系统提示词，启动时调用一次。"""
    ensure_user_md()
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    parts = [
        f"当前时间：{now}",
        "",
        "## 行为规则",
        _read_persona("AGENTS.md"),
        "",
        "## 性格设定",
        _read_persona("SOUL.md"),
        "",
        "## 用户自述",
        _read_if_exists("USER.md"),
        "",
        "## 我对用户的记忆",
        get_narrative(),
    ]
    return "\n".join(parts)


def build_enhanced_prompt(system_prompt: str, user_input: str) -> str:
    """重新组装系统提示词，获取最新叙事和用户自述。"""
    return build_system_prompt()
