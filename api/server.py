"""FastAPI 应用工厂 — 生命周期管理、CORS、路由挂载、静态文件服务。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from api.dependencies import get_llm, get_system_prompt, get_tools
from api.health import get_health_report
from api.routes import chat, files, memory, sessions, balance
from api.session_manager import SessionManager
from memory.narrative import MEMORY_PATH, LongTermMemoryInterface
from skills.mcp import init_mcp_tools, close_mcp
from version import __version__

WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化共享资源
    app.state.llm = get_llm()
    app.state.system_prompt = get_system_prompt()
    app.state.native_tools = get_tools()
    app.state.session_manager = SessionManager()
    app.state.ltm = LongTermMemoryInterface(MEMORY_PATH)
    app.state.ltm.start_listening(app.state.llm)

    # 加载 MCP 工具（Word 文档编辑能力）
    app.state.mcp_tools = await init_mcp_tools()
    app.state.tools = app.state.native_tools + app.state.mcp_tools

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
