"""模型视觉能力检测 — 兼容层，委托到 capabilities 包。"""

from pathlib import Path

from api.providers import ProviderConfig
from api.providers.capabilities.vision import VisionTester
from api.providers.openai_provider import OpenAIProvider


async def test_model_vision(
    provider: "api.providers.Provider", model_name: str, image_path: Path
) -> bool:
    """检测单个模型是否具备视觉能力（兼容旧接口）。"""
    tester = VisionTester(image_path)
    result = await tester.test(provider, model_name)
    return result.supported


async def detect_vision_capabilities(
    config: ProviderConfig, image_path: Path
) -> dict[str, bool]:
    """批量检测提供商下所有模型的视觉能力（兼容旧接口）。"""
    import asyncio

    if not config.models:
        return {}

    provider = OpenAIProvider(config)
    tester = VisionTester(image_path)

    tasks = [tester.test(provider, model) for model in config.models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    vision: dict[str, bool] = {}
    for model, result in zip(config.models, results):
        if isinstance(result, bool):
            vision[model] = bool(result)
        elif hasattr(result, "supported"):
            vision[model] = result.supported
        else:
            vision[model] = False

    return vision
