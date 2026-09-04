"""类装饰器（confirm_execution / get_doc / background）共享的底层原语。

这些装饰器都在「类层面」操控整个工具类：解析 langchain 真正会调用的执行方法
（``_run`` / ``_arun``）、必要时替换其实现，并向工具的 ``args_schema``（Input
pydantic 模型）注入附加字段。本模块收敛这些 pydantic / langchain 细节，供各
策略类装饰器复用，避免各自复制一份。

两个必须先理解的框架事实（pydantic 2.13 / langchain-core 1.3 实证，见
langchain_core/tools/base.py）：

1. 执行方法的判定镜像 langchain 自身：子类覆写 ``_arun`` 时，同步/异步调用最终
   都走 ``_arun``（``BaseTool.arun`` 按 ``cls._arun is not BaseTool._arun`` 选执行
   函数）；否则走 ``_run``（``BaseTool._arun`` 默认在线程池里执行 ``_run``）。
   见 ``exec_method_name``。
2. 字段只能在 pydantic **新子类**上覆写：pydantic v2 在类创建时捕获字段默认值，
   事后 ``cls.args_schema = X`` 或改 ``model_fields["args_schema"].default`` 都不
   生效。因此 enrich 在确有改动时返回 ``type(cls.__name__, (cls,), namespace)``
   新子类，并在其命名空间里用 ``__annotations__`` 重声明 ``args_schema``；
   给 Input 模型追加字段则用 ``create_model(orig.__name__, __base__=orig, ...)``，
   兼容已含 ``Annotated[..., InjectedToolCallId]`` 的模型。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

# args_schema 字段规格：(字段注解类型, Field(...) 产生的 FieldInfo)。
# 装饰器按此约定注入「策略开关」字段（如 get_doc / background）。
FieldSpec = tuple[type[Any], FieldInfo]

# langchain 可能注入、以及策略自身消耗的技术性 kwargs——永远不该进 ask_user
# 确认载荷或后台任务摘要（用户可见字段之外的实现细节）。
INJECTED_KWARGS: frozenset[str] = frozenset({
    "run_manager", "config", "callbacks", "get_doc", "background",
})


def exec_method_name(cls: type[BaseTool]) -> str:
    """返回 langchain 实际会调用的执行方法名（镜像 ``BaseTool.arun`` 的判定）。

    判据必须与 langchain 保持一致（覆写 ``_arun`` 走 ``_arun``，否则 ``_run``）；
    langchain-core 若改动此判定，本函数应在契约测试中报红。注册工具已全 arun 化，
    对它们本函数恒返回 ``_arun``；保留 _run 分支仅用于容忍未经转换的第三方子类。
    """
    if cls._arun is not BaseTool._arun:
        return "_arun"
    return "_run"


def get_args_schema(cls: type[BaseTool]) -> type[BaseModel] | None:
    """返回工具当前的 args_schema（Input pydantic 模型），未设置时返回 None。"""
    default = cls.model_fields["args_schema"].default
    if isinstance(default, type) and issubclass(default, BaseModel):
        return default
    return None


def _schema_with_extra_fields(
    cls: type[BaseTool],
    schema_fields: dict[str, FieldSpec] | None,
) -> type[BaseModel] | None:
    """把 *schema_fields* 注入 Input 模型，返回增强后的模型；无需改动时返回 None。

    - 字段已在模型上则跳过（幂等：多套策略叠层时不会重复注入）。
    - 工具未显式设置 args_schema 时字段将静默不生效（对应包装恒直通）——装饰器
      声明了能力却被悄然丢弃。此处直接抛 TypeError，让失效在导入期显性暴露
      （与 confirm_execution 对非异步工具 fail-fast 的做法一致）。
    """
    if not schema_fields:
        return None
    base = get_args_schema(cls)
    if base is None:
        raise TypeError(
            f"{cls.__name__} 未显式设置 args_schema，无法注入字段 "
            f"{sorted(schema_fields)}"
        )
    additions = {
        name: (annotation, field)
        for name, (annotation, field) in schema_fields.items()
        if name not in base.model_fields
    }
    if not additions:
        return None
    # 一次 create_model 建出携带全部新字段的单层子类：__base__=base 保留既有
    # 字段与校验，新字段追加在末尾。
    return create_model(base.__name__, __base__=base, **additions)


def _wrapped_exec_method(
    cls: type[BaseTool],
    wrap_method: Callable[[Callable[..., Any]], Callable[..., Any]] | None,
    method_name: str,
) -> tuple[str, Callable[..., Any]] | None:
    """解析 *method_name* 指向的方法并交给 *wrap_method* 包装。

    返回 (方法名, 包装后的方法)；*wrap_method* 为空时不包装（返回 None）。
    此处只读不写原类，替换发生在 enrich 生成的新子类上。
    """
    if wrap_method is None:
        return None
    return method_name, wrap_method(getattr(cls, method_name))


def enrich_tool_class(
    cls: type[BaseTool],
    *,
    schema_fields: dict[str, FieldSpec] | None = None,
    wrap_method: Callable[[Callable[..., Any]], Callable[..., Any]] | None = None,
    method_name: str | None = None,
) -> type[BaseTool]:
    """应用两类类级增强，返回一个（必要时新建的）子类：

    - ``schema_fields``：向 args_schema 注入字段；
    - ``wrap_method``：把真正执行的方法（``_run``/``_arun``）替换为包装结果。

    两种增强都无实际改动时原样返回 *cls*；否则返回
    ``type(name, (cls,), namespace)`` 新子类（字段覆写必须落在新子类上，见模块
    注释）。继承链上再套一层策略（如 get_doc 叠在 confirm 之上）得到的是子类套
    子类，天然构成 外层→内层→核心 的调用链。

    ``method_name`` 可显式指定要包装的方法名，覆盖 ``exec_method_name`` 的默认
    解析（如 background 装饰器强制包装 ``_arun``，使纯同步工具也能后台化——同步
    工具未覆写 ``_arun`` 时，该名字解析到 langchain 的默认实现，其内部经线程池
    执行 ``_run``）。
    """
    name = method_name or exec_method_name(cls)
    new_schema = _schema_with_extra_fields(cls, schema_fields)
    new_method = _wrapped_exec_method(cls, wrap_method, name)
    if new_schema is None and new_method is None:
        return cls

    namespace: dict[str, object] = {
        "__module__": cls.__module__,
        "__qualname__": cls.__qualname__,
        "__doc__": cls.__doc__,
    }
    if new_schema is not None:
        # 仅赋值 args_schema 属性不生效：pydantic 在类创建时捕获字段，须在子类
        # 命名空间里同时用 __annotations__ 重声明 args_schema 才算「覆写字段」。
        namespace["args_schema"] = new_schema
        namespace["__annotations__"] = {"args_schema": type[BaseModel]}
    if new_method is not None:
        wrapped_name, wrapped = new_method
        namespace[wrapped_name] = wrapped

    return type(cls.__name__, (cls,), namespace)
