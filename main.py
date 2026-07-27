"""SonettoHere — LangGraph ReAct AI Agent Web 入口。"""

import sys

import uvicorn
from version import __version__

from api.server import create_app
from api.memory.user_init import ensure_all
from config.log_config import configure_logging
from api.utils.logger import get_logger


def main():
    # 1. 初始化日志（必须在其他模块导入之前）
    configure_logging()

    logger = get_logger("main")

    # CLI：轮换 Token
    if "--rotate-token" in sys.argv:
        from api.core.auth import rotate_token

        rotated = rotate_token()
        logger.info("Token rotated: %s", rotated)
        return

    logger.info("SonettoHere %s", __version__)

    ensure_all()

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
