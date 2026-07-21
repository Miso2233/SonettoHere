"""REST API — 提供商 CRUD 与连接测试。"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.providers import ProviderConfig
from api.providers.enrich import enrich_provider_config
from api.providers.default_llm import refresh_default_llm
from api.providers.manager import ProviderManager, get_manager
from api.providers.openai_provider import OpenAIProvider

router = APIRouter()


# ── Pydantic 请求/响应模型 ──────────────────────────────


class ProviderCreateBody(BaseModel):
    id: str
    provider_type: str = "openai"
    label: str
    api_key: str
    base_url: str
    models: list[str] = []
    enabled: bool = True


class ProviderUpdateBody(BaseModel):
    label: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None
    is_default_provider: bool | None = None
    default_model: str | None = None


class TestConnectionBody(BaseModel):
    api_key: str
    base_url: str
    provider_type: str = "openai"


# ── HELPERS ─────────────────────────────────────────────


def _require_manager() -> ProviderManager:
    mgr = get_manager()
    if mgr is None:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    return mgr


async def _refresh_app_llm() -> None:
    """刷新默认 LLM 缓存。LTM 内部已通过 get_default_llm() 按需获取，无需同步。"""
    refresh_default_llm()


# ── CRUD ────────────────────────────────────────────────


@router.get("/providers")
def list_providers(request: Request) -> dict:
    """返回所有已配置的提供商（含未启用的）。"""
    configs = _require_manager().list_configs()
    return {"providers": [c.to_dict() for c in configs]}


@router.get("/providers/{provider_id}")
def get_provider(provider_id: str, request: Request) -> dict:
    """获取单个提供商配置。"""
    config = _require_manager().get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return config.to_dict()


@router.post("/providers")
async def create_provider(body: ProviderCreateBody, request: Request) -> dict:
    """新增提供商，并自动对模型进行元数据测定与填充。"""
    mgr = _require_manager()
    if mgr.get_config(body.id) is not None:
        raise HTTPException(
            status_code=409, detail=f"Provider '{body.id}' already exists"
        )

    config = ProviderConfig(
        id=body.id,
        provider_type=body.provider_type,
        label=body.label,
        api_key=body.api_key,
        base_url=body.base_url,
        models=body.models,
        enabled=body.enabled,
    )

    # 并发检测视觉能力和填充上下文窗口
    await enrich_provider_config(config)

    # 统一写入 YAML（含 model_vision + model_context_windows）
    mgr.save_config(config)

    await _refresh_app_llm()
    return config.to_dict()


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdateBody, request: Request) -> dict:
    """更新提供商配置（部分字段），并重新对模型进行元数据测定与填充。"""
    mgr = _require_manager()
    config = mgr.get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = body.model_dump(exclude_unset=True)

    # 唯一性约束：设置 is_default_provider=True 时清除其他供应商的标记
    if update_data.get("is_default_provider") is True:
        all_configs = mgr.list_configs()
        for other in all_configs:
            if other.id != provider_id and other.is_default_provider:
                other.is_default_provider = False
                mgr.save_config(other)

    # 验证 default_model 在当前 models 列表中
    if "default_model" in update_data:
        dm = update_data["default_model"]
        models = update_data.get("models", config.models)
        if dm is not None and dm not in models:
            raise HTTPException(
                status_code=400,
                detail=f"Default model '{dm}' is not in the provider's model list",
            )

    for field, value in update_data.items():
        setattr(config, field, value)

    # 并发检测视觉能力和填充上下文窗口
    await enrich_provider_config(config)

    # 统一写入 YAML（含 model_vision + model_context_windows）
    mgr.save_config(config)

    await _refresh_app_llm()
    return config.to_dict()


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str, request: Request) -> dict:
    """删除提供商配置。"""
    if not _require_manager().delete_config(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    await _refresh_app_llm()
    return {"status": "deleted"}


# ── 连接测试与模型发现 ─────────────────────────────────


def _build_temp_provider(body: TestConnectionBody) -> OpenAIProvider:
    """根据请求体凭据临时创建 provider 用于测试。"""
    return OpenAIProvider(
        ProviderConfig(
            id="_test_",
            provider_type=body.provider_type,
            label="",
            api_key=body.api_key,
            base_url=body.base_url,
        )
    )


@router.post("/providers/test")
async def test_connection(body: TestConnectionBody) -> dict:
    """测试任意凭据的连接（前端向导填写凭据后调用）。"""
    provider = _build_temp_provider(body)
    result = await provider.check_health()
    return {
        "status": result.status,
        "latency_ms": result.latency_ms,
        "detail": result.detail,
    }


@router.post("/providers/{provider_id}/test")
async def test_existing_provider(provider_id: str, request: Request) -> dict:
    """测试已保存提供商的连接。"""
    mgr = _require_manager()
    try:
        provider = mgr.get(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Provider not found or not enabled")
    result = await provider.check_health()
    return {
        "status": result.status,
        "latency_ms": result.latency_ms,
        "detail": result.detail,
    }


@router.post("/providers/discover-models")
async def discover_models(body: TestConnectionBody) -> dict:
    """根据凭据拉取模型列表（前端向导步骤 3）。"""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=body.api_key, base_url=body.base_url)
        models = await client.models.list()
        model_names = sorted(m.id for m in models.data)

        from api.providers.model_context_windows import lookup_context_window
        model_context_windows: dict[str, int] = {}
        for m in models.data:
            ctx = lookup_context_window(m.id)
            if ctx:
                model_context_windows[m.id] = ctx

        return {"models": model_names, "model_context_windows": model_context_windows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/providers/{provider_id}/discover-models")
async def discover_models_for_existing(provider_id: str, request: Request) -> dict:
    """拉取已保存提供商的模型列表并更新缓存。

    重新拉取后，如果原来的 default_model 已不存在，自动置 None 并返回警告。
    """
    from openai import AsyncOpenAI
    from api.providers.model_context_windows import lookup_context_window

    mgr = _require_manager()
    config = mgr.get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        models = await client.models.list()
        model_names = sorted(m.id for m in models.data)

        # 从 OpenRouter 查找模型上下文窗口
        model_context_windows: dict[str, int] = {}
        for m in models.data:
            ctx = lookup_context_window(m.id)
            if ctx:
                model_context_windows[m.id] = ctx

        # 检查 default_model 是否还在新列表中（仅提示，不做保存）
        warning = None
        if config.default_model is not None and config.default_model not in model_names:
            warning = f"Default model '{config.default_model}' is no longer available and has been reset"

        return {
            "models": model_names,
            "model_context_windows": model_context_windows,
            "default_model_warning": warning,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
