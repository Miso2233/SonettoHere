"""结构化日志工具 — 替代 print() 的统一日志入口。

用法::

    from api.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("队列已就绪")
    logger.warning("配置缺失: %s", key)
    logger.error("处理失败", exc_info=True)

trace_id 支持::

    from api.utils.logger import set_trace_id

    set_trace_id("req_abc123")
    logger.info("请求开始")  # 自动携带 trace_id
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

# ── 模块级公共符号 ──────────────────────────────────────────

__all__ = [
    "get_logger",
    "set_trace_id",
    "get_trace_id",
    "DEFAULT_FORMAT",
    "STRUCTURED_FORMAT",
]

# ── ContextVar：每个 asyncio Task 独立的 trace_id ────────────

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str | None) -> None:
    """为当前协程上下文设置 trace_id。

    Args:
        trace_id: 追踪 ID；设为 None 会恢复为默认值。
    """
    if trace_id is None:
        _trace_id.set(None)
    else:
        _trace_id.set(trace_id)


def get_trace_id() -> str | None:
    """获取当前协程上下文的 trace_id。"""
    return _trace_id.get()


# ── 格式化器 ────────────────────────────────────────────────

# 开发环境友好格式: [时间] [模块] 级别: 消息
DEFAULT_FORMAT = "[%(asctime)s] [%(name)s] %(levelname)-7s: %(message)s"

# 含 trace_id 的详细格式（用于文件日志）
STRUCTURED_FORMAT = (
    "[%(asctime)s] [%(name)s] %(levelname)-7s: %(message)s"
    "  [trace=%(trace_id)s]"
)


class TraceIdFormatter(logging.Formatter):
    """自动注入 trace_id 的格式化器。

    通过 ContextVar 获取当前协程的 trace_id，注入日志记录的 extra 字段。
    """

    def format(self, record: logging.LogRecord) -> str:
        tid = _trace_id.get()
        record.trace_id = tid or "-"
        return super().format(record)


# ── 日志级别快捷别名 ────────────────────────────────────────

CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG


# ── Logger 获取 ─────────────────────────────────────────────


def get_logger(name: str, level: int | str | None = None) -> logging.Logger:
    """获取一个结构化 Logger。

    Args:
        name: Logger 名称，通常传入 ``__name__``。
        level: 可选，覆盖全局级别设置。

    Returns:
        已配置的 :class:`logging.Logger` 实例。
    """
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger


# ── 便捷配置 ────────────────────────────────────────────────


def configure_console_logger(
    level: int | str = logging.INFO,
    fmt: str = DEFAULT_FORMAT,
) -> None:
    """快速配置控制台日志（无文件输出）。

    适用于开发环境或快速测试。

    Args:
        level: 日志级别，默认 INFO。
        fmt: 日志格式字符串。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(TraceIdFormatter(fmt))
    _apply_config(level, handler)


def configure_file_logger(
    level: int | str = logging.INFO,
    file_path: str = "logs/sonetto.log",
    fmt: str = STRUCTURED_FORMAT,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """配置文件日志（控制台 + 文件轮转）。

    Args:
        level: 日志级别，默认 INFO。
        file_path: 日志文件路径。
        fmt: 日志格式字符串。
        max_bytes: 单个日志文件最大字节数。
        backup_count: 保留的备份文件数量。
    """
    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(TraceIdFormatter(DEFAULT_FORMAT))

    # 文件 Handler（带轮转）
    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(TraceIdFormatter(fmt))
    except (OSError, PermissionError):
        # 无法写入日志文件时仅使用控制台
        file_handler = None

    handlers: list[logging.Handler] = [console_handler]
    if file_handler is not None:
        handlers.append(file_handler)

    _apply_config(level, *handlers)


def _apply_config(level: int | str, *handlers: logging.Handler) -> None:
    """将配置应用到 root logger。"""
    root = logging.getLogger()
    root.setLevel(level)
    # 清除默认 handler，避免重复
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in handlers:
        root.addHandler(h)
