"""api/auth.py 测试 — Token 生成、加载、轮换。"""

import pytest
import yaml

import api.auth as auth


class TestLoadOrCreateToken:
    """load_or_create_token 测试。"""

    def test_load_existing_token(self, monkeypatch, tmp_path):
        """文件存在且有有效 token key → 返回已有值。"""
        token_path = tmp_path / "auth_token.yaml"
        token_path.write_text(
            yaml.dump({"token": "existing-token-value"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.load_or_create_token()

        assert result == "existing-token-value"

    def test_load_or_create_creates_new(self, monkeypatch, tmp_path):
        """文件不存在 → 生成并写入新 token。"""
        token_path = tmp_path / "auth_token.yaml"
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.load_or_create_token()

        assert token_path.exists()
        assert isinstance(result, str)
        assert len(result) > 0
        # 验证写入内容
        data = yaml.safe_load(token_path.read_text(encoding="utf-8"))
        assert data["token"] == result

    def test_load_or_create_corrupted_file(self, monkeypatch, tmp_path):
        """文件存在但 YAML 无效 → 抛出异常（生产代码暂未处理此情况）。"""
        import yaml
        token_path = tmp_path / "auth_token.yaml"
        token_path.write_text("{{ 无效 yaml !!", encoding="utf-8")
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        with pytest.raises(yaml.parser.ParserError):
            auth.load_or_create_token()

    def test_load_or_create_missing_key(self, monkeypatch, tmp_path):
        """文件存在但无 token key → 重新生成。"""
        token_path = tmp_path / "auth_token.yaml"
        token_path.write_text(
            yaml.dump({"other_key": "value"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.load_or_create_token()

        assert isinstance(result, str)
        assert len(result) > 0
        data = yaml.safe_load(token_path.read_text(encoding="utf-8"))
        assert data["token"] == result


class TestRotateToken:
    """rotate_token 测试。"""

    def test_rotate_creates_new_token(self, monkeypatch, tmp_path):
        """rotate_token 返回新值并写入文件。"""
        token_path = tmp_path / "auth_token.yaml"
        # 先创建一个已有 token
        token_path.write_text(
            yaml.dump({"token": "old-token"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.rotate_token()

        assert isinstance(result, str)
        assert len(result) > 0
        data = yaml.safe_load(token_path.read_text(encoding="utf-8"))
        assert data["token"] == result

    def test_rotate_different_from_old(self, monkeypatch, tmp_path):
        """轮换前后 token 不同。"""
        token_path = tmp_path / "auth_token.yaml"
        token_path.write_text(
            yaml.dump({"token": "old-token"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.rotate_token()

        assert result != "old-token"

    def test_rotate_writes_file_even_if_not_exists(self, monkeypatch, tmp_path):
        """rotate_token 在文件不存在时也创建。"""
        token_path = tmp_path / "auth_token.yaml"
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        result = auth.rotate_token()

        assert token_path.exists()
        data = yaml.safe_load(token_path.read_text(encoding="utf-8"))
        assert data["token"] == result


class TestTokenFormat:
    """Token 格式验证。"""

    def test_token_format(self, monkeypatch, tmp_path):
        """生成的 token 是 43 字符 URL-safe base64。"""
        token_path = tmp_path / "auth_token.yaml"
        monkeypatch.setattr(auth, "AUTH_TOKEN_PATH", token_path)

        token = auth.load_or_create_token()

        # token_urlsafe(32) → 43 chars, no padding chars like + or /
        assert len(token) == 43
        # URL-safe: only letters, digits, -, _
        assert all(c.isalnum() or c in "-_" for c in token)
