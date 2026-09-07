"""path_guard — 「统一路径校验 + sudo 越权」类装饰器。

把文件类工具内联在 sync 身体里的整套路径卫语句（空值 / 存在性 / isfile|isdir /
路径安全访问）抽离，统一包装工具的 ``async _arun``：

- 声明式 ``PathSpec`` 逐路径参数描述要做什么检查；安全访问（SonettoBlocker +
  白名单，见 ``tools.base.check_path_access``）**恒开**；
- 每个路径参数按「空值 → 安全访问 → 存在 → 类型」的相位序校验；多路径参数时
  **分相位跨参执行**（先全参空值 → 再全参访问 → 再逐参存在/类型），使源路径
  缺失优先于目标已存在等语义稳定；
- 校验经 ``off_thread`` 离环执行（守 ``tools.base`` 的「阻塞体绝不内联协程」纪律），
  错误一律返回 ``format_error(...)`` 字符串，绝不 raise；
- 内置 **sudo** 越权：向工具 schema 注入非必填 ``sudo: bool = False``。仅当安全
  访问被阻断（SonettoBlocker / 白名单）且 ``sudo=True`` 时，先弹一次 mode="sudo"
  的用户授权确认（气泡前端统一走单个 ConfirmBubble）；批准后本次调用一次性越过
  安全访问，**空值/存在/类型仍照常校验**。sudo 授权**始终要求显式确认**，不受
  会话 auto_approve 影响。sudo 提示发生在确认弹窗/后台 spawn 之前，故对同时带
  ``@confirm_execution`` 的工具，交互顺序恒为「先 sudo，后侵彻性文件操作」；
- 不改动底层原语 ``tools.policies``：仅以 ``enrich_tool_class`` 包 ``_arun`` 建子类，
  经 ``schema_fields`` 注入 sudo 字段。

用法（作用于工具类，携带参数；置于 ``@confirm_execution`` / ``@background`` 之上，
使其成为最外层包装）：

    @path_guard(PathSpec("file_path", kind="file"))
    @confirm_execution(question="…")
    class SomeFileTool(ToolBase):
        async def _arun(self, file_path: str = ""): ...
"""

from __future__ import annotations

import asyncio
import functools
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import Field

from api.agent import interaction
from api.events import ToolSender
from tools.base import check_path_access, format_error, off_thread
from tools.policies import INJECTED_KWARGS, enrich_tool_class

ToolClass = type[BaseTool]

PathKind = Literal["file", "dir", "any"]
Existence = Literal["exists", "absent"]

SUDO_DESCRIPTION = (
    "设为 true 时，若路径被安全策略（SonettoBlocker/白名单）阻断，将先弹出 sudo "
    "授权确认；批准后本次调用一次性越权放行（仍校验路径存在/类型）。"
)
SUDO_APPROVE_TEXT = "sudo 授权"
SUDO_REJECT_TEXT = "拒绝"
SUDO_REJECT_MESSAGE = "用户拒绝了 sudo 越权授权"
SUDO_MODE = "sudo"


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


# ── 相位检查（均同步；由 wrapper 按需经 off_thread 离环）──────────


def _resolve_specs(specs: tuple[PathSpec, ...], resolved: dict[str, Any]) -> str | None:
    """Phase A — 空值（逐参，按 spec 顺序）；required=False 时静默解析为 default。

    就地回填 default；返回首个空值错误文案，无错误返回 None。
    """
    for spec in specs:
        if resolved.get(spec.arg, "") == "":
            if spec.required:
                return _message(spec, "empty", "")
            resolved[spec.arg] = spec.default  # type: ignore[assignment]
    return None


def _first_access_error(specs: tuple[PathSpec, ...], resolved: dict[str, Any]) -> str | None:
    """Phase B — 安全访问（SonettoBlocker + 白名单），返回首个错误文案或 None。"""
    for spec in specs:
        target = resolved[spec.arg]
        assert isinstance(target, str)
        err = check_path_access(target)
        if err:
            return err
    return None


def _first_existence_type_error(
    specs: tuple[PathSpec, ...], resolved: dict[str, Any]
) -> str | None:
    """Phase C — 存在 / 类型（逐参，按 spec 顺序），返回首个错误文案或 None。"""
    for spec in specs:
        target = resolved[spec.arg]
        assert isinstance(target, str)
        if spec.existence == "exists" and not os.path.exists(target):
            return _message(spec, "exists", target)
        if spec.existence == "absent" and os.path.exists(target):
            return _message(spec, "absent", target)
        if spec.existence == "exists" and _is_type_checked(spec):
            if spec.kind == "file" and not os.path.isfile(target):
                return _message(spec, "type", target)
            if spec.kind == "dir" and not os.path.isdir(target):
                return _message(spec, "type", target)
    return None


# ── sudo 授权 ───────────────────────────────────────────────


async def _request_sudo(
    sender: ToolSender,
    tool_name: str,
    question: str,
    payload: dict[str, Any],
) -> str | None:
    """请求一次 sudo 授权（mode="sudo"）。

    Returns:
        None — 用户批准，可越过安全访问；
        str  — 应回给 LLM 的 format_error 错误串（拒绝/取消/异常）。
    """
    interaction_id, future = interaction.register()
    try:
        await sender.ask_user(
            tool_name=tool_name,
            question=question,
            mode=SUDO_MODE,
            interaction_id=interaction_id,
            approve_text=SUDO_APPROVE_TEXT,
            reject_text=SUDO_REJECT_TEXT,
            **payload,
        )
        answer: Any = await future

        action: Any = answer
        reason: str = ""
        if isinstance(answer, dict):
            action = answer.get("action", "")
            reason = answer.get("reason", "")

        if action == "approve":
            return None
        if reason:
            return format_error(f"{SUDO_REJECT_MESSAGE}。原因：{reason}")
        return format_error(SUDO_REJECT_MESSAGE)
    except asyncio.CancelledError:
        return format_error("用户取消了回复")
    finally:
        interaction.cleanup(interaction_id)


async def _sudo_authorize(
    tool: BaseTool, resolved: dict[str, Any]
) -> str | None:
    """访问被阻断且 sudo=True 时的授权入口。

    Returns:
        None — 用户批准 sudo，可越过安全访问；
        str  — 应回给 LLM 的 format_error 错误串。

    sudo 授权始终要求显式确认：不读会话 auto_approve。面板文案仅保留说明与
    所涉路径（路径由前端文件卡片从 payload 展示），不放具体阻断细节。
    """
    sender = ToolSender.from_context()
    if sender is None:
        return format_error("WebSocket 连接不可用")

    payload = {
        name: value
        for name, value in resolved.items()
        if name not in INJECTED_KWARGS
    }
    question = (
        "该操作路径被安全策略阻断。sudo 将对本次调用越权放行一次，是否确认？"
    )
    return await _request_sudo(
        sender, tool_name=tool.name, question=question, payload=payload
    )


def path_guard(*specs: PathSpec) -> Callable[[ToolClass], ToolClass]:
    """应用「统一路径校验 + sudo 越权」类装饰器。

    Args:
        specs: 逐路径参数的 ``PathSpec`` 声明，至少一个。

    Returns:
        增强后的 pydantic 子类（包 ``_arun``，注入非必填 ``sudo: bool``）。
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
                # sudo 为注入的技术参：消费后不再透传给内层（含 confirm payload）
                sudo = bool(kwargs.pop("sudo", False))
                resolved = dict(kwargs)

                # Phase A — 空值 + 静默默认（纯内存，可内联）
                empty_error = _resolve_specs(specs, resolved)
                if empty_error is not None:
                    return format_error(empty_error)

                # Phase B — 安全访问（离环）
                access_error = await off_thread(_first_access_error, specs, resolved)
                if access_error is not None:
                    if not sudo:
                        return format_error(access_error)
                    sudo_error = await _sudo_authorize(self, resolved)
                    if sudo_error is not None:
                        return sudo_error  # 已是 format_error 串
                    # sudo 已批准：越过安全访问，继续存在/类型校验

                # Phase C — 存在 / 类型（离环）
                phase_error = await off_thread(
                    _first_existence_type_error, specs, resolved
                )
                if phase_error is not None:
                    return format_error(phase_error)

                return await orig(self, *args, **resolved)

            return wrapper

        return enrich_tool_class(
            cls,
            schema_fields={
                "sudo": (bool, Field(default=False, description=SUDO_DESCRIPTION)),
            },
            wrap_method=make_wrapper,
        )

    return decorator
