"""SonettoHere — 首次设置脚本
用法: python setup.py
"""

import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def header():
    print("=" * 48)
    print("  SonettoHere v2.0.0 — 首次初始化")
    print("=" * 48)
    print()
    print("本脚本将自动安装依赖并准备好运行环境。")
    print("初始化完成后，运行 start.bat 即可启动。")
    print()


def welcome(total: int):
    """新手友好的开头总结"""
    print("本脚本将一步步帮你准备好运行 SonettoHere 所需的一切。")
    print()
    print(f"一共 {total} 步，分别是：")
    print()
    print("  [1/4]  检查 Node.js 是否安装")
    print("         确保你的电脑有 JavaScript 运行环境，这是Sonetto前端界面的基础")
    print()
    print("  [2/4]  创建 Python 虚拟环境，安装后端依赖")
    print("         会在当前目录创建 .venv 文件夹")
    print("         （内含 Python 解释器和所有需要的库）")
    print()
    print("  [3/4]  安装前端依赖")
    print("         下载 Vue 页面所需的 npm 包")
    print("         会在 web/node_modules/ 存放数百个小文件")
    print()
    print("  [4/4]  生成 .env 配置文件")
    print("         从 .env.example 复制一份，用来保存一些工具需要的 API 密钥")
    print()
    print("对电脑的影响：")
    print("  • 不修改系统文件，不写注册表，不装全局工具")
    print("  • 仅在项目文件夹内创建文件与目录")
    print()
    print("需要联网：会从 npm 和 PyPI 下载包（共约 200-400 MB）")
    print()


def step(n, total, label):
    print(f"\n[{n}/{total}] {label}")
    print("-" * 40)


def ok(msg):
    print(f"  [✓]  {msg}")


def skip(msg):
    print(f"  [−] {msg}")


def fail(msg):
    print(f"  [✗] {msg}")
    return False


def _npm_cmd():
    return ["npm"]

def _node_cmd():
    return ["node"]


def check_nodejs():
    try:
        r = subprocess.run(_node_cmd() + ["--version"], capture_output=True, text=True, shell=True)
        if r.returncode != 0:
            return fail("未找到 Node.js，请从 https://nodejs.org/ 下载安装")
        ver = r.stdout.strip()
        major = ver.lstrip("v").split(".")[0]
        if int(major) < 18:
            print(f"  [!] 建议 Node.js v18+（Vite 5 要求），当前 {ver}")
        else:
            ok(f"Node.js {ver}")
        return True
    except FileNotFoundError:
        return fail("未找到 Node.js，请从 https://nodejs.org/ 下载安装")


def setup_venv():
    if os.path.exists(os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")):
        skip(".venv 已存在")
    else:
        print("  正在创建虚拟环境 ...")
        r = subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=PROJECT_ROOT)
        if r.returncode != 0:
            return fail("创建虚拟环境失败")
        ok(".venv 已创建")

    print("  正在安装 Python 依赖（这可能需要一些时间）...")
    pip = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "pip")
    r = subprocess.run([pip, "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT)
    if r.returncode != 0:
        return fail("pip 安装失败，请检查网络连接")
    ok("Python 依赖已安装")
    return True


def setup_frontend():
    node_modules = os.path.join(PROJECT_ROOT, "web", "node_modules")
    if os.path.exists(node_modules):
        skip("web/node_modules 已存在")
        return True

    print("  正在安装前端 npm 包 ...")
    r = subprocess.run(_npm_cmd() + ["install"], cwd=os.path.join(PROJECT_ROOT, "web"), shell=True)
    if r.returncode != 0:
        return fail("npm install 失败")
    ok("前端依赖已安装")
    return True


def setup_env():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    example_path = os.path.join(PROJECT_ROOT, ".env.example")

    if os.path.exists(env_path):
        skip(".env 已存在")
        return True

    if os.path.exists(example_path):
        shutil.copy2(example_path, env_path)
        ok("已从 .env.example 创建 .env")
        print("       请编辑 .env 填入你的 API 密钥（Todoist、高德、Tavily 等）")
    else:
        print("  [!] 未找到 .env.example，如有需要请手动创建 .env")
    return True


def summary():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    env_ok = os.path.exists(env_path)
    print()
    print("=" * 48)
    print("  初始化完成")
    print("=" * 48)
    print()
    print("  [✓] Python 依赖已安装")
    print("  [✓] 前端依赖已安装")
    print(f"  [{'✓' if env_ok else '−'}] .env "
          f"{'已就绪' if env_ok else '— 请从 .env.example 创建'}")
    print()
    print("  接下来：")
    print()
    print("  1. 启动程序：")
    print("       start.bat")
    print("     或者在资源管理器中双击 start.bat")
    print()
    print("  2. 配置 LLM 提供商（对话必需）：")
    print("     启动后访问 http://localhost:5173/providers")
    print("     添加兼容 OpenAI API 的提供商")
    print("     （如 DeepSeek、OpenAI、OpenRouter 等）")
    print()
    print("  3.（可选）定制 AI 个性：")
    print("     编辑 config\\personas\\USER.md  — 你的自我介绍")
    print("     编辑 config\\personas\\SOUL.md  — AI 人设")
    print()


def main():
    header()
    total = 4

    welcome(total)
    try:
        input("按 Enter 键开始安装，或关闭窗口取消...")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        sys.exit(0)
    print()

    step(1, total, "前置检查")
    if not check_nodejs():
        sys.exit(1)

    step(2, total, "Python 虚拟环境")
    if not setup_venv():
        sys.exit(1)

    step(3, total, "前端依赖")
    if not setup_frontend():
        sys.exit(1)

    step(4, total, "环境配置")
    setup_env()

    summary()


if __name__ == "__main__":
    main()
