"""共享 fixtures — FastAPI TestClient、认证 Token、最小测试 app。"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from api.middleware.auth import AuthMiddleware


@pytest.fixture
def auth_token() -> str:
    """固定测试 Token。"""
    return "test-token-123"


@pytest.fixture
def minimal_app(auth_token: str) -> FastAPI:
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

    app.state.auth_token = auth_token
    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture
def client(minimal_app: FastAPI) -> TestClient:
    """Starlette TestClient 实例。"""
    return TestClient(minimal_app)
