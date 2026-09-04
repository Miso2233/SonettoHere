"""confirm_execution — 「执行前确认」类装饰器。

把「执行危险操作前先征得用户同意」的门控逻辑从工具方法中抽离，包装工具的
``_arun``：

- 会话级 auto_approve 开启时直接放行，不打扰用户；
- 否则经 WebSocket ``ask_user(mode="confirm")`` 请求确认，approve 后才执行原方法，
  reject 返回统一拒绝错误，用户中途取消返回统一取消错误；
- 确认期间注册的交互在 finally 清理。

确认气泡载荷取原方法的用户可见命名参数（已剔除 INJECTED_KWARGS 技术参数）；
批准后含技术参数的完整 ``**kwargs`` 原样透传给原方法。

用法（作用于工具类，携带参数）：

    @confirm_execution(question="即将执行危险操作，是否继续？")
    class SomeTool(ToolBase):
        async def _arun(self, ...): ...
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool

from api.agent import interaction
from api.events import ToolSender
from tools.base import format_error
from tools.policies import INJECTED_KWARGS, enrich_tool_class

ToolClass = type[BaseTool]


def confirm_execution(
    cls: ToolClass | None = None,
    *,
    question: str,
    approve_text: str = "允许执行",
    reject_text: str = "拒绝执行",
    reject_message: str = "用户拒绝执行",
) -> ToolClass | Callable[[ToolClass], ToolClass]:
    """构造/应用「执行前确认」工具类装饰器。

    Args:
        cls: ``@confirm_execution`` 携带参数应用时的目标工具类。本装饰器需
            question 等参数、无裸用场景，保留该位置参数仅为与 get_doc 同构。
        question: 发送给 ask_user 的确认问题文本。
        approve_text: 允许按钮的文案，默认 "允许执行"。
        reject_text: 拒绝按钮的文案，默认 "拒绝执行"。
        reject_message: 用户拒绝时返回的错误消息前缀（独立于拒绝按钮文案）。

    Returns:
        传入 *cls* 时返回增强后的 pydantic 子类；未传入时返回待应用的装饰器。
    """

    def decorator(target: ToolClass) -> ToolClass:
        def make_wrapper(orig: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(orig)
            async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                # 自动执行：会话级 auto_approve 开启时直接放行，不打扰用户。
                # 不强制要求 WebSocket 连接可用——被装饰方法自行按需处理。
                session_id = interaction.current_session_id.get()
                if session_id and interaction.get_session_auto_approve(session_id):
                    return await orig(self, *args, **kwargs)

                # 手动确认：必须能通过 WebSocket 把确认问题送达用户
                sender = ToolSender.from_context()
                if sender is None:
                    return format_error("WebSocket 连接不可用")

                # 载荷 = 两个按钮文案 + 被装饰方法的用户可见命名形参。技术参数
                # 只从载荷**副本**剔除，原 kwargs 原样保留透传给 orig（run_python
                # 的 run_id 正取自其中 langchain 注入的 run_manager）。
                payload = {
                    name: value
                    for name, value in kwargs.items()
                    if name not in INJECTED_KWARGS
                }
                interaction_id, future = interaction.register()

                await sender.ask_user(
                    tool_name=self.name,
                    question=question,
                    mode="confirm",
                    interaction_id=interaction_id,
                    approve_text=approve_text,
                    reject_text=reject_text,
                    **payload,
                )

                try:
                    answer: Any = await future

                    action: Any = answer
                    reason: str = ""
                    if isinstance(answer, dict):
                        action = answer.get("action", "")
                        reason = answer.get("reason", "")

                    if action == "approve":
                        return await orig(self, *args, **kwargs)

                    if reason:
                        return format_error(f"{reject_message}。原因：{reason}")
                    return format_error(reject_message)
                except asyncio.CancelledError:
                    return format_error("用户取消了回复")
                finally:
                    interaction.cleanup(interaction_id)

            return wrapper

        return enrich_tool_class(target, wrap_method=make_wrapper)

    if cls is not None:
        return decorator(cls)
    return decorator
