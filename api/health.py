"""后端四部件健康自检 — LLM / 记忆 / 原生工具集 / MCP 工具集。"""

import asyncio
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from memory.memory_manager import MemoryManager
from memory.narrative import MEMORY_PATH

ANTHROPIC_SKILLS_DIR = Path(__file__).resolve().parent.parent / "anthropic_skills"


class ComponentHealth(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    llm: ComponentHealth
    memory: ComponentHealth
    native_tools: ComponentHealth
    mcp_tools: ComponentHealth
    anthropic_skills_count: int = 0
    providers: dict[str, ComponentHealth] = {}
    timestamp: float


# ── LLM 健康检查（通过 ProviderManager）──────────────


async def check_llm(app: FastAPI) -> ComponentHealth:
    """使用 ProviderManager 中第一个 enabled provider 检查 LLM 连通性。"""
    mgr = getattr(app.state, "provider_manager", None)
    if mgr is None or mgr.count == 0:
        return ComponentHealth(
            status="error",
            detail="No LLM providers configured. Add one via the providers panel.",
        )

    start = time.monotonic()
    for provider in mgr.iter_enabled():
        result = await provider.check_health()
        if result.status == "ok":
            elapsed = (time.monotonic() - start) * 1000
            return ComponentHealth(
                status="ok",
                latency_ms=round(elapsed, 1),
                detail=f"Provider: {provider.provider_name}",
            )

    elapsed = (time.monotonic() - start) * 1000
    return ComponentHealth(
        status="error",
        latency_ms=round(elapsed, 1),
        detail="All providers unreachable",
    )


async def check_memory(app: FastAPI) -> ComponentHealth:
    start = time.monotonic()
    try:
        memory_path = MEMORY_PATH
        if not memory_path.exists():
            elapsed = (time.monotonic() - start) * 1000
            return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail="记忆文件不存在")

        mm = MemoryManager(yaml_file=str(memory_path))
        items = mm.show()

        ltm = app.state.ltm
        consumer_running = ltm.is_listening if hasattr(ltm, "is_listening") else False

        parts = [f"{len(items)} 条记忆"]
        if not consumer_running:
            parts.append("后台消费者异常")
        status: Literal["ok", "error"] = "ok" if consumer_running else "error"

        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(status=status, latency_ms=round(elapsed, 1), detail="，".join(parts))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=str(e))


async def check_native_tools(app: FastAPI) -> ComponentHealth:
    start = time.monotonic()
    try:
        tools = app.state.native_tools
        names = sorted(t.name for t in tools)
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(
            status="ok",
            latency_ms=round(elapsed, 1),
            detail=f"{len(tools)} 个工具",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=str(e))


async def check_mcp_tools(app: FastAPI) -> ComponentHealth:
    start = time.monotonic()
    try:
        tools = app.state.mcp_tools
        if not tools:
            elapsed = (time.monotonic() - start) * 1000
            return ComponentHealth(status="ok", latency_ms=round(elapsed, 1), detail="0 个工具（未配置 MCP 服务器）")
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(
            status="ok",
            latency_ms=round(elapsed, 1),
            detail=f"{len(tools)} 个工具",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=str(e))


async def check_health_providers(app: FastAPI) -> dict[str, ComponentHealth]:
    """遍历 ProviderManager 中所有 enabled provider 并行健康检查。"""
    mgr = getattr(app.state, "provider_manager", None)
    if mgr is None or mgr.count == 0:
        return {}

    async def _check_one(provider) -> tuple[str, ComponentHealth]:
        result = await provider.check_health()
        return (provider.provider_name, ComponentHealth(
            status=result.status,
            latency_ms=result.latency_ms,
            detail=result.detail,
        ))

    tasks = [_check_one(p) for p in mgr.iter_enabled()]
    results = await asyncio.gather(*tasks)
    return dict(results)


async def get_health_report(app: FastAPI) -> HealthResponse:
    from version import __version__

    llm = await check_llm(app)
    memory = await check_memory(app)
    native_tools = await check_native_tools(app)
    mcp_tools = await check_mcp_tools(app)
    providers = await check_health_providers(app)

    # 统计 anthropic_skills 下的 skill 数量
    skills_count = 0
    if ANTHROPIC_SKILLS_DIR.is_dir():
        skills_count = len([p for p in ANTHROPIC_SKILLS_DIR.iterdir() if p.is_dir()])

    all_checks = [llm, memory, native_tools, mcp_tools] + list(providers.values())
    overall: Literal["ok", "degraded"] = (
        "ok" if all(c.status == "ok" for c in all_checks) else "degraded"
    )

    return HealthResponse(
        status=overall,
        version=__version__,
        llm=llm,
        memory=memory,
        native_tools=native_tools,
        mcp_tools=mcp_tools,
        anthropic_skills_count=skills_count,
        providers=providers,
        timestamp=time.time(),
    )
