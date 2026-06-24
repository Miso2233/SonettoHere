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

    def test_ws_path_protected(self, client):
        """/ws/ 路径受保护。"""
        resp = client.get("/ws/test")
        assert resp.status_code == 401

    def test_ws_path_with_valid_token(self, client, auth_token):
        """/ws/ 路径带 X-Sonetto-Token 头 → 200。"""
        resp = client.get("/ws/test", headers={"X-Sonetto-Token": auth_token})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ws"}

    def test_ws_path_with_wrong_token(self, client):
        """/ws/ 路径带错误 X-Sonetto-Token → 401。"""
        resp = client.get("/ws/test", headers={"X-Sonetto-Token": "wrong"})
        assert resp.status_code == 401

    def test_query_param_no_longer_works(self, client):
        """/api/ 路径仅接受 Header，?token= 查询参数不再有效。"""
        resp = client.get("/api/test?token=any-token")
        assert resp.status_code == 401


class TestAuthMiddlewareNoToken:
    """app.state.auth_token 为 None 时的行为。"""

    def test_empty_auth_token_returns_401(self, client):
        """app.state.auth_token 为 None → 401。"""
        # 覆盖 fixture：设置 auth_token 为 None
        client.app.state.auth_token = None
        resp = client.get("/api/test", headers={"X-Sonetto-Token": "any-token"})
        assert resp.status_code == 401
