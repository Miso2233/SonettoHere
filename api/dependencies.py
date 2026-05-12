"""Web API 共享资源 — LLM、系统提示词、工具集的惰性单例。"""

from langchain_openai import ChatOpenAI

from agent.prompts import build_system_prompt
from config.settings import get_settings
from skills import get_all_skills

_llm: ChatOpenAI | None = None
_system_prompt: str | None = None
_tools: list | None = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatOpenAI(
            model="deepseek-v4-flash",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.7,
            streaming=True,
            extra_body={"thinking": {"type": "disabled"}},
        )
    return _llm


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()
    return _system_prompt


def get_tools() -> list:
    global _tools
    if _tools is None:
        _tools = get_all_skills()
    return _tools
