"""SonettoHere v2.1 — LangGraph ReAct AI Agent 入口。"""

import sys


def main():
    print("SonettoHere v2.1.0")
    print("用法: python main.py [cli|qqbot|web]")
    print()

    mode = sys.argv[1] if len(sys.argv) > 1 else "cli"

    if mode == "cli":
        from clients.cli import main as cli_main
        cli_main()
    elif mode == "qqbot":
        from clients.qqbot import main as qqbot_main
        qqbot_main()
    elif mode == "web":
        import uvicorn
        from api.server import create_app
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print(f"未知模式: {mode}，可选: cli / qqbot / web")


if __name__ == "__main__":
    main()
