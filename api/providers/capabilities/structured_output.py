"""模型结构化输出能力检测器。

请求 response_format: {type: "json_object"} 看模型能否返回合法 JSON。
"""

from langchain_core.messages import HumanMessage

from api.providers import Provider
from api.providers.capabilities.base import CapabilityTester, CapabilityTestResult

_PROMPT = 'Output a JSON object with one key "name" set to "test". Reply with ONLY valid JSON.'


class StructuredOutputTester(CapabilityTester):
    """检测模型是否支持 JSON 结构化输出。"""

    @property
    def capability_name(self) -> str:
        return "structured_output"

    async def test(self, provider: Provider, model_name: str) -> CapabilityTestResult:
        try:
            llm = provider.create_llm(
                model_name,
                temperature=0,
                model_kwargs={"response_format": {"type": "json_object"}},
            )

            response = await llm.ainvoke([HumanMessage(content=_PROMPT)])
            raw = response.content if hasattr(response, "content") else str(response)
            text = raw if isinstance(raw, str) else str(raw)

            import json
            data = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
            if isinstance(data, dict) and "name" in data:
                return CapabilityTestResult(
                    capability="structured_output",
                    supported=True,
                )
            return CapabilityTestResult(
                capability="structured_output",
                supported=False,
                detail=f"Response did not contain expected key: {text[:200]}",
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return CapabilityTestResult(
                capability="structured_output",
                supported=False,
                detail=str(exc)[:200],
            )
        except Exception as exc:
            return CapabilityTestResult(
                capability="structured_output",
                supported=False,
                detail=str(exc)[:200],
            )
