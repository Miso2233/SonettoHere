"""系统提示词组装。"""

import re
from functools import lru_cache
from pathlib import Path

from memory.narrative import get_narrative
from memory.user_init import ensure_user_md

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
ANTHROPIC_SKILLS_DIR = Path(__file__).resolve().parent.parent / "anthropic_skills"


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


def _parse_frontmatter(text: str) -> dict[str, str]:
    """简易解析 YAML frontmatter，提取 name 和 description。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("name", "description"):
                meta[key] = val
    return meta


def _scan_anthropic_skills() -> str:
    """扫描 anthropic_skills/ 下所有 SKILL.md，返回元数据清单。"""
    if not ANTHROPIC_SKILLS_DIR.is_dir():
        return ""
    entries: list[str] = []
    for sk_path in sorted(ANTHROPIC_SKILLS_DIR.rglob("SKILL.md")):
        rel = sk_path.relative_to(ANTHROPIC_SKILLS_DIR).parent
        meta = _parse_frontmatter(sk_path.read_text(encoding="utf-8"))
        name = meta.get("name", rel.name)
        desc = meta.get("description", "")
        path_str = str(sk_path).replace("\\", "/")
        if desc:
            entries.append(f"- [{name}]({path_str}): {desc}")
        else:
            entries.append(f"- [{name}]({path_str})")
    if not entries:
        return ""
    lines = [
        "## 可用 Anthropic Skills",
        "以下 skill 文件存放在 `anthropic_skills/` 目录中，包含完整的任务指令和流程。",
        "当你需要执行符合上述描述的任务时，应使用文件读取工具按需读取对应 SKILL.md 的完整内容。",
        "",
        *entries,
    ]
    return "\n".join(lines)


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    """组装完整系统提示词，进程生命周期内只组装一次（LRU 缓存）。"""
    ensure_user_md()
    parts = [
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
        "",
        _scan_anthropic_skills(),
    ]
    return "\n".join(parts)


