"""钉住 tools/policies.py 底层原语的契约测试。

不实例化任何工具（仅做类级判定/组装），因此不依赖具体工具模块。

覆盖：
- ``get_args_schema`` 对未显式设置 args_schema 的工具返回 None。
- ``enrich_tool_class`` 恒返回「新子类」且不原地修改原类：
  注入只落在新子类上、包装恒作用在 ``_arun``（全工具 arun 化后不再解析
  ``_run``）、字段已存在时不重复注入、未显式设置 args_schema 却请求注入字段
  时导入期 TypeError。
"""

from typing import Any

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.policies import enrich_tool_class, get_args_schema


# ── 探针：直接子类化 langchain BaseTool，最小可用 ──────────────

class SyncInput(BaseModel):
    x: int = 0


class AsyncInput(BaseModel):
    y: int = 0


class SyncTool(BaseTool):
    name: str = "sync-tool"
    description: str = "sync tool"
    args_schema: type[BaseModel] = SyncInput

    def _run(self, x: int = 0) -> str:  # type: ignore[override]
        return str(x)


class SchemalessTool(BaseTool):
    name: str = "schemaless-tool"
    description: str = "no explicit args_schema"

    def _run(self) -> str:  # type: ignore[override]
        return "ok"


def _identity_wrap(orig: Any) -> Any:
    """生成一个新函数对象的包装（换一层但行为不变），用于类级替换判定。"""

    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        return orig(self, *args, **kwargs)

    return wrapper


# ── get_args_schema ──────────────────────────────────────────


def test_get_args_schema_returns_model_when_set() -> None:
    assert get_args_schema(SyncTool) is SyncInput


def test_get_args_schema_none_when_unset() -> None:
    assert get_args_schema(SchemalessTool) is None


# ── enrich_tool_class：恒新建子类、不原地改原类 ────────────────


def test_enrich_always_returns_new_subclass_not_mutating_original() -> None:
    """即便无任何增强也返回一个新子类；原类与其 args_schema 原封不动。"""
    enriched = enrich_tool_class(SyncTool)
    assert enriched is not SyncTool
    assert issubclass(enriched, SyncTool)
    assert get_args_schema(SyncTool) is SyncInput


def test_enrich_adds_field_to_subclass_not_original() -> None:
    """注入只落在新子类上；重复注入同一字段不再重复叠加、不再改原 schema。"""
    schema_fields = {"flag": (bool, Field(default=False))}
    enriched = enrich_tool_class(SyncTool, schema_fields=schema_fields)
    assert enriched is not SyncTool
    assert "flag" in get_args_schema(enriched).model_fields
    assert "flag" not in get_args_schema(SyncTool).model_fields

    again = enrich_tool_class(enriched, schema_fields=schema_fields)
    assert again is not enriched  # 每次调用都是新子类
    assert "flag" in get_args_schema(again).model_fields
    assert len(get_args_schema(again).model_fields) == len(
        get_args_schema(enriched).model_fields
    )  # flag 未被重复注入


def test_enrich_wrap_always_targets_arun() -> None:
    """包装恒作用在 ``_arun``（SyncTool 未覆写时取 BaseTool._arun 默认实现）。"""
    enriched = enrich_tool_class(SyncTool, wrap_method=_identity_wrap)
    assert issubclass(enriched, SyncTool)
    assert enriched._arun is not SyncTool._arun
    assert enriched._run is SyncTool._run  # _run 不被触碰


def test_enrich_wrap_only_works_on_schemaless_tool() -> None:
    """只包装方法（confirm 路径）不要求工具显式设置 args_schema。"""
    enriched = enrich_tool_class(SchemalessTool, wrap_method=_identity_wrap)
    assert enriched is not SchemalessTool
    assert enriched._arun is not SchemalessTool._arun


def test_enrich_schema_on_schemaless_tool_raises() -> None:
    """请求注入字段却无显式 args_schema → 导入期 TypeError（拒绝静默失效）。"""
    schema_fields = {"flag": (bool, Field(default=False))}
    with pytest.raises(TypeError):
        enrich_tool_class(SchemalessTool, schema_fields=schema_fields)
