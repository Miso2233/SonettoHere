"""@get_doc — 「按需返回领域文档」类装饰器。

往工具类的 ``args_schema`` 注入非必填 ``get_doc: bool = False`` 字段，并把
``_arun`` 包一层：``get_doc=True`` 时短路返回 ``self._load_doc()``（同目录
TOOL.md，经线程池离环读取），否则原样转发原方法。返回的是普通字符串文档。

用法：

    @get_doc
    class SomeTool(ToolBase):
        async def _arun(self, ...): ...

无参装饰器；``get_doc`` 字段统一使用 ``DEFAULT_DESCRIPTION`` 文案，更长的引导
文案请写入同目录 TOOL.md（``get_doc=True`` 返回的内容），不要塞进 schema。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from pydantic import Field

from langchain_core.tools import BaseTool

from tools.base import off_thread
from tools.policies import enrich_tool_class

DEFAULT_DESCRIPTION = "设为 true 以获取使用说明"

ToolClass = type[BaseTool]


def get_doc(cls: ToolClass) -> ToolClass:
    """应用「按需返回领域文档」类装饰器。

    Args:
        cls: 目标工具类。

    Returns:
        增强后的 pydantic 子类。
    """

    def make_wrapper(orig: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(orig)
        async def async_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if kwargs.pop("get_doc", False):
                # TOOL.md 磁盘读取离环，避免卡事件循环
                return await off_thread(self._load_doc)
            return await orig(self, *args, **kwargs)

        return async_wrapper

    return enrich_tool_class(
        cls,
        schema_fields={
            "get_doc": (bool, Field(default=False, description=DEFAULT_DESCRIPTION)),
        },
        wrap_method=make_wrapper,
    )
