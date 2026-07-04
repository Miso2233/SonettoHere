"""REST API — 提供商 CRUD、连接测试、能力检测。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.providers import ProviderConfig
from api.providers.capabilities import get_all_testers, test_model_capabilities
from api.dependencies import get_llm

router = APIRouter()

# 视觉能力测试图片路径
IMAGE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "SonettoTest.png"
)


# ── Pydantic 请求/响应模型 ──────────────────────────────


class ProviderCreateBody(BaseModel):
    id: str
    provider_type: str = "openai"
    label: str
    api_key: str
    base_url: str
    models: list[str] = []
    enabled: bool = True
    context_window: int = 256_000


class ProviderUpdateBody(BaseModel):
    label: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None
    context_window: int | None = None
    is_default_provider: bool | None = None
    default_model: str | None = None


class TestConnectionBody(BaseModel):
    api_key: str
    base_url: str
    provider_type: str = "openai"


class TestCapabilityBody(BaseModel):
    model_name: str
    capability: str | None = None  # None = 测试所有能力


# ── HELPERS ─────────────────────────────────────────────


def _get_manager(request: Request):
    return request.app.state.provider_manager


async def _refresh_app_llm(request: Request) -> None:
    """从 provider_manager 刷新 app.state.llm，同步 LTM 消费者生命周期。"""
    mgr = _get_manager(request)
    old_llm = getattr(request.app.state, "llm", None)
    ltm = getattr(request.app.state, "ltm", None)

    try:
        request.app.state.llm = get_llm(mgr)
        if old_llm is None and ltm is not None and not ltm.is_listening:
            ltm.start_listening(
                request.app.state.llm,
                ws_registry=request.app.state.ws_registry,
            )
            print("[provider] LLM became available — LTM consumer started")
    except RuntimeError:
        request.app.state.llm = None
        if ltm is not None and ltm.is_listening:
            await ltm.stop_listening()
            print("[provider] LLM became unavailable — LTM consumer stopped")


def _get_testers() -> list:
    """获取可用的能力检测器列表。"""
    from api.providers.capabilities.vision import VisionTester
    from api.providers.capabilities.tool_call import ToolCallTester
    from api.providers.capabilities.structured_output import StructuredOutputTester

    testers = [ToolCallTester(), StructuredOutputTester()]
    if IMAGE_PATH.exists():
        testers.append(VisionTester(IMAGE_PATH))
    return testers


# ── CRUD ────────────────────────────────────────────────


@router.get("/providers")
def list_providers(request: Request):
    """返回所有已配置的提供商（含未启用的）。"""
    configs = _get_manager(request).list_configs()
    return {"providers": [c.to_dict() for c in configs]}


@router.get("/providers/{provider_id}")
def get_provider(provider_id: str, request: Request):
    """获取单个提供商配置。"""
    config = _get_manager(request).get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return config.to_dict()


@router.post("/providers")
async def create_provider(body: ProviderCreateBody, request: Request):
    """新增提供商（不再自动检测能力，需用户手动触发）。"""
    mgr = _get_manager(request)
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
        context_window=body.context_window,
    )

    mgr.save_config(config)
    await _refresh_app_llm(request)
    return config.to_dict()


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdateBody, request: Request):
    """更新提供商配置（部分字段），不再自动检测能力。"""
    mgr = _get_manager(request)
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

    mgr.save_config(config)
    await _refresh_app_llm(request)
    return config.to_dict()


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str, request: Request):
    """删除提供商配置。"""
    if not _get_manager(request).delete_config(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    await _refresh_app_llm(request)
    return {"status": "deleted"}


# ── 连接测试与模型发现 ─────────────────────────────────


def _build_temp_provider(body: TestConnectionBody):
    """根据请求体凭据临时创建 provider 用于测试。"""
    from api.providers.openai_provider import OpenAIProvider

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
async def test_connection(body: TestConnectionBody):
    """测试任意凭据的连接（前端向导填写凭据后调用）。"""
    provider = _build_temp_provider(body)
    result = await provider.check_health()
    return {
        "status": result.status,
        "latency_ms": result.latency_ms,
        "detail": result.detail,
    }


@router.post("/providers/{provider_id}/test")
async def test_existing_provider(provider_id: str, request: Request):
    """测试已保存提供商的连接。"""
    mgr = _get_manager(request)
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
async def discover_models(body: TestConnectionBody):
    """根据凭据拉取模型列表（前端向导步骤 3）。"""
    from openai import AsyncOpenAI
    from api.data.model_context_windows import get_context_window

    try:
        client = AsyncOpenAI(api_key=body.api_key, base_url=body.base_url)
        models = await client.models.list()
        model_names = sorted(m.id for m in models.data)

        # 尝试从 API 元数据获取上下文窗口
        model_context_windows: dict[str, int] = {}
        for m in models.data:
            ctx = getattr(m, "max_context_length", None) or getattr(m, "context_window", None)
            if ctx:
                model_context_windows[m.id] = int(ctx)
            else:
                model_context_windows[m.id] = get_context_window(m.id)

        return {"models": model_names, "model_context_windows": model_context_windows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/providers/{provider_id}/discover-models")
async def discover_models_for_existing(provider_id: str, request: Request):
    """拉取已保存提供商的模型列表并更新缓存。

    重新拉取后，如果原来的 default_model 已不存在，自动置 None 并返回警告。
    """
    from openai import AsyncOpenAI
    from api.data.model_context_windows import get_context_window

    mgr = _get_manager(request)
    config = mgr.get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        models = await client.models.list()
        model_names = sorted(m.id for m in models.data)

        # 默认模型联动：检查 default_model 是否还在新列表中
        warning = None
        if config.default_model is not None and config.default_model not in model_names:
            warning = f"Default model '{config.default_model}' is no longer available and has been reset"
            config.default_model = None

        # 填充 model_context_windows
        model_context_windows: dict[str, int] = {}
        for m in models.data:
            ctx = getattr(m, "max_context_length", None) or getattr(m, "context_window", None)
            if ctx:
                model_context_windows[m.id] = int(ctx)
            else:
                model_context_windows[m.id] = get_context_window(m.id)
        config.model_context_windows = model_context_windows

        config.models = model_names
        mgr.save_config(config)

        result: dict = {"models": model_names}
        if warning:
            result["default_model_warning"] = warning
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 能力检测 ─────────────────────────────────────────────


@router.post("/providers/{provider_id}/test-capability")
async def test_single_capability(provider_id: str, body: TestCapabilityBody, request: Request):
    """测试指定模型的单个或所有能力，并保存结果。"""
    mgr = _get_manager(request)
    config = mgr.get_config(provider_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.model_name not in config.models:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{body.model_name}' is not in provider's model list",
        )

    testers = _get_testers()
    if body.capability:
        testers = [t for t in testers if t.capability_name == body.capability]
        if not testers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown capability '{body.capability}'",
            )

    results = await test_model_capabilities(config, body.model_name, testers)

    # 保存到 model_capabilities
    if body.capability:
        # 单项测试：只更新一个能力
        model_caps = config.model_capabilities.get(body.model_name, {})
        model_caps[body.capability] = results[body.capability]
        if body.model_name not in config.model_capabilities:
            config.model_capabilities[body.model_name] = {}
        config.model_capabilities[body.model_name].update(model_caps)
    else:
        # 全量测试：替换整个模型的记录
        config.model_capabilities[body.model_name] = results

    mgr.save_config(config)
    return {"capabilities": results}


@router.post("/providers/{provider_id}/test-all-capabilities")
async def test_all_capabilities(provider_id: str, body: TestCapabilityBody, request: Request):
    """测试指定模型的所有能力。兼容旧端点路径。"""
    return await test_single_capability(provider_id, body, request)


# ── 上下文窗口 ─────────────────────────────────────────────


class RefreshContextWindowsBody(BaseModel):
    url: str = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"


@router.post("/providers/refresh-context-windows")
async def refresh_context_windows(body: RefreshContextWindowsBody, request: Request):
    """从 LiteLLM 公开数据源拉取最新模型上下文窗口，更新配置文件。"""
    import httpx
    import yaml
    from pathlib import Path

    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "model_context_windows.yaml"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(body.url)
            resp.raise_for_status()
            litellm_data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch: {exc}")

    fetched: dict[str, int] = {}
    for model_id, model_info in litellm_data.items():
        if isinstance(model_info, dict) and model_info.get("max_input_tokens"):
            fetched[model_id] = int(model_info["max_input_tokens"])

    if not fetched:
        raise HTTPException(status_code=502, detail="No valid context window data found")

    # 写入 YAML 配置文件
    overrides = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
                overrides = existing.get("overrides", {})
        except Exception:
            pass

    merged = {**overrides}
    for model_id, ctx in fetched.items():
        if model_id not in merged:
            merged[model_id] = ctx

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump({"overrides": merged}, f, default_flow_style=False, allow_unicode=True)

    # 更新已配置 provider 的 model_context_windows
    mgr = _get_manager(request)
    updated = 0
    for config in mgr.list_configs():
        if not config.models:
            continue
        for mn in config.models:
            if mn not in config.model_context_windows:
                config.model_context_windows[mn] = fetched.get(mn, 128_000)
        mgr.save_config(config)
        updated += 1

    return {"status": "ok", "fetched_models": len(fetched), "updated_providers": updated}

