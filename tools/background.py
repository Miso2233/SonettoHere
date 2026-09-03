"""background — 「后台运行」工具类装饰器。

把「长耗时操作转入后台、立即返回任务索引」的能力从工具方法中抽离：

- 类装饰器往工具的 args_schema 注入非必填 ``background: bool = False`` 字段；
- 强制包装 ``_arun``（见下），``background=False`` 时原样直通（与未装饰行为
  完全一致）；``background=True`` 时把真实执行体交给后台任务注册表
  （api/agent/background.py）spawn 为独立 asyncio.Task，调用本身立即返回
  统一格式的任务索引，agent 之后用 await_background 工具按索引取回结果。

双模式支持——同步与异步工具都可装饰：

- langchain 的调用最终都走 ``_arun``（子类覆写了 ``_arun`` 时），未覆写时
  ``_arun`` 即 ``BaseTool._arun`` 默认实现——其内部经线程池执行 ``_run``。
  因此强制包装 ``_arun`` 后，async 工具 spawn 的是真实 ``_arun``，同步工具
  spawn 的是「线程池里的 ``_run``」，两条路径统一为同一段 spawn 代码，
  事件循环均不被阻塞，也无需 run_coroutine_threadsafe。
- 包装经 ``functools.wraps`` 保留原签名：async 工具签名声明的 ``run_manager``
  仍会被 langchain 注入并随 kwargs 透传进后台任务（run_python 的流式推送
  与 run_id 链路因此保持不变）。

用法与叠加顺序：

    @get_doc                 # 最外层：get_doc=True 读文档时不 spawn
    @confirm_execution(...)  # 审批先于 spawn
    @background
    class SomeTool(ToolBase):
        ...

适用范围：长耗时工具（网络搜索/抓取、代码执行、大目录扫描、视觉模型
调用）与子 Agent 调用（call_sub_agent——其结果 Future 由子会话自身轮次
resolve，与父轮解耦，后台化天然可行；工具侧配套 detached 等待语义）。
ask_user 系列（值就在于阻塞等用户）、read_image 等返回 Command 的工具
不适用。

被装饰工具经 ``background_mode`` ContextVar 感知自身是否运行在 detached
任务中（spawn 时在新任务上下文内置位），用于分支化后台专属语义（如
call_sub_agent 的等待超时与 detached 事件标记）。
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
                # 直通：sync 工具此时即 BaseTool._arun 默认实现（线程池跑
                # _run），与未装饰时的行为完全一致。
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
        # 强制包装 _arun：sync 工具的 _arun 即 BaseTool._arun 默认实现
        # （内部线程池执行 _run），spawn 该协程即完成后台化且零阻塞。
        method_name="_arun",
        schema_fields={
            "background": (bool, Field(default=False, description=DEFAULT_DESCRIPTION)),
        },
        wrap_method=make_wrapper,
    )


def _spawn_coro(
    orig: Callable[..., Any], self: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> Coroutine[Any, Any, Any]:
    """构造 detached 任务协程：新任务上下文内置位后台模式标记后执行原方法。

    set 发生在新任务自身运行时（协程首次执行），不污染发起调用的上下文，
    后续同步工具调用读到的 background_mode 仍为 False。
    """

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
