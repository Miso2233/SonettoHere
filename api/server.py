"""FastAPI 应用工厂 — 生命周期管理、CORS、路由挂载。"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import time

from api.session.const_store import (
    deserialize_messages,
    load_all_const_sessions,
)
from agent import build_agent, build_system_prompt
from api.core.health import get_health_report
from api.providers.manager import init_manager
from api.providers.store import ProviderConfigStore
from api.routes import chat, files, images, memory, sessions, balance, providers
from api.routes import path_whitelist as path_whitelist_router
from api.routes import persona as persona_router
from api.routes import sonetto_blocker as sonetto_blocker_router
from api.routes import skills as skills_router
from api.routes import news as news_router
from api.routes import mcp as mcp_router
from api.routes import restart as restart_router
from api.routes import env_vars as env_vars_router
from api.session.manager import SessionState, session_manager
from api.memory.long_term import MEMORY_PATH, LongTermMemory
from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager
from api.tools.manager import ToolManager
from api.providers.default_llm import init_provider_manager, get_default_llm
from version import __version__

from api.middleware.auth import AuthMiddleware


async def _load_const_sessions(app: FastAPI):
    """从 YAML 重建所有 const 固定会话到内存 SessionManager。"""
    sm = session_manager
    const_list = load_all_const_sessions()
    if not const_list:
        return

    if get_default_llm() is None:
        print(f"[const] Skipping {len(const_list)} const session(s) — no LLM available")
        return

    from api.memory.short_term import get_checkpointer

    loaded = 0
    for const_data in const_list:
        sid = const_data.get("session_id")
        if not sid or sm.exists(sid):
            continue

        metadata = const_data.get("metadata", {})
        const_name = const_data.get("const_name", "")
        messages = const_data.get("messages", [])

        # 用全局单例 checkpointer 重建
        try:
            reconstructed = deserialize_messages(messages)
            checkpointer = get_checkpointer()
            if reconstructed:
                agent = build_agent(
                    model=get_default_llm(),
                    tools=app.state.tool_manager.get_all(),
                    system_prompt=build_system_prompt(),
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
            is_const=True,
            const_name=const_name,
        )
        sm.put(sid, session)
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
    provider_manager = init_manager(provider_store)
    provider_manager.load_all()
    init_provider_manager(provider_manager)
    print(f"[provider] loaded {provider_manager.count} provider(s)")

    # 预加载 OpenRouter 上下文窗口数据，为已配置的模型补充信息
    from api.providers.model_context_windows import ensure_openrouter_cache, fill_missing_context_windows
    ensure_openrouter_cache()  # 启动预热
    total_filled = 0
    for p in provider_manager.list_configs():
        filled = await fill_missing_context_windows(p)
        if filled:
            provider_manager.save_config(p)
            total_filled += filled
    if total_filled:
        print(f"[context-window] auto-filled {total_filled} model(s) from OpenRouter")

    # 2. 其他共享资源（LLM 统一从 ProviderManager 获取）
    if get_default_llm() is None:
        print(
            "[llm] No LLM configured — chat will be read-only until a provider is added"
        )
    app.state.tool_manager = ToolManager()
    await app.state.tool_manager.load_all()
    app.state.ltm = LongTermMemory(MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(MEMORY_PATH)).build())
    app.state.ltm.start_listening()
    app.state.ltm.inject_all()

    # 加载 const 固定会话（需要 tools 已就绪）
    await _load_const_sessions(app)

    yield

    # 关闭：清理资源
    await app.state.tool_manager.close()
    await app.state.ltm.stop_listening()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SonettoHere API",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS：开发环境仅放行 Vite（5173），生产可加 localhost:8000
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    if os.environ.get("SONETTO_ENV") == "production":
        cors_origins += [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST 路由
    app.include_router(sessions.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(images.router, prefix="/api")
    app.include_router(balance.router, prefix="/api")

    # WebSocket 路由（无 /api 前缀）
    app.include_router(chat.router)

    # Provider CRUD 路由
    app.include_router(providers.router, prefix="/api")

    # MCP 服务器配置查看与热加载
    app.include_router(mcp_router.router, prefix="/api")

    # 人设读写 (SOUL.md / USER.md)
    app.include_router(persona_router.router, prefix="/api")

    # 本地路径白名单管理
    app.include_router(path_whitelist_router.router, prefix="/api")

    # SonettoBlocker 拒止锚管理
    app.include_router(sonetto_blocker_router.router, prefix="/api")

    # Anthropic Skills
    app.include_router(skills_router.router, prefix="/api")

    # 系统更新动态
    app.include_router(news_router.router, prefix="/api")

    # 重启后端
    app.include_router(restart_router.router, prefix="/api")

    # 工具环境变量管理
    app.include_router(env_vars_router.router, prefix="/api")

    # 健康检查
    @app.get("/api/health")
    async def health():
        return await get_health_report(app)

    # 认证中间件（在路由之后添加，确保只拦截 API/WS 路径）
    app.add_middleware(AuthMiddleware)

    return app
