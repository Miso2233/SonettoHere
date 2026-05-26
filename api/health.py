"""后端四部件健康自检 — LLM / 记忆 / 原生工具集 / MCP 工具集。"""

import asyncio
import time
from typing import Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from config.settings import get_settings
from memory.memory_manager import MemoryManager
from memory.narrative import MEMORY_PATH


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
    timestamp: float


# ── LLM 健康缓存（30 秒 TTL，避免高频 API 调用）──────────────

_llm_health_cache: tuple[float, ComponentHealth] | None = None
_LLM_CACHE_TTL = 30.0


_httpx_client: httpx.AsyncClient | None = None


def _get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(timeout=5.0)
    return _httpx_client


async def check_llm(app: FastAPI) -> ComponentHealth:
    global _llm_health_cache

    now = time.monotonic()
    if _llm_health_cache is not None and now - _llm_health_cache[0] < _LLM_CACHE_TTL:
        return _llm_health_cache[1]

    start = now
    try:
        settings = get_settings()
        client = _get_httpx_client()
        resp = await client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": "ok"}],
                "max_tokens": 1,
            },
        )
        elapsed = (time.monotonic() - start) * 1000

        if resp.is_success:
            result = ComponentHealth(status="ok", latency_ms=round(elapsed, 1))
        else:
            result = ComponentHealth(
                status="error",
                latency_ms=round(elapsed, 1),
                detail=f"API {resp.status_code}: {resp.text[:200]}",
            )
    except asyncio.TimeoutError:
        elapsed = (time.monotonic() - start) * 1000
        result = ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail="请求超时（5s）")
    except httpx.RequestError as e:
        elapsed = (time.monotonic() - start) * 1000
        result = ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=f"网络错误: {e}")
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        result = ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=str(e))

    _llm_health_cache = (time.monotonic(), result)
    return result


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
            return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail="MCP 工具未加载")
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(
            status="ok",
            latency_ms=round(elapsed, 1),
            detail=f"{len(tools)} 个工具",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ComponentHealth(status="error", latency_ms=round(elapsed, 1), detail=str(e))


async def get_health_report(app: FastAPI) -> HealthResponse:
    from version import __version__

    llm = await check_llm(app)
    memory = await check_memory(app)
    native_tools = await check_native_tools(app)
    mcp_tools = await check_mcp_tools(app)

    overall: Literal["ok", "degraded"] = (
        "ok" if all(c.status == "ok" for c in [llm, memory, native_tools, mcp_tools]) else "degraded"
    )

    return HealthResponse(
        status=overall,
        version=__version__,
        llm=llm,
        memory=memory,
        native_tools=native_tools,
        mcp_tools=mcp_tools,
        timestamp=time.time(),
    )
