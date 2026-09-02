"""confirm_execution — 「执行前确认」通用异步方法装饰器。

把「执行危险操作前先征得用户同意」的门控逻辑从工具方法中抽离：

- 会话开启自动执行（auto_approve）时直接放行，不打扰用户；
- 否则要求 WebSocket 连接可用，通过 ask_user(mode="confirm") 弹出确认，
  用户 approve 后调用被装饰方法，reject 返回统一拒绝错误；
- 用户中途取消（CancelledError）返回统一取消错误；注册的交互在 finally 清理。

auto mode 信号统一取自会话级 auto_approve（interaction._settings，由 WebSocket
层写入），对**所有受装饰工具一致生效**，无需逐个传参。

适用范围：run_python 及 5 个破坏性/写入 file 工具（file_write / file_edit /
file_delete / file_create_directory / file_rename）——仅这些执行前需放行的工具。
ask_qa / single_choice / multi_choice 属于「采集输入」语义（收集后继续，而非
确认后放行），不适用。

设计约定（确认先于逻辑，代码最简）：
- 每个工具只把**真正执行**的那个异步方法（确认门控后）用本装饰器包装，
  形参即工具入参；方法体先确认放行、再做前置校验与操作，无需拆两段。
- 确认气泡的载荷 = 被装饰方法的全部命名形参，由 wrapper 把 ``**kwargs``
  原样转发给 ask_user，前端按工具名选用字段；无需回调构造载荷。因此被装饰
  方法**必须以关键字参数被调用**，且签名中不含非用户可见的技术参数。
- 装饰器与确认流程不接触 run_manager / run_id。仅 run_python 的流式执行需要
  run_id：在其**未装饰**的 _arun 入口取出后存入模块级 ContextVar，确认放行后
  的内层方法自行读取（同一 asyncio 任务内 set/read 天然隔离）。
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
    reject_message: str = "用户拒绝执行",
) -> Callable[[AsyncMethod], AsyncMethod]:
    """构造「执行前确认」装饰器。

    Args:
        question: 发送给 ask_user 的确认问题文本。
        options: ask_user 的按钮选项列表（如 ["执行", "取消"]）。
        reject_message: 用户拒绝时的错误消息前缀。

    Returns:
        一个装饰器，包装异步方法，使其先经过确认门控。
    """

    def decorator(fn: AsyncMethod) -> AsyncMethod:
        @functools.wraps(fn)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # 自动执行：会话级 auto_approve 开启时直接放行，不打扰用户。
            # 不强制要求 WebSocket 连接可用——被装饰方法自行按需处理。
            session_id = interaction.current_session_id.get()
            if session_id and interaction.get_session_auto_approve(session_id):
                return await fn(self, *args, **kwargs)

            # 手动确认：必须能通过 WebSocket 把确认问题送达用户
            sender = ToolSender.from_context()
            if sender is None:
                return format_error("WebSocket 连接不可用")

            interaction_id, future = interaction.register()

            # 载荷 = 被装饰方法的全部命名形参（即工具入参），原样转发，
            # 前端按工具名选用所需字段。被装饰方法按关键字调用、签名
            # 不含 run_manager 等技术参数，因此 kwargs 即用户可见载荷。
            await sender.ask_user(
                tool_name=self.name,
                question=question,
                mode="confirm",
                options=options,
                interaction_id=interaction_id,
                **kwargs,
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
