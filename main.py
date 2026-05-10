"""SonettoHere v2.0 — LangGraph ReAct AI Agent 入口。"""

import sys


def main():
    print("SonettoHere v2.0.0")
    print("用法: python main.py [cli|qqbot]")
    print()

    mode = sys.argv[1] if len(sys.argv) > 1 else "cli"

    if mode == "cli":
        from clients.cli import main as cli_main
        cli_main()
    elif mode == "qqbot":
        from clients.qqbot import main as qqbot_main
        qqbot_main()
    else:
        print(f"未知模式: {mode}，可选: cli / qqbot")


if __name__ == "__main__":
    main()
