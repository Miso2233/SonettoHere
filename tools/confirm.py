"""confirm_execution — 「执行前确认」通用异步方法装饰器。

把「执行危险操作前先征得用户同意」的门控逻辑从工具方法中抽离：

- 会话开启自动执行（auto_approve）时直接放行，不打扰用户；
- 否则要求 WebSocket 连接可用，通过 ask_user(mode="confirm") 弹出确认，
  用户 approve 后调用被装饰方法，reject 返回统一拒绝错误；
- 用户中途取消（CancelledError）返回统一取消错误；注册的交互在 finally 清理。

auto mode 信号统一取自会话级 auto_approve（interaction._settings，由 WebSocket
层写入），对**所有受装饰工具一致生效**，无需逐个传参。

适用范围（当前）：仅 run_python。ask_qa / single_choice / multi_choice 属于
「采集输入」语义（收集后继续，而非确认后放行），不适用，不在此重构。

被装饰方法约定：
- 是异步方法，签名 (self, ...) -> str（统一响应字符串）；
- 只负责「拿到参数后真正执行」，无需关心确认流程；
- 若需要 run_id（流式执行），方法签名应声明 run_manager 形参并自行解析。
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any

from api.agent import interaction
from api.events import ToolSender
from tools.base import format_error

# 被装饰方法类型：异步方法，接收 self + 任意参数，返回任意响应字符串。
# 不尝试用 ParamSpec 精确建模 self（方法绑定的 self 无法被 ParamSpec 干净覆盖）。
AsyncMethod = Callable[..., Any]


def confirm_execution(
    *,
    question: str,
    options: list[str],
    extra_payload: Callable[..., dict[str, Any]] | None = None,
    reject_message: str = "用户拒绝执行",
) -> Callable[[AsyncMethod], AsyncMethod]:
    """构造「执行前确认」装饰器。

    Args:
        question: 发送给 ask_user 的确认问题文本。
        options: ask_user 的按钮选项列表（如 ["执行", "取消"]）。
        extra_payload: 可选；接收与被装饰方法相同的 (self, args, kwargs)，
            返回要附带进 ask_user payload 的额外字段（如 run_python 的 code）。
            注意 kwargs 中可能携带 run_manager，实现需接受 **kwargs 兜底。
        reject_message: 用户拒绝时的错误消息前缀。

    Returns:
        一个装饰器，包装异步方法，使其先经过确认门控。
    """

    def decorator(fn: AsyncMethod) -> AsyncMethod:
        @functools.wraps(fn)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # 自动执行：会话级 auto_approve 开启时直接放行，不打扰用户。
            # 与手动确认分支不同：不强制要求 WebSocket 连接可用——
            # 内层方法自行按 run_id 决定是否依赖 WebSocket（无 run_id 时可
            # 退化为进程内执行），与 run_python 既有语义一致。
            session_id = interaction.current_session_id.get()
            if session_id and interaction.get_session_auto_approve(session_id):
                return await fn(self, *args, **kwargs)

            # 手动确认：必须能通过 WebSocket 把确认问题送达用户
            sender = ToolSender.from_context()
            if sender is None:
                return format_error("WebSocket 连接不可用")

            interaction_id, future = interaction.register()

            payload: dict[str, Any] = (
                extra_payload(self, *args, **kwargs) if extra_payload is not None else {}
            )
            await sender.ask_user(
                tool_name=self.name,
                question=question,
                mode="confirm",
                options=options,
                interaction_id=interaction_id,
                **payload,
            )

            try:
                answer: Any = await future

                action: Any = answer
                reason = ""
                if isinstance(answer, dict):
                    action = answer.get("action", "")
                    reason = answer.get("reason", "")

                if action == "approve":
                    return await fn(self, *args, **kwargs)

                if reason:
                    return format_error(f"{reject_message}。原因：{reason}")
                return format_error(reject_message)
            except asyncio.CancelledError:
                return format_error("用户取消了回复")
            finally:
                interaction.cleanup(interaction_id)

        return wrapper

    return decorator
