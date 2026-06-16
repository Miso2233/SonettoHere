"""Tool: call_sub_agent — 创建子 Agent 会话执行单轮任务并返回结果。"""

import asyncio
import contextvars
import json
import sys
import traceback

from pydantic import BaseModel, Field

from api import interaction
from tools.base import ToolBase, format_success, format_error


class CallSubAgentInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    task: str = Field(default="", description="需要子 Agent 处理的任务描述（完整用户提示词）")
    name: str = Field(default="", description="可选，子会话的显示名称（用于侧边栏标识）")

# 深度追踪 — 使用 ContextVar 实现每个 asyncio Task 独立的计数。
# 并发调用（同一层级的多个子 Agent）互不干扰；
# 链式递归（子 Agent 再调子 Agent）才会递增深度。
_sub_call_depth: contextvars.ContextVar[int] = contextvars.ContextVar("_sub_call_depth", default=0)
_MAX_SUB_CALL_DEPTH = 2


class CallSubAgentTool(ToolBase):
    name: str = "call_sub_agent"
    description: str = (
        "创建一个子 Agent 会话执行单轮任务并将结果返回。"
        "用于需要独立的推理和工具调用的子任务，例如分析代码文件、执行多步骤搜索等。"
        "子 Agent 拥有独立的上下文窗口，不会污染主对话。"
        "[调用积极性: 可自由看情况调用] [get_doc: 使用前必须 get_doc]"
    )
    args_schema: type[BaseModel] = CallSubAgentInput

    def _run(self, get_doc: bool = False, task: str = "", name: str = "") -> str:
        raise NotImplementedError("call_sub_agent 仅支持异步模式")

    async def _arun(self, get_doc: bool = False, task: str = "", name: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not task.strip():
            return format_error("task 不能为空")

        # ── 深度限制（ContextVar，每个 asyncio Task 独立计数）─
        depth = _sub_call_depth.get()
        if depth >= _MAX_SUB_CALL_DEPTH:
            return format_error(f"子 Agent 嵌套深度已达上限 ({_MAX_SUB_CALL_DEPTH} 层)，拒绝递归调用")
        _sub_call_depth.set(depth + 1)
        try:
            return await self._do_run(task, name)
        finally:
            _sub_call_depth.set(depth)  # 恢复而非递减，避免异常场景下计数错乱

    async def _do_run(self, task: str, name: str = "") -> str:
        print("[call_sub_agent] _do_run entered", file=sys.stderr)
        try:
            ws = interaction.current_ws.get()
            print(f"[call_sub_agent] current_ws OK: {type(ws).__name__}", file=sys.stderr)
        except LookupError:
            print("[call_sub_agent] FATAL: current_ws not set in this context!", file=sys.stderr)
            traceback.print_stack(file=sys.stderr)
            return format_error("内部错误: WebSocket 上下文丢失，无法创建子会话")
        except Exception as e:
            print(f"[call_sub_agent] FATAL: current_ws.get() failed: {e}", file=sys.stderr)
            return format_error(f"内部错误: current_ws 异常: {e}")

        app_state = ws.app.state
        sm = app_state.session_manager
        print("[call_sub_agent] app_state / session_manager OK", file=sys.stderr)

        # 确定 parent_session_id
        # 从 WebSocket 路径推断：ws/chat/{session_id}
        parent_session_id = None
        try:
            path = str(getattr(ws, "url", getattr(ws, "path", "")))
            if "/ws/chat/" in path:
                parent_session_id = path.rsplit("/ws/chat/", 1)[-1]
        except Exception:
            pass

        # 1. 创建 sub-session
        sub = sm.create_sub_session(
            task=task,
            parent_session_id=parent_session_id,
        )
        print(f"[call_sub_agent] sub-session created: {sub.session_id}", file=sys.stderr)

        # 2. 通知前端（通过主 WS）
        print(f"[call_sub_agent] sending sub_session_created via WS", file=sys.stderr)
        await ws.send_json({
            "type": "sub_session_created",
            "payload": {
                "sub_session_id": sub.session_id,
                "parent_session_id": parent_session_id,
                "task": task[:200],
                "name": name[:100] if name else "",
            },
        })
        print(f"[call_sub_agent] sub_session_created sent, awaiting pending_result...", file=sys.stderr)

        # 3. 等待 sub-agent 执行完成
        #    sub-agent 由前端连接 sub-session WS 后自动启动
        #    或在前端未连接时由超时触发后台执行
        try:
            # 等待前端连接并触发 auto-start（最多等 10 秒）
            try:
                final_answer = await asyncio.wait_for(
                    sub._pending_result, timeout=120
                )
                print(f"[call_sub_agent] pending_result resolved, answer len={len(final_answer)}", file=sys.stderr)
            except asyncio.TimeoutError:
                print(f"[call_sub_agent] timeout waiting for pending_result (120s), trying background...", file=sys.stderr)
                # 如果前端一直未连接，后端直接执行（无 WS streaming）
                if not sub._pending_result.done():
                    # 尝试后台执行
                    final_answer = await self._run_background(sub, task, app_state)
                    print(f"[call_sub_agent] background done, answer len={len(final_answer)}", file=sys.stderr)
                else:
                    print(f"[call_sub_agent] pending_result done during timeout, re-raising", file=sys.stderr)
                    raise

            print(f"[call_sub_agent] returning success", file=sys.stderr)
            return format_success({
                "sub_session_id": sub.session_id,
                "answer": final_answer,
            })
        except asyncio.CancelledError:
            print(f"[call_sub_agent] cancelled", file=sys.stderr)
            # 主 Agent 被取消 → 取消 sub-agent
            if sub._active_task and not sub._active_task.done():
                sub._active_task.cancel()
            if sub._pending_result and not sub._pending_result.done():
                sub._pending_result.cancel()
            return format_error("主任务被取消，子 Agent 已终止")
        except Exception as e:
            print(f"[call_sub_agent] error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return format_error(f"子 Agent 执行失败: {str(e)}")

    async def _run_background(self, sub, task: str, app_state) -> str:
        """后端直接执行（无前端连接时的回退路径）。"""
        print(f"[call_sub_agent] _run_background starting for {sub.session_id}", file=sys.stderr)
        from agent.graph import build_agent
        from agent.prompts import build_system_prompt
        from langchain_core.messages import HumanMessage

        system_prompt = build_system_prompt()
        agent = build_agent(
            model=app_state.llm,
            tools=app_state.tools,
            system_prompt=system_prompt,
            checkpointer=sub.checkpointer,
        )
        inputs = {"messages": [HumanMessage(content=task)]}
        config = {"configurable": {"thread_id": sub.session_id}, "recursion_limit": 72}

        final_answer = ""
        try:
            async for event in agent.astream_events(inputs, config=config, version="v2"):
                if event.get("event") == "on_chain_end" and event.get("name") == "agent":
                    output = event["data"].get("output", {})
                    messages = output.get("messages", [])
                    if messages:
                        last = messages[-1]
                        final_answer = last.content if hasattr(last, "content") else str(last)

            # 事件未捕获到 final_answer 时，从 checkpoint 兜底提取
            if not final_answer:
                try:
                    cpt = await sub.checkpointer.aget_tuple(config)
                    if cpt is not None:
                        messages = cpt.checkpoint.get("channel_values", {}).get("messages", [])
                        if messages:
                            last = messages[-1]
                            candidate = last.content if hasattr(last, "content") else str(last)
                            if candidate:
                                final_answer = candidate
                except Exception:
                    pass
        except Exception as e:
            print(f"[call_sub_agent] _run_background agent failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            raise

        print(f"[call_sub_agent] _run_background got answer: {final_answer[:100] if final_answer else '(empty)'}", file=sys.stderr)

        if final_answer:
            sub.message_count += 2
            sub._pending_result.set_result(final_answer)
        else:
            sub._pending_result.set_exception(
                RuntimeError("子 Agent 未能产生有效回答")
            )

        return final_answer
