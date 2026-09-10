"""FastAPI 应用工厂 — 生命周期管理、CORS、路由挂载。"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.health import get_health_report
from api.providers.manager import init_manager, get_manager
from api.providers.enrich import enrich_all_providers
from api.providers.store import ProviderConfigStore
from api.core.auth import load_or_create_token
from api.routes import chat, files, images, memory, sessions, balance, providers
from api.routes import path_whitelist as path_whitelist_router
from api.routes import persona as persona_router
from api.routes import sonetto_blocker as sonetto_blocker_router
from api.routes import skills as skills_router
from api.routes import studios as studios_router
from api.routes import news as news_router
from api.routes import mcp as mcp_router
from api.routes import restart as restart_router
from api.routes import env_vars as env_vars_router
from api.memory.long_term import MEMORY_PATH, LongTermMemory
from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager
from api.tools.manager import ToolManager
from api.edge_light import EdgeLightController, set_active_controller
from version import __version__

from api.middleware.auth import AuthMiddleware
from api.middleware.logging import TraceIdMiddleware
from api.utils.logger import get_logger

_log = get_logger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. 确保认证 Token 提前就绪：Vite dev/build 启动时会读取 auth_token.yaml
    #    注入 __API_TOKEN__，若后端尚未生成该文件，前端将嵌入空 Token 导致全站 401。
    load_or_create_token()

    # 1. 初始化 Provider 管理器（从 YAML 加载）
    provider_store = ProviderConfigStore()
    provider_manager = init_manager(provider_store)
    provider_manager.load_all()
    _log.info("loaded %d provider(s)", provider_manager.count)

    # 预加载 OpenRouter 上下文窗口数据，为已配置的模型补充信息
    await enrich_all_providers(provider_manager)

    # 2. 其他共享资源（LLM 统一从 ProviderManager 获取）
    if provider_manager.get_default_llm() is None:
        _log.warning("未配置 LLM — 对话将处于只读状态")
    app.state.tool_manager = ToolManager()
    await app.state.tool_manager.load_all()
    app.state.ltm = LongTermMemory(MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(MEMORY_PATH)).build())
    app.state.ltm.start()

    # 屏幕边缘灯控制器（Computer Use 状态提示）：惰性启动原生覆盖层子进程
    app.state.edge_light = EdgeLightController()
    set_active_controller(app.state.edge_light)

    yield

    # 关闭：清理资源
    set_active_controller(None)
    app.state.edge_light.shutdown()
    await app.state.tool_manager.close()
    await app.state.ltm.stop()


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

    # Trace ID 中间件（在所有路由之前注入）
    app.add_middleware(TraceIdMiddleware)

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

    # 工作坊（Studio）
    app.include_router(studios_router.router, prefix="/api")

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
