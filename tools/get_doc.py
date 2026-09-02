"""@get_doc — 「按需返回领域文档」类装饰器。

把散落在每个工具类里的 get_doc 样板（args_schema 的 ``get_doc`` 字段、执行方法
签名首参、``if get_doc: return self._load_doc()`` 分支）收敛到一处：

- 类装饰器往工具的 ``args_schema`` 注入非必填 ``get_doc: bool = False`` 字段；
- 按 langchain 真正的执行方法（``_run``/``_arun``，见 tools/policies.py）包一层
  同构 wrapper：``get_doc=True`` 时短路返回 ``self._load_doc()``（TOOL.md 按目录
  加载，返回普通字符串），否则原样转发给原方法；
- wrapper 通过 ``functools.wraps`` 保留原签名，不影响 langchain 的
  ``run_manager`` 注入与模型侧 schema（模型侧只认 args_schema）。

用法：

    @get_doc
    class SomeSyncTool(ToolBase):
        ...

    @get_doc(field_description="设为 true 以获取使用说明和领域知识")
    class SomeAsyncTool(ToolBase):
        async def _arun(self, ...): ...

设计约定：

- 返回文档走普通字符串路径，绝不发 ask_user、绝不返回 Command。
  read_image 的 ``Command(goto=model)`` 仅服务于图片 base64 进消息流，
  get_doc 不做特殊返回（ToolNode 会把 str 归一为 ToolMessage）。
- 类装饰器返回 pydantic 新子类（见 tools/policies.py），因此可叠在
  confirm 策略外层：``@get_doc`` 之下先过 confirm，``get_doc=True`` 时在
  ask_user 之前短路——读文档不弹确认框。
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from pydantic import Field

from langchain_core.tools import BaseTool

from tools.policies import enrich_tool_class

DEFAULT_DESCRIPTION = "设为 true 以获取使用说明"

ToolClass = type[BaseTool]


def get_doc(
    cls: ToolClass | None = None,
    *,
    field_description: str = DEFAULT_DESCRIPTION,
) -> ToolClass | Callable[[ToolClass], ToolClass]:
    """构造/应用 get_doc 类装饰器。

    Args:
        cls: ``@get_doc`` 裸用时的目标工具类。
        field_description: 注入到 args_schema 的 get_doc 字段描述，
            用于保留各工具原有 schema 文案。

    Returns:
        传入 *cls* 时返回增强后的 pydantic 子类；未传入时返回待应用的装饰器。
    """

    def decorator(target: ToolClass) -> ToolClass:
        def make_wrapper(orig: Callable[..., Any]) -> Callable[..., Any]:
            if inspect.iscoroutinefunction(orig):

                @functools.wraps(orig)
                async def async_wrapper(
                    self: Any, *args: Any, **kwargs: Any
                ) -> Any:
                    if kwargs.pop("get_doc", False):
                        return self._load_doc()
                    return await orig(self, *args, **kwargs)

                return async_wrapper

            @functools.wraps(orig)
            def sync_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if kwargs.pop("get_doc", False):
                    return self._load_doc()
                return orig(self, *args, **kwargs)

            return sync_wrapper

        return enrich_tool_class(
            target,
            schema_fields={
                "get_doc": (bool, Field(default=False, description=field_description)),
            },
            wrap_method=make_wrapper,
        )

    if cls is not None:
        return decorator(cls)
    return decorator
