"""FastAPI 应用工厂 — 生命周期管理、CORS、路由挂载、静态文件服务。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

import time

from api.const_session_store import (
    deserialize_messages,
    load_all_const_sessions,
)
from api.dependencies import get_llm, get_system_prompt, get_tools
from api.health import get_health_report
from api.providers.manager import ProviderManager
from api.providers.store import ProviderConfigStore
from api.routes import chat, files, memory, sessions, balance, providers
from api.routes import skills as skills_router
from api.routes import news as news_router
from api.session_manager import SessionManager, SessionState
from agent.graph import build_agent
from memory.narrative import MEMORY_PATH, LongTermMemoryInterface
from skills.mcp import init_mcp_tools, close_mcp
from version import __version__

WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


async def _load_const_sessions(app: FastAPI):
    """从 YAML 重建所有 const 固定会话到内存 SessionManager。"""
    sm = app.state.session_manager
    const_list = load_all_const_sessions()
    if not const_list:
        return

    from langgraph.checkpoint.memory import MemorySaver

    loaded = 0
    for const_data in const_list:
        sid = const_data.get("session_id")
        if not sid or sid in sm._sessions:
            continue

        metadata = const_data.get("metadata", {})
        const_name = const_data.get("const_name", "")
        messages = const_data.get("messages", [])

        # 重建 checkpointer
        try:
            reconstructed = deserialize_messages(messages)
            checkpointer = MemorySaver()
            if reconstructed:
                agent = build_agent(
                    model=app.state.llm,
                    tools=app.state.tools,
                    system_prompt=app.state.system_prompt,
                    checkpointer=checkpointer,
                )
                await agent.aupdate_state(
                    {"configurable": {"thread_id": sid}},
                    {"messages": reconstructed},
                )
        except Exception as e:
            print(f"[const] 重建会话 {sid} 失败: {e}")
            continue

        session = SessionState(
            session_id=sid,
            created_at=metadata.get("created_at", time.time()),
            last_active=metadata.get("last_active", time.time()),
            message_count=metadata.get("message_count", 0),
            checkpointer=checkpointer,
            is_const=True,
            const_name=const_name,
        )
        sm._sessions[sid] = session
        loaded += 1

    print(f"[const] 已加载 {loaded}/{len(const_list)} 个固定会话")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化 Provider 管理器（优先从 YAML 加载）
    provider_store = ProviderConfigStore()
    if provider_store.is_empty:
        migrated = provider_store.migrate_from_env()
        if migrated:
            print(f"[provider] migrated {migrated.label} from .env → providers.yaml")
    provider_manager = ProviderManager(provider_store)
    provider_manager.load_all()
    app.state.provider_manager = provider_manager
    print(f"[provider] loaded {provider_manager.count} provider(s)")

    # 2. 其他共享资源（LLM 从 ProviderManager 优先退化到 .env）
    app.state.llm = get_llm(provider_manager)
    app.state.system_prompt = get_system_prompt()
    app.state.native_tools = get_tools()
    app.state.session_manager = SessionManager()
    app.state.ltm = LongTermMemoryInterface(MEMORY_PATH)
    app.state.ltm.start_listening(app.state.llm)

    # 加载 MCP 工具（Word 文档编辑能力）
    app.state.mcp_tools = await init_mcp_tools()
    app.state.tools = app.state.native_tools + app.state.mcp_tools

    # 加载 const 固定会话（需要 tools 已就绪）
    await _load_const_sessions(app)

    yield

    # 关闭：清理资源
    await close_mcp()
    await app.state.ltm.stop_listening()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SonettoHere API",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST 路由
    app.include_router(sessions.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(balance.router, prefix="/api")

    # WebSocket 路由（无 /api 前缀）
    app.include_router(chat.router)

    # Provider CRUD 路由
    app.include_router(providers.router, prefix="/api")

    # Anthropic Skills
    app.include_router(skills_router.router, prefix="/api")

    # 系统更新动态
    app.include_router(news_router.router, prefix="/api")

    # 健康检查
    @app.get("/api/health")
    async def health():
        return await get_health_report(app)

    # 生产模式：serve 前端静态文件（用 /assets 前缀避免拦截 WebSocket）
    if WEB_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")

        @app.exception_handler(404)
        async def spa_fallback(request, exc):
            return FileResponse(WEB_DIR / "index.html")

    return app
