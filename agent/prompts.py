"""系统提示词组装。"""

import re
from functools import lru_cache
from pathlib import Path

from agent.studio import render_studio_by_name
from api.memory.user_init import ensure_user_md

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
ANTHROPIC_SKILLS_DIR = Path(__file__).resolve().parent.parent / "anthropic_skills"
MACROS_DIR = Path(__file__).resolve().parent.parent / "macros"


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


def _scan_macros() -> str:
    """扫描 macros/ 下所有 MACRO.md，返回元数据清单。"""
    if not MACROS_DIR.is_dir():
        return ""
    entries: list[str] = []
    for mp_path in sorted(MACROS_DIR.rglob("MACRO.md")):
        rel = mp_path.relative_to(MACROS_DIR).parent
        meta = _parse_frontmatter(mp_path.read_text(encoding="utf-8"))
        name = meta.get("name", rel.name)
        desc = meta.get("description", "")
        path_str = str(mp_path).replace("\\", "/")
        if desc:
            entries.append(f"- [{name}]({path_str}): {desc}")
        else:
            entries.append(f"- [{name}]({path_str})")
    if not entries:
        return ""
    lines = [
        "## 可用宏",
        "以下宏文件存放在 `macros/` 目录中，包含可复用的指令片段。",
        "当你需要执行符合上述描述的任务时，应使用文件读取工具按需读取对应 MACRO.md 的完整内容。",
        "",
        *entries,
    ]
    return "\n".join(lines)


def get_system_prompt_parts(studio_name: str | None = None) -> list[dict]:
    """返回系统提示词的各组成部分（含标题+内容），用于 token 细分展示。

    每个元素::
        {"key": str, "label": str, "content": str}

    ``studio_name`` 非空且对应工作坊段落存在时，末尾追加「工作坊」部分。
    """
    ensure_user_md()
    parts = [
        {"key": "behavior_rules", "label": "系统行为规则",
         "content": "## 行为规则\n" + _read_persona("AGENTS.md")},
        {"key": "personality", "label": "性格人设",
         "content": "## 性格设定\n" + _read_persona("SOUL.md")},
        {"key": "user_self_report", "label": "用户自述",
         "content": "## 用户自述\n" + _read_if_exists("USER.md")},
        {"key": "skills", "label": "Skills 清单",
         "content": _scan_anthropic_skills()},
        {"key": "macros", "label": "宏清单",
         "content": _scan_macros()},
    ]
    if studio_name:
        studio_section = render_studio_by_name(studio_name)
        if studio_section:
            parts.append({"key": "studio", "label": "工作坊", "content": studio_section})
    return parts


# 记忆工具使用指引 — 主 Agent 系统提示词中的记忆读取说明。
# 每轮作答前必须先用 memory_search 依据用户输入查询相关记忆（工具触发式回忆，
# 取代旧版图内自动注入）；例外仅在“用户明确不需要”或“本轮未发放该工具（失忆模式）”。
# 历史遗留的【相关记忆】摘要仍可作为背景。
_MEMORY_GUIDE = (
    "你的长期记忆库会持久记录与用户的过往对话、偏好、项目决定与重要时刻，"
    "但它不会自动注入对话。每轮用户消息到达后、开始作答前，你必须先调用 "
    "memory_search 工具，依据用户当前输入查询相关记忆，再把查到的记忆当作背景依据回答"
    "（该工具只读，不修改记忆）。除非满足以下任一例外，否则不得跳过这次查询：\n"
    "- 用户明确表示不需要回忆（如“不用查记忆”等）；\n"
    "- 本轮未发放该工具（失忆模式）——此时你无法读取长期记忆，也不要假装已查阅。\n"
    "查询要点：\n"
    "- 用“主题 KEY + 描述关键词”的组合尽量一次命中；无结果时放宽关键词或换正则再试 1–2 次；\n"
    "- 命中后沿多级 related 关联理解上下文，但回答须基于真实检索内容、不要编造；\n"
    "- 确实检索不到时据实说明“未在记忆中查到相关内容”，不要用想象补全。\n"
    "- 在工具调用的轮次中，也可以查询记忆作为背景资料补充"
)


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
        "## 记忆工具使用指引",
        _MEMORY_GUIDE,
        "",
        _scan_anthropic_skills(),
        "",
        _scan_macros(),
    ]
    return "\n".join(parts)
