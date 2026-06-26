"""Token 认证管理 — 生成、加载、轮换。"""

import secrets

import yaml

from _appdirs import get_api_data_dir

AUTH_TOKEN_PATH = get_api_data_dir() / "auth_token.yaml"


def load_or_create_token() -> str:
    """从 auth_token.yaml 加载 Token，不存在则生成并持久化。"""
    if AUTH_TOKEN_PATH.exists():
        data = yaml.safe_load(AUTH_TOKEN_PATH.read_text(encoding="utf-8"))
        if data and "token" in data:
            return data["token"]

    token = secrets.token_urlsafe(32)
    AUTH_TOKEN_PATH.write_text(
        yaml.dump({"token": token}, encoding="utf-8").decode("utf-8"),
        encoding="utf-8",
    )
    return token


def rotate_token() -> str:
    """轮换 Token，覆盖写入文件并返回新值。"""
    token = secrets.token_urlsafe(32)
    AUTH_TOKEN_PATH.write_text(
        yaml.dump({"token": token}, encoding="utf-8").decode("utf-8"),
        encoding="utf-8",
    )
    return token
