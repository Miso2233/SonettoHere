"""CLI 入口 — 异步命令行对话界面。"""

import asyncio
import uuid
from datetime import datetime

from langchain_openai import ChatOpenAI

from agent.graph import build_agent
from agent.prompts import build_enhanced_prompt, build_system_prompt
from callbacks.printer import PrinterCallback
from config.settings import get_settings
from memory.short_term import ShortTermMemory
from memory.narrative import LongTermMemoryInterface, MEMORY_PATH
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
            extra_body={"thinking": {"type": "disabled"}},
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
        self.ltm = LongTermMemoryInterface(MEMORY_PATH)

    async def run(self) -> None:
        """启动 REPL 主循环：读取用户输入 → 注入长期记忆 → 流式输出 → 保存本轮对话。"""
        print("SonettoHere v2.0.0 — LangGraph ReAct Agent")
        print("输入 /help 或 / 查看可用命令\n")

        self.ltm.start_listening(self.llm)
        try:
            await self._repl()
        finally:
            await self.ltm.stop_listening()

    async def _repl(self) -> None:
        """REPL 主循环体。"""
        loop = asyncio.get_running_loop()
        while True:
            try:
                prompt = ">>> "
                user_input = (await loop.run_in_executor(None, input, prompt)).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break
            except asyncio.CancelledError:
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
            if user_input in ("/", "/help"):
                print("""
可用命令:
  /exit       退出程序
  /clear      清空当前对话
  /narrative  查看当前记忆叙事
  /help       显示此帮助信息
""")
                continue
            if user_input == "/narrative":
                from memory.narrative import get_narrative
                narrative = get_narrative()
                if narrative:
                    print(f"\n{narrative}\n")
                else:
                    print("\n暂无记忆叙事。\n")
                continue

            # 生成提示词
            enhanced_prompt = build_enhanced_prompt(self.system_prompt, user_input)

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
            await self._run_stream_events(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
            )
            print()

            await self.ltm.send_history(self._turn_messages)
            self._turn_messages.clear()

    async def _run_stream_events(self, inputs: dict, config: dict) -> None:
        """流式消费 Agent 图事件，收集工具输出和最终回复到 _turn_messages。"""

        final_output = None

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


def main():
    """CLI 入口函数，以 asyncio 启动 SonettoCLI。"""
    asyncio.run(SonettoCLI().run())


if __name__ == "__main__":
    main()