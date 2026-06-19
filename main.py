"""SonettoHere v2.0.0 — LangGraph ReAct AI Agent Web 入口。"""

import sys

import uvicorn

from api.server import create_app
from memory.user_init import ensure_all


def main():
    # CLI：轮换 Token
    if "--rotate-token" in sys.argv:
        from api.auth import rotate_token
        rotated = rotate_token()
        print(f"[auth] Token rotated: {rotated}")
        return

    print("SonettoHere v2.0.0")
    print()

    ensure_all()

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
