"""系统提示词组装。"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from memory.long_term import retrieve_long_term_context
from memory.preference import get_stable_preferences

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"


@lru_cache(maxsize=3)
def _read_persona(filename: str) -> str:
    path = PERSONAS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_system_prompt() -> str:
    """组装完整系统提示词，启动时调用一次即可。"""
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
        "## 固定记忆",
        _read_persona("MEMORY.md"),
    ]
    return "\n".join(parts)


def build_enhanced_prompt(system_prompt: str, user_input: str) -> str:
    """检索长期记忆和用户偏好，拼接增强后的系统提示词。"""
    prompt = system_prompt
    try:
        retrieved = retrieve_long_term_context(user_input, top_k=10)
        stable = get_stable_preferences()

        if retrieved.get("error_rules"):
            rules = "\n".join(
                f"- {r.get('correction', r.get('mistake', str(r)))}"
                for r in retrieved["error_rules"][:5]
            )
            prompt += f"\n\n## 错误规避规则\n{rules}"
        if retrieved.get("preference_rules"):
            prefs = "\n".join(
                f"- {p.get('habit', str(p))}"
                for p in retrieved["preference_rules"][:5]
            )
            prompt += f"\n\n## 用户偏好\n{prefs}"
        if stable:
            lines = [f"- {k} = {v.get('value', '')}" for k, v in stable.items()]
            prompt += f"\n\n## 稳定偏好\n" + "\n".join(lines[:5])
    except Exception:
        pass
    return prompt
