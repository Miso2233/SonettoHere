"""Anthropic Skills & 内置工具列表 API。"""

import re
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter()

PERSONAS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "personas"
ANTHROPIC_SKILLS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "anthropic_skills"
)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """简易解析 YAML frontmatter，提取 name 和 description（支持多行 | 和 >）。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    meta: dict[str, str] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key in ("name", "description"):
                if val in ("|", ">"):
                    # 多行块标量：收集后续缩进行
                    parts: list[str] = []
                    i += 1
                    while i < len(lines) and (
                        lines[i].startswith("  ") or lines[i].startswith("\t")
                    ):
                        parts.append(lines[i].strip())
                        i += 1
                    meta[key] = " ".join(parts)
                    continue
                else:
                    meta[key] = val.strip('"').strip("'")
        i += 1
    return meta


@router.get("/skills")
async def list_skills():
    """扫描 anthropic_skills/ 下所有 SKILL.md，返回结构化列表。"""
    if not ANTHROPIC_SKILLS_DIR.is_dir():
        return {"skills": []}

    skills: list[dict[str, str]] = []
    for sk_path in sorted(ANTHROPIC_SKILLS_DIR.rglob("SKILL.md")):
        rel = sk_path.relative_to(ANTHROPIC_SKILLS_DIR).parent
        meta = _parse_frontmatter(sk_path.read_text(encoding="utf-8"))
        name = meta.get("name", str(rel))
        description = meta.get("description", "")
        path_str = str(sk_path).replace("\\", "/")
        skills.append(
            {
                "name": name,
                "description": description,
                "path": path_str,
            }
        )

    return {"skills": skills}


@router.get("/macros")
async def list_macros():
    """扫描 macros/ 下所有 MACRO.md，返回结构化列表。"""
    MACROS_DIR = (
        Path(__file__).resolve().parent.parent.parent / "macros"
    )
    if not MACROS_DIR.is_dir():
        return {"macros": []}

    macros_list: list[dict[str, str]] = []
    for mp_path in sorted(MACROS_DIR.rglob("MACRO.md")):
        rel = mp_path.relative_to(MACROS_DIR).parent
        meta = _parse_frontmatter(mp_path.read_text(encoding="utf-8"))
        name = meta.get("name", str(rel))
        description = meta.get("description", "")
        path_str = str(mp_path).replace("\\", "/")
        macros_list.append(
            {
                "name": name,
                "description": description,
                "path": path_str,
            }
        )

    return {"macros": macros_list}


@router.get("/tools")
async def list_tools(request: Request):
    """返回所有已加载的 Python 内置工具（native_tools + mcp_tools）。"""
    tools = getattr(request.app.state, "tools", [])
    return {"tools": [{"name": t.name, "description": t.description} for t in tools]}
