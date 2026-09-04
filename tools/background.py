"""background — 「后台运行」类装饰器。

往工具类的 ``args_schema`` 注入非必填 ``background: bool = False`` 字段，并把
``_arun`` 包一层：``background=True`` 时不等待真实执行体完成，将其作为独立
``asyncio.Task`` 交给后台任务注册表（api/agent/background.py）运行，本调用立即
返回统一的任务索引；调用方之后用 ``await_background`` 工具按索引取回结果。
``background=False``（或缺省）时直通，行为与未装饰一致。

后台任务运行在 detached 上下文中：spawn 时把 ``background_mode`` ContextVar 置位，
被装饰工具可据此分支后台专属语义。

用法：

    @background
    class SomeTool(ToolBase):
        async def _arun(self, ...): ...
"""

from __future__ import annotations

import contextvars
import functools
import json
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import Field

from langchain_core.tools import BaseTool

from api.agent import background as background_registry
from api.agent import interaction
from tools.base import format_error, format_success
from tools.policies import INJECTED_KWARGS, enrich_tool_class

DEFAULT_DESCRIPTION = (
    "设为 true 时不等待本工具完成，立即返回任务索引并转入后台运行；"
    "之后用 await_background 工具（index 传返回的 task_index）取回结果。"
    "适合长耗时操作，可在等待期间并行推进其他任务。"
)

ToolClass = type[BaseTool]

# 当前协程是否运行在 detached 后台任务中（spawn 时在新任务上下文内置位）。
# 被装饰工具据此分支化后台专属语义；同步调用路径恒为 False。
background_mode: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "background_mode", default=False
)


def _args_summary(kwargs: dict[str, Any]) -> str:
    """构造后台任务入参摘要（剔除技术性 kwargs），供列表展示与前端提示。

    截断上限与 WebSocket 回调 on_tool_start 的入参截断一致（500 字符）：
    该摘要会在 await_background 完成时作为原工具入参重新分发给提取器
    （run_python 的 code 等长字段依赖它），不宜过短。
    """
    payload = {
        name: value for name, value in kwargs.items() if name not in INJECTED_KWARGS
    }
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)[:500]
    except (TypeError, ValueError):
        return str(payload)[:500]


def background(cls: ToolClass) -> ToolClass:
    """应用「后台运行」类装饰器。

    Args:
        cls: 目标工具类。

    Returns:
        增强后的 pydantic 子类。
    """

    def make_wrapper(orig: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(orig)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            run_background = bool(kwargs.pop("background", False))

            if not run_background:
                # background=False：直接执行，与未装饰时一致。
                return await orig(self, *args, **kwargs)

            session_id = interaction.current_session_id.get()
            if not session_id:
                return format_error(
                    "后台运行需要会话上下文（session_id 缺失），"
                    "请在不带 background 参数的情况下重新调用"
                )

            task = background_registry.get_registry(session_id).register(
                _spawn_coro(orig, self, args, kwargs),
                tool_name=self.name,
                args_summary=_args_summary(kwargs),
            )
            return _format_spawn_result(task.index)

        return wrapper

    return enrich_tool_class(
        cls,
        # enrich 注入 background 字段并包装 _arun（机制见 tools/policies.py）。
        schema_fields={
            "background": (bool, Field(default=False, description=DEFAULT_DESCRIPTION)),
        },
        wrap_method=make_wrapper,
    )


def _spawn_coro(
    orig: Callable[..., Any], self: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """构造 detached 任务协程：在任务自身上下文里置位后台标记后执行原方法。"""

    async def runner() -> Any:
        background_mode.set(True)
        return await orig(self, *args, **kwargs)

    return runner()


def _format_spawn_result(task_index: int) -> str:
    """后台 spawn 的统一返回格式（真实结果稍后经 await_background 取回）。"""
    return format_success(
        {
            "background": True,
            "task_index": task_index,
            "status": "running",
            "hint": (
                f"任务已转入后台运行（索引 {task_index}）。请继续推进其他工作，"
                f"之后调用 await_background 工具（index={task_index}）取回结果。"
            ),
        }
    )
