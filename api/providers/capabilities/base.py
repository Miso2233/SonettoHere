"""能力检测基础类型 — CapabilityTester 接口与 CapabilityTestResult。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CapabilityTestResult:
    """单个模型的能力检测结果。"""

    capability: str          # "vision" | "tool_call" | "structured_output"
    supported: bool          # 是否支持该能力
    detail: str | None = None  # 失败原因/补充信息


class CapabilityTester(ABC):
    """所有能力检测器必须实现的接口。"""

    @property
    @abstractmethod
    def capability_name(self) -> str:
        """能力名称标识，例如 'vision'、'tool_call'、'structured_output'。"""
        ...

    @abstractmethod
    async def test(self, provider, model_name: str) -> CapabilityTestResult:
        """检测指定模型是否支持该能力。"""
        ...
