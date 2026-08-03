"""工作坊（Studio）— 将 studios/*.yaml 渲染为系统提示词附件的 Markdown 段落。

渲染由声明式 spec（STUDIO_SPEC）驱动：新增/调整字段只需改声明，无需改逻辑。
字段提取部分高度可扩展：支持顶层与 ``body.*`` 等任意点路径嵌套。
"""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

from api.utils.logger import get_logger

_log = get_logger("studio")

STUDIOS_DIR = Path(__file__).resolve().parent.parent / "studios"

RenderKind = Literal["text", "code", "list", "keyval", "join"]


@dataclass(frozen=True)
class StudioFieldSpec:
    """声明式字段 spec：描述 YAML 中一个字段如何渲染为 Markdown 段落。

    Attributes:
        key:       点路径（如 ``"body.workflow"``），在 YAML dict 中取值。
        label:     段落 Markdown 标题（如 ``## 工作流程``）。
        kind:      渲染形态：
                     text   — 字符串，渲染为段落
                     code   — 字符串，渲染为围栏代码块
                     list   — 列表；元素为 str → ``- x``；元素为 dict
                               → 用 item_key / item_note 提取
                     keyval — dict → ``- k: v`` 列表
                     join   — 标量列表 → 单行（join_sep 分隔）
        heading:   标题级别（默认 2）。
        item_key:  kind="list" 且元素为 dict 时，作为列表项文本的键。
        item_note: kind="list" 且元素为 dict 时，作为括号附注的键。
        join_sep:  kind="join" 的分隔符。
    """
    key: str
    label: str
    kind: RenderKind
    heading: int = 2
    item_key: str | None = None
    item_note: str | None = None
    join_sep: str = "、"


# ── 声明式 spec：新增字段 = 在此加一行 ──────────────────────────
STUDIO_SPEC: tuple[StudioFieldSpec, ...] = (
    StudioFieldSpec(key="description", label="简介", kind="text"),
    StudioFieldSpec(key="role", label="角色定位", kind="text"),
    StudioFieldSpec(key="environment", label="工作环境", kind="text"),
    StudioFieldSpec(key="folders", label="知识库文件夹", kind="list",
                    item_key="path", item_note="note"),
    StudioFieldSpec(key="tools", label="可用工具", kind="join"),
    StudioFieldSpec(key="meta", label="元信息", kind="keyval"),
    StudioFieldSpec(key="body.structure", label="目录结构", kind="code"),
    StudioFieldSpec(key="body.workflow", label="工作流程", kind="list"),
    StudioFieldSpec(key="body.rules", label="工作规则", kind="list"),
    StudioFieldSpec(key="body.notes", label="注意事项", kind="list"),
)


@dataclass(frozen=True)
class StudioInfo:
    """供 REST 枚举返回的 studio 元信息。"""
    name: str
    description: str
    filename: str


def _get_path(data: dict[str, Any], dotted: str) -> Any:
    """按点路径取值（支持任意嵌套 dict），路径不存在返回 None。"""
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_studio_file(filepath: Path) -> dict[str, Any] | None:
    """读取单个 YAML；文件缺失/解析失败/非 dict 根 → None。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _iter_studio_data() -> Iterator[tuple[Path, dict[str, Any]]]:
    """按文件名排序遍历所有合法 studio（确定性；同名时先排序者优先）。"""
    if not STUDIOS_DIR.is_dir():
        return
    for fpath in sorted(STUDIOS_DIR.glob("*.yaml")):
        data = load_studio_file(fpath)
        if data is not None:
            yield fpath, data


def load_all_studios() -> list[StudioInfo]:
    """枚举 studios/ 下所有含非空 name 的 studio（供 REST 与前端下拉）。"""
    result: list[StudioInfo] = []
    seen: dict[str, str] = {}
    for fpath, data in _iter_studio_data():
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if name in seen:
            _log.warning("studio name 冲突: %s 与 %s 均使用 name=%r，采用先排序者",
                         seen[name], fpath.name, name)
            continue
        seen[name] = fpath.name
        desc = data.get("description", "")
        result.append(StudioInfo(
            name=name,
            description=desc if isinstance(desc, str) else str(desc),
            filename=fpath.name,
        ))
    return result


def render_studio(
    data: dict[str, Any],
    spec: tuple[StudioFieldSpec, ...] = STUDIO_SPEC,
) -> str:
    """把已解析 dict 渲染为 Markdown 段落，首行 ``## 工作坊：<name>``。"""
    sections: list[str] = []
    for s in spec:
        value = _get_path(data, s.key)
        rendered = _render_field(s, value)
        if rendered:
            sections.append(rendered)
    if not sections:
        return ""
    name = data.get("name")
    title = f"## 工作坊：{name}" if isinstance(name, str) and name else "## 工作坊：未命名"
    return "\n\n".join([title, *sections])


def _render_field(spec: StudioFieldSpec, value: Any) -> str:
    if value is None:
        return ""
    body = _render_kind(spec.kind, value, spec)
    if not body:
        return ""
    heading = "#" * spec.heading
    return f"{heading} {spec.label}\n{body}"


def _render_kind(kind: RenderKind, value: Any, spec: StudioFieldSpec) -> str:
    match kind:
        case "text":
            return str(value).strip()
        case "code":
            return "```\n" + str(value).rstrip("\n") + "\n```"
        case "list":
            return _render_list(value, spec)
        case "keyval":
            return _render_keyval(value)
        case "join":
            if isinstance(value, list):
                items = [str(x) for x in value if x]
                return spec.join_sep.join(items) if items else ""
            return ""
    return ""


def _render_list(value: Any, spec: StudioFieldSpec) -> str:
    if not isinstance(value, list):
        return ""
    lines: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = item.get(spec.item_key, "") if spec.item_key else ""
            note = item.get(spec.item_note, "") if spec.item_note else ""
            text_s = text if isinstance(text, str) else str(text or "")
            note_s = note if isinstance(note, str) else str(note or "")
            lines.append(f"- {text_s}（{note_s}）" if note_s else f"- {text_s}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _render_keyval(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return "\n".join(
        f"- {k}: {v}" for k, v in value.items() if v is not None and v != ""
    )


def render_studio_by_name(name: str | None) -> str:
    """按 name 渲染 studio 为 Markdown；未选中/缺失/解析失败返回空串。

    每次现读文件（不缓存），编辑即时生效。与 build_system_prompt 的
    ``@lru_cache(maxsize=1)`` 无关——studio 是独立附加段，共享前缀缓存不受影响。
    """
    if not name:
        return ""
    for fpath, data in _iter_studio_data():
        n = data.get("name")
        if isinstance(n, str) and n == name:
            return render_studio(data)
        # 回退：文件名 stem 与 name 一致时也命中
        if fpath.stem == name:
            return render_studio(data)
    return ""
