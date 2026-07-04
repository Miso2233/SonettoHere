"""模型视觉能力检测器。

向模型发送一张包含文字 "Sonetto" 的测试图片，
要求模型读出图片中的文字，若响应包含 "Sonetto" 则视为有视觉能力。
"""

import base64
from pathlib import Path

from langchain_core.messages import HumanMessage

from api.providers import Provider
from api.providers.capabilities import CapabilityTester, CapabilityTestResult

_PROMPT = "What text is shown in this image? Reply with only the text."


class VisionTester(CapabilityTester):
    """检测模型是否支持多模态视觉输入。"""

    def __init__(self, image_path: Path):
        self.image_path = image_path

    @property
    def capability_name(self) -> str:
        return "vision"

    async def test(self, provider: Provider, model_name: str) -> CapabilityTestResult:
        try:
            llm = provider.create_llm(model_name, temperature=0)

            with open(self.image_path, "rb") as f:
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
            supported = "Sonetto".lower() in text.lower()
            return CapabilityTestResult(
                capability="vision",
                supported=supported,
                detail=None if supported else "Response did not contain expected text 'Sonetto'",
            )
        except Exception as exc:
            return CapabilityTestResult(
                capability="vision",
                supported=False,
                detail=str(exc),
            )
