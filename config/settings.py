"""Pydantic BaseSettings，从 .env 文件加载配置。"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，所有 API Key 从环境变量/.env 加载。"""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Todoist
    todoist_api_token: str = ""

    # UAPI（天气/娱乐）
    uapis_api_key: str = ""

    # 高德地图
    amap_api_key: str = ""

    # QQ Bot
    qq_appid: str = ""
    qq_token: str = ""

    # 模型上下文窗口大小（DeepSeek V4 Flash = 1M tokens）
    model_context_window: int = 1000000

    # 模型名称
    model_name: str = "deepseek-v4-flash"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局 Settings 单例。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
