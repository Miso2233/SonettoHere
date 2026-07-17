"""向会话 Checkpointer 追加 HumanMessage 的工具函数。

通过 graph.aupdate_state() 将 HumanMessage 追加到消息列表末尾，
避免直接操作 MemorySaver 的低级 checkpoint 结构。

注意：该函数**不会**触发完整的前端事件流（token、thinking 等），
仅修改 checkpoint 状态，供下一轮 Agent 执行时读取。
"""

from langchain_core.messages import HumanMessage

from api.session.manager import SessionState


async def add_human_message(
    session: SessionState,
    message: HumanMessage | str,
) -> None:
    """向会话的 checkpoint 追加一条 HumanMessage。

    SessionState 同时持有 CompiledStateGraph 和 session_id，
    函数内部提取两者，通过 graph.aupdate_state() 经 add_messages reducer 追加，
    自动处理 checkpoint_id、channel_versions、versions_seen 等内部结构。

    注意：graph 内部持有的 checkpointer 与 session.checkpointer 是同一个
    MemorySaver 引用（在 _build_turn_context 中通过 build_agent(checkpointer=session.checkpointer) 传入）。
    因此 graph.aupdate_state() 写入的就是 session.checkpointer，无需额外同步。

    Args:
        session: 会话状态对象，同时持有 graph（执行图）和 session_id。
        message: 要追加的 HumanMessage 实例，或文本内容（自动封装为 HumanMessage）。

    Returns:
        None。成功即 checkpoint 已包含该消息；失败则抛出异常。

    Raises:
        ValueError: graph 为 None 时抛出。
    """
    graph = session.get_graph()
    if graph is None:
        raise ValueError("graph is None，无法追加 HumanMessage")

    if isinstance(message, str):
        message = HumanMessage(content=message)

    config = {"configurable": {"thread_id": session.session_id}}
    await graph.aupdate_state(config, {"messages": [message]})
