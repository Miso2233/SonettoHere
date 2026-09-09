"""长期记忆精确搜索 — 主题 + 正则命中，并沿 related 推导多级关联闭包。

纯逻辑模块（不依赖 tools），供主 Agent 的记忆搜索工具与测试复用。
输入的邻接表来自 :func:`collect_adjacency`（由记忆管理器公共只读接口构建）；
related 为无向边，闭包用多源 BFS 计算最小关联层深。
"""

import re
from collections import deque
from typing import TYPE_CHECKING, Any

from api.memory.theme import require_theme

if TYPE_CHECKING:  # pragma: no cover — 仅类型标注，避免引入运行期依赖
    from api.memory.manager.base import BaseMemoryManager


def collect_adjacency(
    memory_manager: "BaseMemoryManager",
) -> dict[str, dict[str, Any]]:
    """把记忆管理器扁平化为 ``{id: {id, theme, description, related, _sort_time}}``。

    使用公共只读 ``get_memories_grouped()``（每节含 theme、每项含 related），
    不触碰受保护的 ``_load_all``，可安全读取。
    """
    grouped = memory_manager.get_memories_grouped()
    adjacency: dict[str, dict[str, Any]] = {}
    for section in grouped.get("sections", []):
        theme = section.get("theme", "")
        for item in section.get("items", []):
            adjacency[item["id"]] = {
                "id": item["id"],
                "theme": theme,
                "description": item.get("description", ""),
                "related": list(item.get("related") or []),
                "_sort_time": item.get("_sort_time", ""),
            }
    return adjacency


def search_with_closure(
    adjacency: dict[str, dict[str, Any]],
    *,
    theme: str | None,
    regex: str,
    max_related: int = 60,
) -> dict[str, Any]:
    """按主题 + 正则搜索，并返回沿 related 推出的多级关联闭包。

    Args:
        adjacency: :func:`collect_adjacency` 的输出。
        theme: 限定主题 KEY；``None`` 表示搜索全部主题。
        regex: 对 description 做 ``re.search`` 的正则。
        max_related: 关联条目返回上限（超出截断并在结果中标记）。

    Returns:
        形如 ``{"theme": ..., "matched": [...], "related": [...],
        "related_total": int, "truncated": bool}``。matched 按 _sort_time 降序；
        related 为去重、不含命中集、附 ``depth``（最小关联层深）的多级条目。

    Raises:
        ValueError: theme 非空但非法时。
        re.error: regex 非法时。
    """
    if theme is not None:
        require_theme(theme, who="memory_search(theme)")
    compiled = re.compile(regex)

    candidates = list(adjacency.values())
    if theme is not None:
        candidates = [item for item in candidates if item["theme"] == theme]
    matched = [item for item in candidates if compiled.search(item["description"])]
    matched.sort(key=lambda item: item["_sort_time"], reverse=True)

    matched_ids = {item["id"] for item in matched}
    visited: set[str] = set(matched_ids)
    depth: dict[str, int] = {mid: 0 for mid in matched_ids}
    frontier: deque[str] = deque(matched_ids)

    related: list[dict[str, Any]] = []
    while frontier:
        current = frontier.popleft()
        for rid in adjacency[current].get("related", []):
            if rid not in adjacency or rid in visited:  # 跳过悬空/已访问
                continue
            visited.add(rid)
            depth[rid] = depth[current] + 1
            entry = dict(adjacency[rid])
            entry["depth"] = depth[rid]
            related.append(entry)
            frontier.append(rid)

    related_total = len(related)
    truncated = related_total > max_related
    if truncated:
        related = related[:max_related]

    return {
        "theme": theme,
        "matched": matched,
        "related": related,
        "related_total": related_total,
        "truncated": truncated,
    }


def render_search_result(result: dict[str, Any]) -> str:
    """把搜索结果格式化为人类/大模型友好的多行文本。"""
    matched = result.get("matched", [])
    related = result.get("related", [])
    if not matched and not related:
        return "（无匹配记忆）"

    lines: list[str] = []
    lines.append(f"## 匹配条目（{len(matched)}）")
    if matched:
        for item in matched:
            lines.append(f"  [{item['id']}] ({item['theme']}) {item['description']}")
    else:
        lines.append("  （无）")

    lines.append(f"## 关联条目（多级，{len(related)}）")
    if related:
        for item in related:
            lines.append(
                f"  [{item['id']}] ({item['theme']}) {item['description']}"
                f"   ← 第 {item['depth']} 级关联"
            )
    else:
        lines.append("  （无）")

    if result.get("truncated"):
        remaining = result.get("related_total", len(related)) - len(related)
        lines.append(f"（已截断，另有 {remaining} 条关联未列出）")
    return "\n".join(lines)
