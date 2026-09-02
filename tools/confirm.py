"""confirm_execution — 「执行前确认」工具类装饰器。

把「执行危险操作前先征得用户同意」的门控逻辑从工具方法中抽离：

- 会话开启自动执行（auto_approve）时直接放行，不打扰用户；
- 否则要求 WebSocket 连接可用，通过 ask_user(mode="confirm") 弹出确认，
  用户 approve 后调用被装饰方法，reject 返回统一拒绝错误；
- 用户中途取消（CancelledError）返回统一取消错误；注册的交互在 finally 清理。

auto mode 信号统一取自会话级 auto_approve（interaction._settings，由 WebSocket
层写入），对**所有受装饰工具一致生效**，无需逐个传参。

作为「针对工具类」的装饰器，与 @get_doc（tools/get_doc.py）共用类装饰器框架
（tools/policies.py 的 ``enrich_tool_class``）：解析 langchain 真正会调用的异步
执行方法（``_arun``，同步 ``_run`` 无法承载异步确认），在其外层包一层同构
wrapper，并通过 ``functools.wraps`` 保留原签名。因此：

- 装饰目标是**工具类**而非单个方法；可与其它类装饰器叠层。与 get_doc 同用时
  必须 ``@get_doc`` 在**外层**、本装饰器在内层：``get_doc=True`` 读文档时在本
  装饰器（ask_user）之前短路，不弹确认框；顺序反转则读文档也会先弹确认。
- 仅支持异步执行工具：装饰到只覆写同步 ``_run`` 的类在导入期抛 TypeError。
- 确认气泡载荷 = 被装饰方法（除 INJECTED_KWARGS 技术参数：run_manager / config
  / callbacks / get_doc 外）的全部命名形参，由 wrapper 从 ``**kwargs`` 剔除技术
  参数后构造，原样转发给 ask_user。langchain 始终以**纯关键字**调用执行方法
  （输入经 args_schema 校验后透传），故 kwargs 即用户可见入参，前端按工具名选用
  字段。因此被装饰方法必须以关键字参数被调用、且不含非用户可见的注入注解
  （InjectedToolCallId 等不在 INJECTED_KWARGS 内，会漏进载荷）。
- 被装饰方法签名可声明 ``run_manager`` 等技术形参（langchain 仅当签名声明时才
  注入）。wrapper 批准后把含技术参数的完整 ``**kwargs`` **原样透传**给原方法
  （只从载荷副本剔除，绝不在 kwargs 上 pop）——run_id 等仅在批准后由原方法取出
  使用，同一 asyncio 任务内 set/read 天然隔离，确认等待期间 langchain run 保持
  开启、run_id 不可变，无副作用。

适用范围：run_python 及 5 个破坏性/写入 file 工具（file_write / file_edit /
file_delete / file_create_directory / file_rename）——仅这些执行前需放行的工具。
ask_qa / single_choice / multi_choice 属于「采集输入」语义（收集后继续，而非
确认后放行），不适用。
"""

from __future__ import annotations

import asyncio
import functools
import inspect
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
            # 确认依赖异步 ask_user，同步 _run 无法承载：在 enrich_tool_class
            # 内部解析执行方法后、生成子类前校验，非异步工具导入期即 fail-fast。
            if not inspect.iscoroutinefunction(orig):
                raise TypeError(
                    "confirm_execution 仅支持异步执行工具（须覆写 async _arun）；"
                    f"{target.__name__} 的真实执行方法是同步的 {orig.__name__}"
                )

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
