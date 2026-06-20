"""工具（Tool）基类和共享 HTTP 客户端。"""

import json
import os
from pathlib import Path

import yaml

import requests
from langchain_core.tools import BaseTool
from todoist_api_python.api import TodoistAPI
from uapi import UapiClient

from config.settings import get_settings


class SharedAPIClient:
    """所有 Tool 共享的 HTTP 客户端，API Key 仅加载一次。"""

    def __init__(self):
        settings = get_settings()
        self._session = requests.Session()
        self._uapi: UapiClient | None = None
        self._todoist: TodoistAPI | None = None
        self._amap_key = settings.amap_api_key
        self._uapis_key = settings.uapis_api_key
        self._todoist_token = settings.todoist_api_token

    @property
    def uapi(self) -> UapiClient:
        if self._uapi is None:
            self._uapi = UapiClient("https://uapis.cn", token=self._uapis_key)
        return self._uapi

    @property
    def todoist(self) -> TodoistAPI:
        if self._todoist is None:
            self._todoist = TodoistAPI(self._todoist_token)
        return self._todoist

    @property
    def amap_key(self) -> str:
        return self._amap_key

    def amap_request(self, endpoint: str, params: dict) -> dict:
        """发起高德地图 API 请求。"""
        params["key"] = self._amap_key
        resp = self._session.get(f"https://restapi.amap.com{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._session.close()


class ToolBase(BaseTool):
    """所有 Tool 的基类。提供 get_doc 通用实现和统一错误格式。"""

    client: SharedAPIClient | None = None

    def _load_doc(self) -> str:
        """读取同目录下的 TOOL.md，作为领域知识返回给 LLM。"""
        import sys

        mod = sys.modules.get(self.__class__.__module__)
        if mod is not None and hasattr(mod, "__file__") and mod.__file__ is not None:
            tool_dir = Path(mod.__file__).parent
        else:
            tool_dir = Path(".")
        doc_path = tool_dir / "TOOL.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
        return "（本 Tool 暂无文档）"


def format_success(data: dict) -> str:
    """统一成功响应格式。"""
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)


def format_error(message: str) -> str:
    """统一错误响应格式。"""
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def check_sonetto_blocker(target_path: str) -> str | None:
    """逐级检查路径的每一级目录是否包含 SonettoBlocker 文件（不区分大小写，不匹配后缀名）。

    从盘符根目录开始，依次检查每一层父目录中是否存在名为 "SonettoBlocker"
    的文件（任何扩展名均匹配）。一旦发现，返回该目录路径；否则返回 None。
    """
    if not target_path:
        return None

    abs_path = os.path.abspath(target_path)
    p = Path(abs_path)

    # 收集待检查的所有目录层级
    dirs_to_check: list[str] = []

    if p.is_dir():
        dirs_to_check.append(str(p))
    else:
        # 文件还不存在（如 write_file 写入新文件）则检查父目录
        parent = p.parent
        if parent:
            dirs_to_check.append(str(parent))

    # parents 从父目录向上直到根
    dirs_to_check.extend(str(parent) for parent in p.parents)

    # 从根向下逐级检查
    seen: set[str] = set()
    for dir_path in reversed(dirs_to_check):
        normalized = os.path.normpath(dir_path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if not os.path.isdir(normalized):
            continue
        try:
            for entry in os.listdir(normalized):
                entry_name, _ = os.path.splitext(entry)
                if entry_name.lower() == "sonettoblocker":
                    # 返回友好的展示形式
                    return normalized
        except (PermissionError, OSError):
            continue

    return None


# ── 路径白名单 ──────────────────────────────────────────────

_WHITELIST_PATH = (
    Path(__file__).resolve().parent.parent / "api" / "data" / "path_whitelist.yaml"
)

# 项目根目录：由 base.py 所在位置 (tools/base.py) 向上推一级
_PROJECT_ROOT = os.path.normpath(
    os.path.abspath(Path(__file__).resolve().parent.parent)
)
# 默认白名单路径：仅暴露 anthropic_skills 和 macros 目录
_DEFAULT_WHITELIST_PATH = os.path.join(_PROJECT_ROOT, "anthropic_skills")
_DEFAULT_MACROS_WHITELIST_PATH = os.path.join(_PROJECT_ROOT, "macros")

# ── 路径白名单 ──────────────────────────────────────────────

_WHITELIST_PATH = (
    Path(__file__).resolve().parent.parent / "api" / "data" / "path_whitelist.yaml"
)


def _ensure_whitelist() -> None:
    """确保白名单文件存在且包含当前工程的 anthropic_skills 和 macros 目录。

    在模块导入时（即应用启动时）调用一次：
    - 文件不存在 → 自动创建，写入 anthropic_skills + macros 路径
    - 工程被移动（自动条目路径不匹配当前路径） → 更新文件，
      保留用户添加的额外条目，仅替换/添加自动生成条目
    - 文件已存在且自动条目匹配 → 不做任何操作
    """
    if not _WHITELIST_PATH.parent.exists():
        _WHITELIST_PATH.parent.mkdir(parents=True)

    _defaults = _default_entries()

    if not _WHITELIST_PATH.exists():
        _write_whitelist(_defaults)
        return

    # 文件已存在，检查默认路径是否已在白名单中
    try:
        with open(_WHITELIST_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("whitelist", [])
        if not isinstance(entries, list):
            _write_whitelist(_defaults)
            return

        changed = False
        for default_entry in _defaults:
            target_path = os.path.normpath(os.path.abspath(default_entry["path"]))
            target_desc = default_entry["description"]
            has_current = False
            auto_entry_idx = -1

            for i, entry in enumerate(entries):
                if not isinstance(entry, dict) or "path" not in entry:
                    continue
                entry_path = os.path.normpath(os.path.abspath(entry["path"]))
                if entry_path == target_path:
                    has_current = True
                    break
                if entry.get("description") == target_desc:
                    auto_entry_idx = i

            if has_current:
                continue

            # 工程移动了：更新旧的自动条目，或在开头插入新条目
            if auto_entry_idx >= 0:
                entries[auto_entry_idx]["path"] = str(target_path)
            else:
                entries.insert(0, default_entry)
            changed = True

        if changed:
            with open(_WHITELIST_PATH, "w", encoding="utf-8") as f:
                yaml.dump(
                    {"whitelist": entries}, f, allow_unicode=True, default_flow_style=False
                )

    except (yaml.YAMLError, OSError, ValueError):
        # 文件损坏 → 重写
        _write_whitelist(_defaults)


def _default_entry() -> dict:
    return {
        "path": os.path.normpath(str(_DEFAULT_WHITELIST_PATH)),
        "description": "技能目录（自动生成）",
        "recursive": True,
    }


def _default_macros_entry() -> dict:
    return {
        "path": os.path.normpath(str(_DEFAULT_MACROS_WHITELIST_PATH)),
        "description": "宏目录（自动生成）",
        "recursive": True,
    }


def _default_entries() -> list[dict]:
    """返回所有自动生成的默认白名单条目。"""
    return [_default_entry(), _default_macros_entry()]


def _write_whitelist(entries: list) -> None:
    content = {
        "whitelist": entries,
    }
    with open(_WHITELIST_PATH, "w", encoding="utf-8") as f:
        # 写入手动头注释
        f.write("# 路径白名单（自动生成，首次 import 时创建）\n")
        f.write("# 编辑此文件以添加更多允许的路径前缀。\n")
        yaml.dump(content, f, allow_unicode=True, default_flow_style=False)


_BLOCKER_YAML_PATH = (
    Path(__file__).resolve().parent.parent / "api" / "data" / "sonetto_blocker.yaml"
)

_BLOCKER_FILENAME = "SonettoBlocker"
_AUTO_BLOCKER_PATH = os.path.join(_PROJECT_ROOT, "api", "data")


def _ensure_blocker() -> None:
    """确保 api/data/ 目录受 SonettoBlocker 保护。

    在模块导入时自动运行：
    - 如果 api/data/ 下没有 SonettoBlocker 标记文件 → 创建
    - 如果 sonetto_blocker.yaml 中没有对应条目 → 添加
    """
    marker = Path(_AUTO_BLOCKER_PATH) / _BLOCKER_FILENAME
    if not marker.exists():
        try:
            marker.write_text("", encoding="utf-8")
        except OSError:
            return

    if not _BLOCKER_YAML_PATH.exists():
        return

    try:
        with open(_BLOCKER_YAML_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("blockers", [])
        if not isinstance(entries, list):
            return

        normalized = os.path.normpath(_AUTO_BLOCKER_PATH)
        has_entry = any(
            isinstance(e, dict)
            and os.path.normpath(os.path.abspath(e.get("path", ""))) == normalized
            for e in entries
        )
        if not has_entry:
            entries.insert(
                0,
                {
                    "path": _AUTO_BLOCKER_PATH,
                    "description": "API 数据目录（自动生成）",
                },
            )
            with open(_BLOCKER_YAML_PATH, "w", encoding="utf-8") as f:
                yaml.dump(
                    {"blockers": entries},
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                )
    except (yaml.YAMLError, OSError):
        pass


# 模块加载时自动执行：确保白名单存在 + api/data/ 拒止锚存在（首次 import 时运行一次）
_ensure_whitelist()
_ensure_blocker()


def _load_path_whitelist() -> list[tuple[str, bool]]:
    """从 YAML 文件加载白名单条目列表。

    每个条目返回 (normalized_path, recursive) 元组。
    recursive=True 时该路径下所有子目录继承访问权限；
    recursive=False 时仅允许访问该确切路径。

    文件格式:
        whitelist:
          - path: "/some/allowed/dir"
            description: ...
            recursive: true
    读取失败时返回空列表（会触发 fail-secure 全阻断）。
    """
    try:
        with open(_WHITELIST_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("whitelist", [])
        if not isinstance(entries, list):
            return []
        result: list[tuple[str, bool]] = []
        for entry in entries:
            if isinstance(entry, dict) and "path" in entry:
                normalized = os.path.normpath(os.path.abspath(entry["path"]))
                recursive = entry.get("recursive", True)
                if isinstance(recursive, bool):
                    result.append((normalized, recursive))
                else:
                    result.append((normalized, True))
        return result
    except (yaml.YAMLError, OSError, ValueError):
        return []


def check_path_whitelisted(target_path: str) -> str | None:
    """检查 *target_path* 是否位于白名单设置的任一前缀下。

    参数:
        target_path: 待验证的文件或目录路径（相对或绝对均可）。

    返回:
        None      — 允许访问（路径在白名单内）。
        str       — 阻断原因描述，调用方应将其传给 format_error() 返回给 LLM。

    算法行为（按优先级排列）:

        1) 精确匹配
           目标路径与任何条目的路径完全一致 → 放行。这是最高优先级，
           不受该条目或任何父目录条目的 recursive 标志影响。

        2) 非递归阻断
           匹配到某个 non-recursive 条目的子路径 → 阻断。
           non-recursive 的含义是"仅当前目录"——该条目的所有子路径
           均被拒绝，即使更深层另有一个 recursive 子条目也无法覆盖。
           父目录 non-recursive 的阻断强于子目录 recursive 的放行。

        3) 递归放行
           没有任何 non-recursive 父目录阻断，且匹配到某个 recursive
           条目的子路径 → 放行。recursive 的含义是该路径及以下所有
           目录均允许访问。

        4) 无匹配
           以上都不满足 → 阻断。
    """
    if not target_path:
        return None

    abs_target = os.path.normpath(os.path.abspath(target_path))
    whitelist = _load_path_whitelist()

    if not whitelist:
        return f"路径不在白名单中: {target_path}（白名单为空或未配置）"

    has_recursive_parent = False

    for allowed_prefix, recursive in whitelist:
        # 去掉末尾分隔符，避免 root 路径（如 T:\）拼接 os.sep 产生双分隔符
        prefix_stripped = allowed_prefix.rstrip(os.sep)
        separator = prefix_stripped + os.sep

        # 优先级 1: 精确匹配 → 不受 recursive 标志影响
        if abs_target in (allowed_prefix, prefix_stripped):
            return None

        # 目标不在当前条目的路径树下 → 跳过，检查下一项
        if not abs_target.startswith(separator):
            continue

        # 目标在当前条目的子目录中
        if not recursive:
            # 优先级 2: non-recursive → 阻断一切子路径（即使另有 recursive 子条目）
            return f"路径受限: {target_path}（白名单条目 '{allowed_prefix}' 限定仅当前目录）"
        # 优先级 3 候选: recursive 父目录匹配 → 标记，继续检查后续非递归条目
        has_recursive_parent = True

    if has_recursive_parent:
        return None

    return f"路径不在白名单中: {target_path}"


# ── exec() 安全 builtins（维持日常功能，仅拦截 open） ──────


def _whitelisted_open(
    file,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    closefd: bool = True,
    opener=None,
):
    """``open()`` 的包装版本，在打开文件前先检查 SonettoBlocker，再检查白名单。

    完全兼容内置 ``open()`` 的全部参数签名。检查顺序：
    1. ``check_sonetto_blocker()`` — 若阻断则抛出 ``PermissionError``（Blocker 优先）
    2. ``check_path_whitelisted()`` — 若不在白名单则抛出 ``PermissionError``
    """
    import builtins as _real_builtins

    # 仅对字符串路径进行检查，跳过已打开的文件描述符
    file_str = file
    if isinstance(file, os.PathLike):
        file_str = os.fspath(file)
    if isinstance(file_str, str):
        # 1. SonettoBlocker 优先
        blocked = check_sonetto_blocker(file_str)
        if blocked:
            raise PermissionError(
                "🚫 安全阻断：操作已被 SonettoBlocker 阻断。\n"
                f"SonettoBlocker 文件位于: {blocked}\n"
                "请立即停止当前任务。"
            )
        # 2. 白名单次之
        blocked = check_path_whitelisted(file_str)
        if blocked:
            raise PermissionError(blocked)

    return _real_builtins.open(
        file, mode, buffering, encoding, errors, newline, closefd, opener
    )


def get_safe_builtins() -> dict:
    """构造用于 ``exec()`` 的安全 builtins 字典。

    保留全部内置函数（包括 ``__import__``、``eval`` 等），
    仅将 ``open()`` 替换为经过 ``check_path_whitelisted()``
    审查的包装版本。日常计算、模块导入、调试等功能均不受影响。
    """
    # 在非 __main__ 模块中，__builtins__ 是模块对象而非 dict
    if isinstance(__builtins__, dict):  # type: ignore[name-defined]
        source = __builtins__  # type: ignore[name-defined]
    else:
        source = __builtins__.__dict__  # type: ignore[name-defined]

    safe = dict(source)
    safe["open"] = _whitelisted_open
    safe["__builtins__"] = safe
    return safe
