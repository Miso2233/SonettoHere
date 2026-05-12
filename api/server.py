"""FastAPI 应用工厂 — 生命周期管理、CORS、路由挂载、静态文件服务。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.dependencies import get_llm, get_system_prompt, get_tools
from api.routes import chat, memory, sessions
from api.session_manager import SessionManager
from memory.narrative import MEMORY_PATH, LongTermMemoryInterface

WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化共享资源
    app.state.llm = get_llm()
    app.state.system_prompt = get_system_prompt()
    app.state.tools = get_tools()
    app.state.session_manager = SessionManager()
    app.state.ltm = LongTermMemoryInterface(MEMORY_PATH)
    app.state.ltm.start_listening(app.state.llm)

    yield

    # 关闭：清理资源
    await app.state.ltm.stop_listening()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SonettoHere API",
        version="2.1.0",
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

    # WebSocket 路由（无 /api 前缀）
    app.include_router(chat.router)

    # 健康检查
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "2.1.0"}

    # 生产模式：serve 前端静态文件
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")

    return app
