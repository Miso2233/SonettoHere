"""工具策略类装饰器的共享底层原语。

confirm_execution 与 get_doc 都改在类层面「操控整个工具类」：解析 langchain
真正会调用的执行方法（``_run`` 还是 ``_arun``）、必要时替换其实现，并向工具
的 ``args_schema``（Input pydantic 模型）注入附加字段。本模块收敛这些
pydantic / langchain 细节，供各策略类装饰器复用，避免各自复制一份。

关键机制（pydantic 2.13 / langchain-core 1.3 实证，见 langchain_core/tools/base.py）：

- 子类覆写了 ``_arun`` 时，langchain 的异步/同步调用最终都走 ``_arun``
  （``BaseTool.arun`` 按 ``cls._arun is not BaseTool._arun`` 判定选执行函数）；
  否则走 ``_run``（``BaseTool._arun`` 默认在线程池里执行 ``_run``）。
  因此解析执行方法的规则恰好与 langchain 自身的判定一致。
- 事后改写 pydantic 字段（``cls.args_schema = X`` 或改
  ``model_fields["args_schema"].default``）都不生效——pydantic v2 在类创建时
  捕获字段默认值。要覆写字段，必须返回一个 pydantic **新子类**，在其命名空间里
  用 ``__annotations__`` 重声明 ``args_schema`` 字段。
- 给 Input 模型追加字段用 ``create_model(orig.__name__, __base__=orig, ...)``，
  兼容已含 ``Annotated[..., InjectedToolCallId]`` 的模型。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, create_model
from langchain_core.tools import BaseTool

from typing import Callable

# langchain 可能注入、以及策略自身消耗的技术性 kwargs——永远不该进
# ask_user 确认载荷（用户可见字段之外的实现细节）。
INJECTED_KWARGS: frozenset[str] = frozenset({
    "run_manager", "config", "callbacks", "get_doc",
})


def exec_method_name(cls: type[BaseTool]) -> str:
    """返回 langchain 实际会调用的执行方法名（镜像 BaseTool.arun 的判定）。"""
    if cls._arun is not BaseTool._arun:
        return "_arun"
    return "_run"


def current_input(cls: type[BaseTool]) -> type[BaseModel] | None:
    """返回工具当前的 args_schema（Input pydantic 模型），未设置时为 None。"""
    default = cls.model_fields["args_schema"].default
    if isinstance(default, type) and issubclass(default, BaseModel):
        return default
    return None


def add_input_field(
    orig: type[BaseModel],
    name: str,
    typ: type,
    field: Field,
) -> type[BaseModel]:
    """在 Input 模型上追加一个字段，返回（可能新建的）模型。

    幂等：字段已存在时原样返回。新模型以 ``create_model`` 子类化 *orig* 生成，
    保留其既有全部字段与校验，并把 *name* 追加到末尾（非必填、带默认值）。
    """
    if name in orig.model_fields:
        return orig
    return create_model(
        orig.__name__,
        __base__=orig,
        **{name: (typ, field)},
    )


def enrich_tool_class(
    cls: type[BaseTool],
    *,
    schema_fields: dict[str, tuple[type, Field]] | None = None,
    wrap_method: Callable[[Callable], Callable] | None = None,
) -> type[BaseTool]:
    """返回一个（必要时新建的）pydantic 子类，应用两类增强：

    - ``schema_fields``：往工具的 args_schema 注入字段；
    - ``wrap_method``：把真正执行的方法（``_run``/``_arun``）替换为包装结果。

    无任何增强时原样返回 *cls*。字段覆写必须通过新建子类完成（见模块注释），
    故始终返回 ``type(name, (cls,), namespace)``。继承链上再套一层策略
    （如 get_doc 叠在 confirm 之上）得到的是子类套子类，天然构成
    外层→内层→核心 的调用链。
    """
    if not schema_fields and wrap_method is None:
        return cls

    new_input = current_input(cls)
    if schema_fields and new_input is not None:
        for name, (typ, field) in schema_fields.items():
            new_input = add_input_field(new_input, name, typ, field)

    method_name = exec_method_name(cls)
    orig = getattr(cls, method_name)

    namespace: dict[str, object] = {
        "__module__": cls.__module__,
        "__qualname__": cls.__qualname__,
        "__doc__": cls.__doc__,
    }
    if schema_fields and new_input is not None and new_input is not current_input(cls):
        namespace["args_schema"] = new_input
        namespace["__annotations__"] = {"args_schema": type[BaseModel]}
    if wrap_method is not None:
        namespace[method_name] = wrap_method(orig)

    return type(cls.__name__, (cls,), namespace)
