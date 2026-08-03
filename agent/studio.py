"""工作坊（Studio）— 将 studios/*.yaml 渲染为系统提示词附件的 Markdown 段落。

渲染由声明式 spec（STUDIO_SPEC）驱动：新增/调整字段只需改声明，无需改逻辑。
字段提取部分高度可扩展：支持顶层与 ``body.*`` 等任意点路径嵌套。
"""

import os
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
        key:        点路径（如 ``"body.workflow"``），在 YAML dict 中取值。
        label:      段落 Markdown 标题（如 ``## 工作流程``）。
        kind:       渲染形态：
                      text   — 字符串，渲染为段落
                      code   — 字符串，渲染为围栏代码块
                      list   — 列表；元素为 str → ``- x``；元素为 dict
                                → 用 item_key / item_note 提取
                      keyval — dict → ``- k: v`` 列表
                      join   — 标量列表 → 单行（"、" 分隔）
        description: 标题之后、内容之前的正文形式说明文本（默认空）。
        empty_text:  字段缺失或渲染为空时的占位文本（默认（无）；
                     设为空串可恢复「整段跳过」）。
        item_key:   kind="list" 且元素为 dict 时，作为列表项文本的键。
        item_note:  kind="list" 且元素为 dict 时，作为换行附注的键。
    """
    key: str
    label: str
    kind: RenderKind
    description: str = ""
    empty_text: str = "（无）"
    item_key: str | None = None
    item_note: str | None = None


# ── 声明式 spec：新增字段 = 在此加一行 ──────────────────────────
STUDIO_SPEC: tuple[StudioFieldSpec, ...] = (
    StudioFieldSpec(key="description", label="简介", kind="text"),
    StudioFieldSpec(key="role", label="角色定位", kind="text"),
    StudioFieldSpec(key="main_folder", label="主要文件夹", kind="list",
                    item_key="path", item_note="note", description="你只可以对此文件夹进行写操作。"),
    StudioFieldSpec(key="additional_folders", label="参考文件夹", kind="list",
                    item_key="path", item_note="note", description="你可以可选地从以下文件夹读取更多信息"),
    StudioFieldSpec(key="tools", label="推荐工具", kind="join", description="推荐关注以下工具进行工作"),
    StudioFieldSpec(key="macros", label="推荐宏", kind="join", description="推荐关注以下宏进行工作"),
    StudioFieldSpec(key="skills", label="推荐技能", kind="join", description="推荐关注以下技能进行工作"),
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
    header = f"## {spec.label}"
    body = _render_kind(spec.kind, value, spec) if value is not None else ""
    if not body:
        if spec.empty_text:
            return f"{header}\n{spec.empty_text}"
        return ""
    if spec.description:
        return f"{header}\n{spec.description}\n\n{body}"
    return f"{header}\n{body}"


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
                return "、".join(items) if items else ""
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
            # 附注换行缩进放置，避免与 path 正文混淆
            lines.append(f"- {text_s}\n  （{note_s}）" if note_s else f"- {text_s}")
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
    data = get_studio(name)
    return render_studio(data) if data is not None else ""


# ── 编辑器支撑：schema / 校验 / CRUD ──────────────────────────

def studio_schema() -> list[dict[str, Any]]:
    """把 STUDIO_SPEC 序列化为 dict 列表，供前端动态生成编辑表单。"""
    return [
        {
            "key": s.key,
            "label": s.label,
            "kind": s.kind,
            "description": s.description,
            "empty_text": s.empty_text,
            "item_key": s.item_key,
            "item_note": s.item_note,
        }
        for s in STUDIO_SPEC
    ]


_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


def _sanitize_filename(name: str) -> str:
    """把展示名安全化为 Windows 兼容文件名（去非法字符、去首尾空白/点）。"""
    cleaned = "".join(c for c in name.strip() if c not in _INVALID_FILENAME_CHARS)
    return cleaned.strip().rstrip(" .")


def find_studio_file(name: str) -> Path | None:
    """按 name 定位 studio 文件；未命中（含缺失/解析失败）返回 None。

    先按 YAML 内 name 精确匹配，再回退按文件名 stem 匹配（兼容历史文件）。
    """
    if not name:
        return None
    for fpath, data in _iter_studio_data():
        n = data.get("name")
        if isinstance(n, str) and n == name:
            return fpath
        if fpath.stem == name:
            return fpath
    return None


def get_studio(name: str) -> dict[str, Any] | None:
    """按 name 返回完整 YAML dict（供编辑回填）；未命中返回 None。"""
    fpath = find_studio_file(name)
    return load_studio_file(fpath) if fpath is not None else None


def validate_studio(data: dict[str, Any]) -> list[str]:
    """返回校验错误列表；空列表 = 通过。"""
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return ["name 不能为空"]
    if not _sanitize_filename(name):
        return ["name 无法生成合法文件名"]
    return []


def _to_info(data: dict[str, Any], filename: str) -> StudioInfo:
    name = data.get("name")
    desc = data.get("description", "")
    return StudioInfo(
        name=name if isinstance(name, str) else "",
        description=desc if isinstance(desc, str) else str(desc),
        filename=filename,
    )


def _safe_studio_path(filename: str) -> Path:
    """把 <name 安全化>.yaml 拼接到 STUDIOS_DIR 下，并校验不越出该目录。

    采用 CodeQL py/path-injection 识别的 SafeAccessCheck 模式：abspath 归一化后，
    解析结果必须位于 STUDIOS_DIR 之内（前缀校验），否则越权路径（如 ``..``
    上跳）直接抛 ValueError。
    """
    base = os.path.abspath(str(STUDIOS_DIR))
    path = os.path.abspath(os.path.join(base, filename))
    if not path.startswith(base + os.sep):
        raise ValueError(f"非法的工作坊文件名: {filename!r}")
    return Path(path)


def _write_studio_file(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def create_studio(data: dict[str, Any]) -> StudioInfo:
    """新建：校验 → 查重 → 写 <name 安全化>.yaml。重复/非法抛 ValueError。"""
    data = dict(data)
    name = str(data.get("name") or "").strip()
    data["name"] = name
    errors = validate_studio(data)
    if errors:
        raise ValueError("；".join(errors))
    if find_studio_file(name) is not None:
        raise ValueError(f"工作坊「{name}」已存在")
    filename = _sanitize_filename(name) + ".yaml"
    STUDIOS_DIR.mkdir(parents=True, exist_ok=True)
    _write_studio_file(_safe_studio_path(filename), data)
    return _to_info(data, filename)


def update_studio(name: str, data: dict[str, Any]) -> StudioInfo:
    """更新：按 name 定位旧文件；body 内 name 变更则重命名文件。

    不存在 → ValueError；新名与他人冲突 → ValueError。
    """
    errors = validate_studio(data)
    if errors:
        raise ValueError("；".join(errors))
    old_path = find_studio_file(name)
    if old_path is None:
        raise ValueError(f"工作坊「{name}」不存在")
    new_name = str(data["name"]).strip()
    new_filename = _sanitize_filename(new_name) + ".yaml"
    new_path = _safe_studio_path(new_filename)
    if new_name != name and find_studio_file(new_name) is not None:
        raise ValueError(f"工作坊「{new_name}」已存在")
    if old_path != new_path:
        old_path.rename(new_path)
    _write_studio_file(new_path, data)
    return _to_info(data, new_filename)


def delete_studio(name: str) -> bool:
    """删除指定工作坊文件；不存在返回 False。"""
    fpath = find_studio_file(name)
    if fpath is None:
        return False
    fpath.unlink()
    return True
