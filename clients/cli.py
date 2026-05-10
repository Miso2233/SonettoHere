"""CLI 入口 — 异步命令行对话界面。"""

import asyncio
import uuid
from datetime import datetime

from langchain_openai import ChatOpenAI

from agent.graph import build_agent
from agent.prompts import build_system_prompt
from callbacks.printer import PrinterCallback
from config.settings import get_settings
from memory.extractor import extract_from_messages, save_extracted
from memory.long_term import retrieve_long_term_context
from memory.preference import get_stable_preferences
from memory.short_term import ShortTermMemory
from skills import get_all_skills


class SonettoCLI:
    """异步命令行对话界面，基于 LangGraph ReAct Agent。"""

    def __init__(self):
        """初始化会话 ID、LLM 客户端、系统提示词、工具集、Agent 图和短期记忆。"""
        settings = get_settings()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        self.llm = ChatOpenAI(
            model="deepseek-v4-flash",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.7,
            streaming=True,
        )
        self.system_prompt = build_system_prompt()
        self.tools = get_all_skills()
        self.graph = build_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.system_prompt,
        )
        self.memory = ShortTermMemory()
        self._turn_messages: list[dict] = []

    async def run(self) -> None:
        """启动 REPL 主循环：读取用户输入 → 注入长期记忆 → 流式输出 → 保存本轮对话。"""
        print("SonettoHere v2.0.0 — LangGraph ReAct Agent")
        print("输入 /exit 退出，/clear 清空对话\n")

        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue
            if user_input == "/exit":
                print("再见！")
                break
            if user_input == "/clear":
                self.memory.clear()
                self._turn_messages.clear()
                print("对话已清空。")
                continue

            # 注入长期记忆
            enhanced_prompt = self._build_enhanced_prompt(user_input)

            self.graph = build_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=enhanced_prompt,
            )

            config = {
                "configurable": {"thread_id": self.session_id},
                "callbacks": [PrinterCallback()],
            }
            self._turn_messages = [{"role": "user", "content": user_input}]

            print()
            await self._stream_events(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
            )
            print()

            self._save_turn()

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

    async def _stream_events(self, inputs: dict, config: dict) -> None:
        """流式消费 Agent 图事件，收集工具输出和最终回复到 _turn_messages。"""

        async for event in self.graph.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_tool_end":
                output = event["data"].get("output", "")
                out_str = str(output) if not isinstance(output, str) else output
                if len(out_str) > 300:
                    out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"
                self._turn_messages.append({"role": "tool", "content": out_str})

            elif kind == "on_chain_end" and name == "agent":
                output = event["data"].get("output", {})
                messages = output.get("messages", [])
                if messages:
                    last = messages[-1]
                    if hasattr(last, "content"):
                        final_output = last.content

        if final_output:
            self._turn_messages.append({"role": "assistant", "content": final_output})

    def _save_turn(self) -> None:
        """将本轮消息交给记忆提取器，持久化错误规则和偏好。"""
        if not self._turn_messages:
            return
        try:
            extracted = extract_from_messages(self._turn_messages, self.llm)
            save_extracted(extracted, session_id=self.session_id)
        except Exception:
            pass


def main():
    """CLI 入口函数，以 asyncio 启动 SonettoCLI。"""
    asyncio.run(SonettoCLI().run())


if __name__ == "__main__":
    main()
