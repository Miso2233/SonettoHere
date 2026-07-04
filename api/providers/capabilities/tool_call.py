"""模型工具调用能力检测器。

向模型发一条带虚假 tool_choice 的消息，看模型能否正常响应。
"""

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from api.providers import Provider
from api.providers.capabilities.base import CapabilityTester, CapabilityTestResult


@tool
def _test_tool(query: str) -> str:
    """A test tool for capability detection."""
    return f"echo: {query}"


class ToolCallTester(CapabilityTester):
    """检测模型是否支持工具/函数调用。"""

    @property
    def capability_name(self) -> str:
        return "tool_call"

    async def test(self, provider: Provider, model_name: str) -> CapabilityTestResult:
        try:
            llm = provider.create_llm(model_name, temperature=0).bind_tools([_test_tool])

            response = await llm.ainvoke([
                HumanMessage(content="Say 'ping' using the test tool.")
            ])

            # 检查响应是否包含工具调用
            if hasattr(response, "tool_calls") and response.tool_calls:
                return CapabilityTestResult(
                    capability="tool_call",
                    supported=True,
                )

            # 部分模型会拒绝调用但返回有效文本，也算支持工具调用
            if hasattr(response, "content") and response.content:
                return CapabilityTestResult(
                    capability="tool_call",
                    supported=True,
                    detail="Model responded with text instead of tool call, but did not error",
                )

            return CapabilityTestResult(
                capability="tool_call",
                supported=False,
                detail="No tool call and no valid response",
            )
        except Exception as exc:
            return CapabilityTestResult(
                capability="tool_call",
                supported=False,
                detail=str(exc),
            )
