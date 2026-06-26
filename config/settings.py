"""Pydantic BaseSettings，从 .env 文件加载配置。

LLM 提供商配置（API key、base_url、model、context_window）
已移至 providers.yaml，通过 Web UI /providers 管理。
此文件仅保留工具类凭据和第三方服务 API key。

.env 路径解析：
1. 优先使用 ``_appdirs.get_env_path()``（支持 ``SONETTO_HOME`` 环境变量）
2. 回退到工作目录下的 ``.env``
"""

from pydantic_settings import BaseSettings

from _appdirs import get_env_path


class Settings(BaseSettings):
    """全局配置，所有 API Key 从环境变量/.env 加载。"""

    # ZhiPu AI (GLM-5V-Turbo 图片理解工具)
    zhipuai_api_key: str = ""

    # Todoist
    todoist_api_token: str = ""

    # UAPI（天气/娱乐）
    uapis_api_key: str = ""

    # 高德地图
    amap_api_key: str = ""

    # Tavily（网络搜索/提取）
    tavily_api_key: str = ""

    model_config = {
        "env_file": str(get_env_path()),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局 Settings 单例。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
