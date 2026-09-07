"""path_guard — 「统一路径校验」类装饰器。

把文件类工具内联在 sync 身体里的整套路径卫语句（空值 / 存在性 / isfile|isdir /
路径安全访问）抽离，统一包装工具的 ``async _arun``：

- 声明式 ``PathSpec`` 逐路径参数描述要做什么检查；安全访问（SonettoBlocker +
  白名单，见 ``tools.base.check_path_access``）**恒开不可关**；
- 每个路径参数按「空值 → 安全访问 → 存在 → 类型」的相位序校验；多路径参数时
  **分相位跨参执行**（先全参空值 → 再全参访问 → 再逐参存在/类型），使源路径
  缺失优先于目标已存在等语义稳定；
- 校验经 ``off_thread`` 离环执行（守 ``tools.base`` 的「阻塞体绝不内联协程」纪律），
  错误一律返回 ``format_error(...)`` 字符串，绝不 raise；
- 不改动底层原语 ``tools.policies``：仅以 ``enrich_tool_class(cls, wrap_method=...)``
  包 ``_arun`` 建子类，不注入 schema 字段。

用法（作用于工具类，携带参数；置于 ``@confirm_execution`` / ``@background`` 之上，
使其成为最外层包装，非法/受限路径在确认弹窗与后台 spawn 之前即被拒）：

    @path_guard(PathSpec("file_path", kind="file"))
    @confirm_execution(question="…")
    class SomeFileTool(ToolBase):
        async def _arun(self, file_path: str = ""): ...
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.tools import BaseTool

from tools.base import check_path_access, format_error, off_thread
from tools.policies import enrich_tool_class

ToolClass = type[BaseTool]

PathKind = Literal["file", "dir", "any"]
Existence = Literal["exists", "absent"]


@dataclass(frozen=True)
class PathSpec:
    """单个路径参数应执行的校验声明。

    Attributes:
        arg: 工具 ``_arun`` 中该路径参数的 kwarg 名。
        kind: 路径语义。``file`` / ``dir`` 会开启类型校验，``any`` 不校验类型。
        required: 为 True 时空参（空串/缺省）报「xx 不能为空」；为 False 时空参被
            静默解析为 *default*（如 list_directory 空参视为 "."），不报错。
        default: ``required=False`` 时的解析默认值（必须提供）。
        existence: ``"exists"`` 要求路径必须存在；``"absent"`` 要求必须不存在
            （如 rename 的目标）；None 表示不校验存在性（如 write/create）。
        type_check: 是否开启类型校验。None 时按 *kind* 推断（file/dir→True，
            any→False）。类型校验仅在 ``existence="exists"`` 时生效——目标尚不
            存在（write/create，existence=None）时无从判定 file/dir，故不校验。
        empty_msg / exists_msg / absent_msg / type_msg: 逐条件文案覆写；缺省用
            统一规范文案（见 ``_message``）。
    """

    arg: str
    kind: PathKind = "file"
    required: bool = True
    default: str | None = None
    existence: Existence | None = "exists"
    type_check: bool | None = None
    empty_msg: str | None = None
    exists_msg: str | None = None
    absent_msg: str | None = None
    type_msg: str | None = None


def _is_type_checked(spec: PathSpec) -> bool:
    """类型校验是否开启（显式给定则采用，否则按 kind 推断）。"""
    if spec.type_check is not None:
        return spec.type_check
    return spec.kind in ("file", "dir")


def _message(spec: PathSpec, condition: str, path: str) -> str:
    """按条件返回校验失败文案（缺省走统一规范文案）。"""
    if condition == "empty":
        return spec.empty_msg or f"{spec.arg} 不能为空"
    if condition == "exists":
        if spec.exists_msg:
            return spec.exists_msg
        prefix = "目录" if spec.kind == "dir" else "文件"
        return f"{prefix}不存在: {path}"
    if condition == "absent":
        return spec.absent_msg or f"目标已存在: {path}"
    # condition == "type"
    if spec.type_msg:
        return spec.type_msg
    if spec.kind == "dir":
        return f"路径不是目录: {path}"
    return f"路径不是文件: {path}"


def _run_path_checks(
    specs: tuple[PathSpec, ...], kwargs: dict[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    """按相位序执行全部路径校验（同步；由调用方经 off_thread 离环）。

    返回 ``(error_message, resolved_kwargs)``：有错误时前者非空；无错误时后者为
    回填了静默默认值的 kwargs 副本，供转发给被包装的 ``_arun``。
    """
    resolved = dict(kwargs)

    # Phase A — 空值（逐参，按 spec 顺序）；required=False 时静默解析为 default。
    for spec in specs:
        if resolved.get(spec.arg, "") == "":
            if spec.required:
                return _message(spec, "empty", ""), resolved
            resolved[spec.arg] = spec.default  # type: ignore[assignment]

    # Phase B — 安全访问（SonettoBlocker + 白名单），恒开、不可跳过。
    for spec in specs:
        target = resolved[spec.arg]
        assert isinstance(target, str)
        err = check_path_access(target)
        if err:
            return err, resolved

    # Phase C — 存在 / 类型（逐参，按 spec 顺序）。
    for spec in specs:
        target = resolved[spec.arg]
        assert isinstance(target, str)
        if spec.existence == "exists" and not os.path.exists(target):
            return _message(spec, "exists", target), resolved
        if spec.existence == "absent" and os.path.exists(target):
            return _message(spec, "absent", target), resolved
        if spec.existence == "exists" and _is_type_checked(spec):
            if spec.kind == "file" and not os.path.isfile(target):
                return _message(spec, "type", target), resolved
            if spec.kind == "dir" and not os.path.isdir(target):
                return _message(spec, "type", target), resolved

    return None, resolved


def path_guard(*specs: PathSpec) -> Callable[[ToolClass], ToolClass]:
    """应用「统一路径校验」类装饰器。

    Args:
        specs: 逐路径参数的 ``PathSpec`` 声明，至少一个。

    Returns:
        增强后的 pydantic 子类（仅包 ``_arun``，不注入 schema 字段）。
    """
    if not specs:
        raise ValueError("path_guard 需要至少一个 PathSpec")

    for spec in specs:
        if not spec.required and spec.default is None:
            raise ValueError(
                f"PathSpec('{spec.arg}') 声明 required=False 时必须提供 default"
            )

    def decorator(cls: ToolClass) -> ToolClass:
        def make_wrapper(orig: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(orig)
            async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                # 校验经线程池离环（listdir 逐级父目录、白名单重载、stat 等）
                error, resolved = await off_thread(_run_path_checks, specs, kwargs)
                if error is not None:
                    return format_error(error)
                return await orig(self, *args, **resolved)

            return wrapper

        return enrich_tool_class(cls, wrap_method=make_wrapper)

    return decorator
