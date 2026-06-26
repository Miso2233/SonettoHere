"""SonettoHere 应用路径统一管理。

所有数据文件/目录路径集中在此模块计算，取代各模块中散落的
``Path(__file__).resolve().parent / ...`` 模式。

路径解析优先级：
1. ``SONETTO_HOME`` 环境变量（最高优先级，用户自定义）
2. 平台标准数据目录（打包模式，PyInstaller frozen）
3. 项目根目录（开发模式，裸 Python 运行）

平台标准数据目录（由 ``platformdirs`` 决定）：
- Windows: ``%APPDATA%/SonettoHere/``
- macOS: ``~/Library/Application Support/SonettoHere/``
- Linux: ``~/.local/share/SonettoHere/``
"""

import os
import sys
from pathlib import Path


def _frozen() -> bool:
    """检测是否在 PyInstaller 打包环境中运行。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_sonetto_home() -> Path:
    """获取 SonettoHere 数据根目录。

    - ``SONETTO_HOME`` 环境变量优先
    - 打包模式下使用平台标准数据目录
    - 开发模式下使用项目根目录
    """
    env = os.environ.get("SONETTO_HOME")
    if env:
        return Path(env).resolve()
    if _frozen():
        import platformdirs

        return Path(platformdirs.user_data_dir("SonettoHere", "SonettoHere"))
    # 开发模式：_appdirs.py 在项目根目录
    return Path(__file__).resolve().parent


# ── 数据子目录 ─────────────────────────────────────────────


def get_personas_dir() -> Path:
    """config/personas/ — SOUL.md, USER.md, AGENTS.md, memory.yaml"""
    return get_sonetto_home() / "config" / "personas"


def get_api_data_dir() -> Path:
    """api/data/ — auth_token.yaml, path_whitelist.yaml, sonetto_blocker.yaml, news.yaml, SonettoBlocker"""
    return get_sonetto_home() / "api" / "data"


def get_const_sessions_dir() -> Path:
    """api/data/const-sessions/ — 固定会话 YAML 文件"""
    return get_api_data_dir() / "const-sessions"


def get_skills_dir() -> Path:
    """anthropic_skills/ — SKILL.md 定义文件（可能与数据目录同级或独立）"""
    return get_sonetto_home() / "anthropic_skills"


def get_macros_dir() -> Path:
    """macros/ — MACRO.md 定义文件"""
    return get_sonetto_home() / "macros"


def get_output_dir() -> Path:
    """output/ — 工具输出文件"""
    return get_sonetto_home() / "output"


# ── 根级数据文件 ──────────────────────────────────────────


def get_env_path() -> Path:
    """.env — 第三方 API Key 文件"""
    return get_sonetto_home() / ".env"


def get_providers_path() -> Path:
    """providers.yaml — LLM 提供商配置"""
    return get_sonetto_home() / "providers.yaml"


# ── 辅助函数 ──────────────────────────────────────────────


def ensure_data_dirs() -> None:
    """确保所有数据子目录存在。

    在 ``main.py`` 启动时调用一次（打包模式下），
    开发模式下由各模块按需创建。
    """
    dirs = [
        get_personas_dir(),
        get_api_data_dir(),
        get_const_sessions_dir(),
        get_output_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
