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
from memory.extractor import extract_from_messages, save_extracted
from memory.long_term import retrieve_long_term_context
from memory.preference import get_stable_preferences
from memory.short_term import ShortTermMemory
from skills import get_all_skills


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

    def _get_session(self, user_id: str) -> dict:
        """获取或创建用户会话（thread_id + 短期记忆）。"""
        if user_id not in self._sessions:
            self._sessions[user_id] = {
                "thread_id": uuid.uuid4().hex,
                "memory": ShortTermMemory(),
            }
        return self._sessions[user_id]

    async def on_c2c_message_create(self, message: Message):
        """处理 C2C 私聊消息，使用 Agent 生成回复。"""
        user_input = message.content
        user_id = message.author.user_openid
        session = self._get_session(user_id)

        # 注入长期记忆构建增强提示词
        enhanced_prompt = self._build_enhanced_prompt(user_input)

        # 每条消息使用独立的 graph，共享 thread_id 以维持对话上下文
        graph = build_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=enhanced_prompt,
        )
        config = {"configurable": {"thread_id": session["thread_id"]}}

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

        # 保存本轮对话到记忆
        turn_messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": final_answer},
        ]
        try:
            extracted = extract_from_messages(turn_messages, self.llm)
            save_extracted(extracted, source="qqbot", session_id=session["thread_id"])
        except Exception:
            pass

    def _build_enhanced_prompt(self, user_input: str) -> str:
        """检索长期记忆和用户偏好，拼接增强后的系统提示词。"""
        prompt = self.system_prompt
        try:
            retrieved = retrieve_long_term_context(user_input, top_k=10)
            stable = get_stable_preferences()

            if retrieved.get("error_rules"):
                rules = "\n".join(
                    f"- {r.get('correction', r.get('mistake', str(r)))}"
                    for r in retrieved["error_rules"][:5]
                )
                prompt += f"\n\n## 错误规避规则\n{rules}"
            if retrieved.get("preference_rules"):
                prefs = "\n".join(
                    f"- {p.get('habit', str(p))}"
                    for p in retrieved["preference_rules"][:5]
                )
                prompt += f"\n\n## 用户偏好\n{prefs}"
            if stable:
                lines = [f"- {k} = {v.get('value', '')}" for k, v in stable.items()]
                prompt += f"\n\n## 稳定偏好\n" + "\n".join(lines[:5])
        except Exception:
            pass
        return prompt


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
