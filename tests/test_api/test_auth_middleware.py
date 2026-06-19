"""api/middleware/auth.py 测试 — AuthMiddleware 认证拦截逻辑。"""


class TestAuthMiddleware:
    """AuthMiddleware 认证逻辑测试。"""

    def test_unprotected_path_passthrough(self, client):
        """非 /api/ 非 /ws/ 路径不受保护。"""
        resp = client.get("/open")
        assert resp.status_code == 200
        assert resp.json() == {"status": "public"}

    def test_health_whitelist(self, client):
        """/api/health 白名单放行。"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_missing_token_returns_401(self, client):
        """未提供 token → 401。"""
        resp = client.get("/api/test")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["detail"]

    def test_wrong_token_returns_401(self, client):
        """token 不匹配 → 401。"""
        resp = client.get("/api/test", headers={"X-Sonetto-Token": "wrong-token"})
        assert resp.status_code == 401

    def test_correct_header_token(self, client, auth_token):
        """X-Sonetto-Token 正确 → 200。"""
        resp = client.get("/api/test", headers={"X-Sonetto-Token": auth_token})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_correct_query_token(self, client, auth_token):
        """?token= 正确 → 200。"""
        resp = client.get(f"/api/test?token={auth_token}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_query_token_wrong_still_401(self, client):
        """?token= 值错误 → 401。"""
        resp = client.get("/api/test?token=wrong-token")
        assert resp.status_code == 401

    def test_ws_path_protected(self, client):
        """/ws/ 路径受保护。"""
        resp = client.get("/ws/test")
        assert resp.status_code == 401

    def test_ws_path_with_valid_token(self, client, auth_token):
        """/ws/ 路径带有效 token → 200。"""
        resp = client.get(f"/ws/test?token={auth_token}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ws"}

    def test_ws_path_with_wrong_token(self, client):
        """/ws/ 路径带无效 token → 401。"""
        resp = client.get("/ws/test?token=wrong")
        assert resp.status_code == 401

    def test_query_token_with_extra_params(self, client, auth_token):
        """?token= 后还有其他 query params 时仍正确提取。"""
        resp = client.get(f"/api/test?token={auth_token}&other=value")
        assert resp.status_code == 200


class TestAuthMiddlewareNoToken:
    """app.state.auth_token 为 None 时的行为。"""

    def test_empty_auth_token_returns_401(self, client):
        """app.state.auth_token 为 None → 401。"""
        # 覆盖 fixture：设置 auth_token 为 None
        client.app.state.auth_token = None
        resp = client.get("/api/test", headers={"X-Sonetto-Token": "any-token"})
        assert resp.status_code == 401
