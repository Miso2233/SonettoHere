"""SonettoHere v2.0.0 — LangGraph ReAct AI Agent Web 入口。"""

import uvicorn

from api.server import create_app
from memory.user_init import ensure_all


def main():
    print("SonettoHere v2.0.0")
    print()

    ensure_all()

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
