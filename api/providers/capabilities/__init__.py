"""通用能力检测框架 — 注册检测器与辅助函数。"""

from pathlib import Path

from api.providers import ProviderConfig
from api.providers.capabilities.base import CapabilityTester  # noqa: F401
from api.providers.capabilities.base import CapabilityTestResult  # noqa: F401
from api.providers.capabilities.vision import VisionTester
from api.providers.capabilities.tool_call import ToolCallTester
from api.providers.capabilities.structured_output import StructuredOutputTester
from api.providers.openai_provider import OpenAIProvider


def get_all_testers(image_path: Path | None = None) -> list[CapabilityTester]:
    """返回所有可用的能力检测器。"""
    testers: list[CapabilityTester] = [
        ToolCallTester(),
        StructuredOutputTester(),
    ]
    if image_path and image_path.exists():
        testers.append(VisionTester(image_path))
    return testers


async def test_model_capabilities(
    config: ProviderConfig,
    model_name: str,
    testers: list[CapabilityTester],
) -> dict[str, bool]:
    """对单个模型运行所有检测器，返回能力名 → 是否支持的映射。"""
    provider = OpenAIProvider(config)
    results: dict[str, bool] = {}
    for tester in testers:
        result = await tester.test(provider, model_name)
        results[result.capability] = result.supported
    return results
