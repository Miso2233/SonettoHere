"""QQ Bot 入口 — 异步 QQ Bot 适配，基于 LangGraph ReAct Agent。"""

import asyncio
import uuid
from datetime import datetime

import botpy
from botpy.types.message import Message
from langchain_openai import ChatOpenAI

from agent.graph import build_agent
from agent.prompts import build_system_prompt
from config.settings import get_settings
from memory.narrative import LongTermMemoryInterface, MEMORY_PATH
from skills import get_all_skills
from skills.mcp import init_mcp_tools, close_mcp


class SonettoQQBot(botpy.Client):
    """QQ 机器人客户端，继承 botpy.Client，基于 LangGraph ReAct Agent 回复 C2C 私聊消息。"""

    def __init__(self, appid: str, token: str):
        intents = botpy.Intents.all()
        super().__init__(intents=intents)
        self.appid = appid
        self.token = token

        settings = get_settings()
        self.llm = ChatOpenAI(
            model="deepseek-v4-flash",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.7,
            extra_body={"thinking": {"type": "disabled"}},
        )
        self.system_prompt = build_system_prompt()
        self.tools = get_all_skills()
        self._sessions: dict[str, dict] = {}
        self.ltm = LongTermMemoryInterface(MEMORY_PATH)

    def _get_session(self, user_id: str) -> dict:
        """获取或创建用户会话（thread_id + 短期记忆）。"""
        if user_id not in self._sessions:
            self._sessions[user_id] = {
                "thread_id": uuid.uuid4().hex,
            }
        return self._sessions[user_id]

    async def on_c2c_message_create(self, message: Message):
        """处理 C2C 私聊消息，使用 Agent 生成回复。"""
        user_input = message.content
        user_id = message.author.user_openid
        session = self._get_session(user_id)

        # 注入长期记忆构建增强提示词
        system_prompt = build_system_prompt()

        # 每条消息使用独立的 graph，共享 thread_id 以维持对话上下文
        graph = build_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        )
        config = {"configurable": {"thread_id": session["thread_id"]}, "recursion_limit": 120}

        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                final_answer = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            else:
                final_answer = "抱歉，我暂时无法回复这条消息。"
        except Exception as e:
            final_answer = f"处理消息时发生错误：{e}"

        # QQ 消息长度限制，超出则截断
        if len(final_answer) > 2000:
            final_answer = final_answer[:1980] + "\n\n...（回复过长已截断）"

        await message.reply(content=final_answer)

        turn_messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": final_answer},
        ]
        await self.ltm.send_history(turn_messages)

    async def run(self, *args, **kwargs):
        """启动 QQ Bot，接管 run 生命周期以管理 LongTermMemoryInterface 和 MCP 工具。"""
        self.ltm.start_listening(self.llm)
        try:
            mcp_tools = await init_mcp_tools()
            self.tools = self.tools + mcp_tools
            await super().run(*args, **kwargs)
        finally:
            await self.ltm.stop_listening()
            await close_mcp()


def create_client_from_config() -> SonettoQQBot:
    """从 Settings 读取 QQ Bot 配置并创建客户端实例。"""
    settings = get_settings()
    if not settings.qq_appid or not settings.qq_token:
        raise ValueError(
            "缺少 QQ Bot 配置，请在 .env 中设置 QQ_APPID 和 QQ_TOKEN"
        )
    return SonettoQQBot(appid=settings.qq_appid, token=settings.qq_token)


def main():
    """QQ Bot 入口函数：读取配置 → 创建客户端 → 启动 asyncio 事件循环。"""
    client = create_client_from_config()
    print(f"SonettoHere QQ Bot 正在启动... (appid: {client.appid})")
    asyncio.run(client.run(appid=client.appid, secret=client.token))


if __name__ == "__main__":
    main()
