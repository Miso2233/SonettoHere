"""Tool: call_sub_agent — 创建子 Agent 会话执行单轮任务并返回结果。"""

import asyncio
import contextvars

from pydantic import BaseModel, Field

from api.agent import interaction
from api.events import ToolSender
from tools.base import ToolBase, format_success, format_error
from api.utils.logger import get_logger

_log = get_logger("call_sub_agent")


class CallSubAgentInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    task: str = Field(
        default="", description="需要子 Agent 处理的任务描述（完整用户提示词）"
    )
    name: str = Field(
        default="", description="可选，子会话的显示名称（用于侧边栏标识）"
    )


# 深度追踪 — 使用 ContextVar 实现每个 asyncio Task 独立的计数。
# 并发调用（同一层级的多个子 Agent）互不干扰；
# 链式递归（子 Agent 再调子 Agent）才会递增深度。
_sub_call_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_sub_call_depth", default=0
)
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
            return format_error(
                f"子 Agent 嵌套深度已达上限 ({_MAX_SUB_CALL_DEPTH} 层)，拒绝递归调用"
            )
        _sub_call_depth.set(depth + 1)
        try:
            return await self._do_run(task, name)
        finally:
            _sub_call_depth.set(depth)  # 恢复而非递减，避免异常场景下计数错乱

    async def _do_run(self, task: str, name: str = "") -> str:
        _log.debug("_do_run entered")
        try:
            ws = interaction.current_ws.get()
            _log.debug("current_ws OK: %s", type(ws).__name__)
        except LookupError:
            _log.error("FATAL: current_ws not set in this context!")
            return format_error("内部错误: WebSocket 上下文丢失，无法创建子会话")
        except Exception as e:
            _log.error("FATAL: current_ws.get() failed: %s", e)
            return format_error(f"内部错误: current_ws 异常: {e}")

        from api.session.manager import session_manager as sm
        app_state = ws.app.state
        _log.debug("session_manager OK")

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
        sub = sm.create_sub_session(task=task)
        _log.info("sub-session created: %s", sub.session_id)

        # 2. 通知前端（通过主 WS）
        _log.debug("sending sub_session_created via WS")
        sender = ToolSender.from_context()
        if sender is not None:
            await sender.sub_session_created(
                sub_session_id=sub.session_id,
                parent_session_id=parent_session_id,
                task=task,
                name=name[:100] if name else "",
            )
        _log.debug("sub_session_created sent, awaiting pending_result...")

        # 3. 等待 sub-agent 执行完成
        #    sub-agent 由前端连接 sub-session WS 后自动启动并返回结果
        try:
            final_answer = await sub.pending_future
            _log.info("pending_result resolved, answer len=%d", len(final_answer))

            _log.debug("returning success")
            return format_success(
                {
                    "sub_session_id": sub.session_id,
                    "answer": final_answer,
                }
            )
        except asyncio.CancelledError:
            _log.info("cancelled")
            # 主 Agent 被取消 → 取消 sub-agent
            sub.cancel_active_task()
            sub.cancel_pending()
            return format_error("主任务被取消，子 Agent 已终止")
        except Exception as e:
            _log.error("error: %s", e, exc_info=True)
            return format_error(f"子 Agent 执行失败: {str(e)}")
