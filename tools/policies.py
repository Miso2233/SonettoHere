"""类装饰器（confirm_execution / get_doc / background）共享的底层原语。

仓库里的工具已全部统一为「真身 ``async def _arun``」形态，因此这些装饰器
无需再判断执行方法是 ``_run`` 还是 ``_arun`` —— 一律包装 ``_arun``、只产出
async wrapper。本模块收敛这类「类级增强」所需的 pydantic / langchain 细节。

框架事实（pydantic 2.x）：字段默认值在类创建时被捕获，事后改 ``cls.args_schema``
或 ``model_fields["args_schema"].default`` 都不生效；要追加/覆写字段只能返回一个
**pydantic 新子类**，在其命名空间里用 ``__annotations__`` 重声明 ``args_schema``。
追加字段用 ``create_model(orig.__name__, __base__=orig, ...)`` 生成携带新字段的
Input 模型，保留原字段与校验（兼容已含 ``Annotated[..., InjectedToolCallId]``
的模型）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

# args_schema 字段规格：(字段注解类型, Field(...) 产生的 FieldInfo)。
FieldSpec = tuple[type[Any], FieldInfo]

# langchain 可能注入、以及策略自身消耗的技术性 kwargs —— 不该进 ask_user 确认
# 载荷或后台任务摘要（用户可见字段之外的实现细节）。
INJECTED_KWARGS: frozenset[str] = frozenset({
    "run_manager", "config", "callbacks", "get_doc", "background",
})


def get_args_schema(cls: type[BaseTool]) -> type[BaseModel] | None:
    """返回工具当前的 args_schema（Input pydantic 模型），未显式设置时返回 None。"""
    default = cls.model_fields["args_schema"].default
    if isinstance(default, type) and issubclass(default, BaseModel):
        return default
    return None


def _schema_with_extra_fields(
    cls: type[BaseTool],
    schema_fields: dict[str, FieldSpec] | None,
) -> type[BaseModel] | None:
    """把 *schema_fields* 注入 Input 模型，返回增强后的模型；无新增字段时返回 None。

    - 字段已在模型上则跳过（同名策略开关在叠层时不会被重复注入）。
    - 工具未显式设置 args_schema 时字段将静默不生效，属「装饰器声明了能力却被丢弃」，
      故直接抛 TypeError，让失效在导入期显性暴露。
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
    # 一次 create_model 建出携带全部新字段的单层子类（__base__=base 保留原字段与校验）。
    return create_model(base.__name__, __base__=base, **additions)


def enrich_tool_class(
    cls: type[BaseTool],
    *,
    schema_fields: dict[str, FieldSpec] | None = None,
    wrap_method: Callable[[Callable[..., Any]], Callable[..., Any]] | None = None,
) -> type[BaseTool]:
    """对工具类应用两类「类级增强」，返回它的一个新子类（纯函数，不改原类）：

    - ``schema_fields``：向 args_schema 注入策略开关字段；
    - ``wrap_method``：把 ``_arun`` 替换为包装结果。

    ``_arun`` 一定可取（覆写即真实异步体；未覆写时取 ``BaseTool._arun`` 默认实现，
    其内部经线程池执行 ``_run``），故无需解析 sync/async。

    每次调用都新建子类：叠加策略（get_doc 叠在 confirm / background 之上）天然构成
    外层→内层→核心 的调用链。重复应用同一策略会再包一层（方法被二次包装），
    属调用方责任，本函数不做隐式去重。
    """
    namespace: dict[str, object] = {
        "__module__": cls.__module__,
        "__qualname__": cls.__qualname__,
        "__doc__": cls.__doc__,
    }
    new_schema = _schema_with_extra_fields(cls, schema_fields)
    if new_schema is not None:
        # 仅赋值 args_schema 不生效：pydantic 在类创建时捕获字段，须在子类命名空间
        # 里同时用 __annotations__ 重声明 args_schema 才算「覆写字段」。
        namespace["args_schema"] = new_schema
        namespace["__annotations__"] = {"args_schema": type[BaseModel]}
    if wrap_method is not None:
        namespace["_arun"] = wrap_method(cls._arun)
    return type(cls.__name__, (cls,), namespace)
