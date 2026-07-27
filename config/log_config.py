"""日志配置 — 统一管理日志级别、输出目标与格式。

启动入口调用 :func:`configure_logging()` 完成初始化。
可通过环境变量 ``SONETTO_LOG_LEVEL`` 覆盖日志级别（默认 INFO）。
"""

from __future__ import annotations

import os

from api.utils.logger import (
    DEFAULT_FORMAT,
    STRUCTURED_FORMAT,
    configure_console_logger,
    configure_file_logger,
)


def resolve_log_level() -> str:
    """从环境变量解析日志级别，默认 INFO。

    优先级: SONETTO_LOG_LEVEL > SONETTO_ENV > 默认 INFO。
    """
    level = os.environ.get("SONETTO_LOG_LEVEL", "")
    if level.upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return level.upper()
    # 生产环境默认 WARNING，开发环境默认 INFO
    if os.environ.get("SONETTO_ENV") == "production":
        return "WARNING"
    return "INFO"


def configure_logging() -> None:
    """初始化全局日志配置。

    根据 ``SONETTO_ENV`` 决定输出目标：
    - production: 文件（logs/sonetto.log）+ 控制台
    - 其他（开发）: 仅控制台
    """
    level = resolve_log_level()
    env = os.environ.get("SONETTO_ENV", "development")

    if env == "production":
        from pathlib import Path

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        configure_file_logger(
            level=level,
            file_path=str(log_dir / "sonetto.log"),
            fmt=STRUCTURED_FORMAT,
        )
    else:
        configure_console_logger(
            level=level,
            fmt=DEFAULT_FORMAT,
        )
