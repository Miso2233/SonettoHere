"""记忆工具模块。

可通过 inject_memory_manager() 从外部注入当前 MemoryManager 实例，
避免每个工具每次调用时都重新创建 YamlMemoryManager。
"""

from pathlib import Path

from api.memory.manager import BaseMemoryManager

_injected_mm: BaseMemoryManager | None = None

# 回退路径：当未注入时自建 YamlMemoryManager 用
_FALLBACK_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"
)


def inject_memory_manager(mm: BaseMemoryManager | None) -> None:
    """注入记忆管理器实例，供本模块所有工具共享。

    由 LongTermMemory.inject_tools() 在应用启动时调用。
    传入 None 可清除注入（用于测试或关闭时清理）。
    """
    global _injected_mm
    _injected_mm = mm


def get_memory_manager() -> BaseMemoryManager:
    """获取当前记忆管理器。优先返回注入的实例，否则自建。"""
    if _injected_mm is not None:
        return _injected_mm
    # 降级：尚未注入时自建
    from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager

    return (
        MemoryManagerBuilder()
        .with_backend(YamlMemoryManager).with_args(yaml_file=str(_FALLBACK_PATH))
        .build()
    )
