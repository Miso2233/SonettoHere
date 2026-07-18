"""短期记忆管理 — 全局 MemorySaver 单例。

所有会话的 LangGraph 检查点（对话上下文）共享同一个 MemorySaver，
通过 thread_id = session.session_id 区分隔离。
"""

from langgraph.checkpoint.memory import MemorySaver

_global_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver:
    """返回全局单例 checkpointer。"""
    return _global_checkpointer


def delete_thread(thread_id: str) -> None:
    """删除指定 thread_id 的全部检查点，释放内存。"""
    _global_checkpointer.delete_thread(thread_id)
