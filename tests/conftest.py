"""共享 fixtures — FastAPI TestClient、认证 Token、最小测试 app。"""

import asyncio
import os

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from api.middleware.auth import AuthMiddleware
from api.middleware import auth as auth_middleware


@pytest.fixture(scope="session", autouse=True)
def _windows_proactor_policy() -> None:
    """Windows 上安装 Proactor 事件循环策略（session 级 autouse）。

    Proactor 原生支持 ``asyncio.create_subprocess_exec``，而 Selector 不支持
    子进程——run_python 子进程隔离执行相关测试依赖此策略。
    其余平台（posix）无此需求，直接跳过。
    """
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest.fixture
def auth_token() -> str:
    """固定测试 Token。"""
    return "test-token-123"


@pytest.fixture
def minimal_app(auth_token: str, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """创建一个最小化的 FastAPI app 用于测试 AuthMiddleware。

    包含：
    - 一个受保护的 /api/test 路由
    - 一个白名单 /api/health 路由
    - 一个不受保护的 /open 路由
    - 一个 /ws/test 路由（WebSocket 路径受保护）
    - AuthMiddleware
    """
    app = FastAPI()

    @app.get("/api/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/open")
    async def open_endpoint():
        return {"status": "public"}

    @app.get("/ws/test")
    async def ws_endpoint():
        return {"status": "ws"}

    # AuthMiddleware 自 #244 起直接调用 load_or_create_token() 鉴权
    # （不再读 app.state.auth_token）。此处将其替换为返回固定测试 Token，
    # 使"正确 token → 200"的用例可断言，同时避免测试读写真实的
    # config/auth_token.yaml。
    monkeypatch.setattr(auth_middleware, "load_or_create_token", lambda: auth_token)
    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture
def client(minimal_app: FastAPI) -> TestClient:
    """Starlette TestClient 实例。"""
    return TestClient(minimal_app)
