"""TimeTraveler — 对话轮次撤回工具。

基于 LangGraph 的 RemoveMessage 机制，通过 CompiledStateGraph.update_state
删除 MemorySaver 检查点中指定轮次的对话消息。
"""

from langchain_core.messages import RemoveMessage


async def undo_rounds(graph, config, n: int = 1) -> int:
    """撤回最近 n 轮对话，返回删除的消息条数。

    Args:
        graph: CompiledStateGraph 实例（需持有会话的 checkpointer）。
        config: LangGraph 配置，至少包含 {"configurable": {"thread_id": ...}}。
        n: 要撤回的轮次数，默认 1。

    Returns:
        实际删除的消息条数。
    """
    if n < 1:
        return 0

    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])

    if not messages:
        return 0

    # 找出所有 HumanMessage 的位置
    human_indices = [i for i, m in enumerate(messages) if m.type == "human"]

    if not human_indices:
        return 0

    if len(human_indices) < n:
        # 不够 n 轮就全部删除
        to_delete = messages
    else:
        # 倒数第 n 个 human 的位置就是切割点
        cutoff = human_indices[-n]
        to_delete = messages[cutoff:]

    # 提交删除指令 — RemoveMessage 会被 add_messages reducer 识别并删除对应 id 的消息
    await graph.aupdate_state(
        config, {"messages": [RemoveMessage(id=m.id) for m in to_delete]}
    )
    return len(to_delete)


async def undo_last_round(graph, config) -> int:
    """撤回最近一轮对话。"""
    return await undo_rounds(graph, config, n=1)


async def undo_all(graph, config) -> int:
    """撤回所有轮次，清空对话历史。"""
    return await undo_rounds(graph, config, n=10**9)
