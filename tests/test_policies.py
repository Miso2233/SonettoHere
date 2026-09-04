"""钉住 tools/policies.py 底层原语的契约测试。

不实例化任何工具（仅做类级判定/组装），因此不依赖具体工具模块。

覆盖：
- ``exec_method_name`` 镜像 langchain 的执行方法判定（sync → _run，async → _arun）；
  这是与 langchain-core 内部实现绑定的版本敏感契约，升级时此测试应最先报红。
- ``get_args_schema`` 对未显式设置 args_schema 的工具返回 None。
- ``enrich_tool_class`` 的幂等性：字段已存在时不再注入、不再产生新子类。
- 未显式设置 args_schema 却请求注入字段 → 导入期 TypeError（拒绝静默失效）。
- 只包装方法（confirm 路径）不要求工具显式设置 args_schema。
"""

from typing import Any

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.policies import enrich_tool_class, exec_method_name, get_args_schema


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


class AsyncTool(BaseTool):
    name: str = "async-tool"
    description: str = "async tool"
    args_schema: type[BaseModel] = AsyncInput

    async def _arun(self, y: int = 0) -> str:  # type: ignore[override]
        return str(y)


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


# ── exec_method_name 契约 ────────────────────────────────────


def test_exec_method_name_sync_tool_is_run() -> None:
    """未覆写 _arun 的工具走同步 _run（BaseTool._arun 默认经线程池执行 _run）。"""
    assert exec_method_name(SyncTool) == "_run"


def test_exec_method_name_async_tool_is_arun() -> None:
    """覆写了 _arun 的工具，langchain 的同步/异步调用最终都走 _arun。"""
    assert exec_method_name(AsyncTool) == "_arun"


def test_exec_method_name_survives_enrich() -> None:
    """包装后仍是同一种执行方法名（子类套子类不改变解析结果）。"""
    enriched = enrich_tool_class(AsyncTool, wrap_method=_identity_wrap)
    assert exec_method_name(enriched) == "_arun"


# ── get_args_schema ──────────────────────────────────────────


def test_get_args_schema_returns_model_when_set() -> None:
    assert get_args_schema(SyncTool) is SyncInput


def test_get_args_schema_none_when_unset() -> None:
    assert get_args_schema(SchemalessTool) is None


# ── enrich_tool_class 幂等与失效策略 ──────────────────────────


def test_enrich_no_op_returns_same_class() -> None:
    """无 schema_fields 且无 wrap_method → 原样返回，不产生子类。"""
    assert enrich_tool_class(SyncTool) is SyncTool


def test_enrich_field_already_present_returns_same_class() -> None:
    """字段已存在（幂等）且不包装 → 不再注入、不再套子类。"""
    schema_fields = {"x": (int, Field(default=0))}  # x 已在 SyncInput
    assert enrich_tool_class(SyncTool, schema_fields=schema_fields) is SyncTool


def test_enrich_schema_on_schemaless_tool_raises() -> None:
    """请求注入字段却无显式 args_schema → 导入期 TypeError（拒绝静默失效）。"""
    schema_fields = {"flag": (bool, Field(default=False))}
    with pytest.raises(TypeError):
        enrich_tool_class(SchemalessTool, schema_fields=schema_fields)


def test_enrich_wrap_only_works_on_schemaless_tool() -> None:
    """只包装方法（confirm 路径）不要求工具显式设置 args_schema。"""
    enriched = enrich_tool_class(SchemalessTool, wrap_method=_identity_wrap)
    assert enriched is not SchemalessTool
    assert enriched._run is not SchemalessTool._run


def test_enrich_adds_field_to_subclass_not_original() -> None:
    """注入只落在新子类上，原类 schema 不被原地改写。"""
    schema_fields = {"flag": (bool, Field(default=False))}
    enriched = enrich_tool_class(SyncTool, schema_fields=schema_fields)
    assert enriched is not SyncTool
    assert "flag" in get_args_schema(enriched).model_fields
    assert "flag" not in get_args_schema(SyncTool).model_fields
    # 重复注入同一字段 → 幂等，不再套新层
    again = enrich_tool_class(enriched, schema_fields=schema_fields)
    assert again is enriched
