"""模型视觉能力检测。

保存提供商时自动检测每个模型是否具备视觉能力：
1. 向模型发送一张包含文字 "Sonetto" 的测试图片
2. 要求模型读出图片中的文字
3. 若响应中包含 "Sonetto" 则视为有视觉能力，否则无
"""

import asyncio
import base64
from pathlib import Path

from langchain_core.messages import HumanMessage

from api.providers import Provider, ProviderConfig

_PROMPT = "What text is shown in this image? Reply with only the text."


async def test_model_vision(
    provider: Provider, model_name: str, image_path: Path
) -> bool:
    """检测单个模型是否具备视觉能力。

    向模型发送一张包含 "Sonetto" 文字的测试图片，要求读出文字。
    若报错或响应不包含 "Sonetto" 则认为该模型无视觉能力。
    """
    try:
        llm = provider.create_llm(model_name, temperature=0)

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        message = HumanMessage(
            content=[
                {"type": "text", "text": _PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ]
        )

        response = await llm.ainvoke([message])
        raw = response.content if hasattr(response, "content") else str(response)
        text = raw if isinstance(raw, str) else str(raw)
        return "Sonetto".lower() in text.lower()
    except Exception:
        return False


async def detect_vision_capabilities(
    config: ProviderConfig, image_path: Path
) -> dict[str, bool]:
    """批量检测提供商下所有模型的视觉能力。

    并发测试 config.models 中的每个模型，返回 model_name → bool 的映射。
    测试失败的模型视为无视觉能力。
    """
    if not config.models:
        return {}

    from api.providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(config)

    tasks = [
        test_model_vision(provider, model, image_path) for model in config.models
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    vision: dict[str, bool] = {}
    for model, result in zip(config.models, results):
        if isinstance(result, bool):
            vision[model] = result
        else:
            vision[model] = False

    return vision
