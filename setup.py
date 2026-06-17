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
    print("  [1/6 全自动]  检查 Node.js 是否安装")
    print("         确保你的电脑有 JavaScript 运行环境，这是Sonetto前端界面的基础")
    print()
    print("  [2/6 全自动]  创建 Python 虚拟环境，安装后端依赖")
    print("         会在当前目录创建 .venv 文件夹")
    print("         （内含 Python 解释器和所有需要的库）")
    print()
    print("  [3/6 全自动]  安装前端依赖")
    print("         下载 Vue 页面所需的 npm 包")
    print("         会在 web/node_modules/ 存放数百个小文件")
    print()
    print("  [4/6 全自动]  生成 .env 配置文件")
    print("         从 .env.example 复制一份，用来保存一些工具需要的 API 密钥")
    print()
    print("  [5/6 手动输入]  配置 LLM 提供商（对话必需）")
    print("         填写 Base URL 和 API Key，自动测试连接并保存可用模型")
    print()
    print("  [6/6 手动输入]  设定你的称呼，配置 AI 个性")
    print("         告诉 Sonetto 如何称呼你，自动完成个性文件设置")
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
        print("       您可以编辑 .env 填入你的 API 密钥（Todoist、高德、Tavily 等）供工具使用")
    else:
        print("  [!] 未找到 .env.example，如有需要请手动创建 .env")
    return True


def setup_provider():
    """引导用户添加 LLM 提供商，测试连接后保存至 providers.yaml。"""
    import json
    import re
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse

    print()
    print("  LLM 提供商是对话功能的基础。")
    print("  如果暂时跳过，之后可以随时在网页端 /providers 页面配置。")
    print()

    while True:
        print("-" * 40)
        base_url = input("  Base URL（如 https://api.deepseek.com/v1）: ").strip()
        if not base_url:
            skip("已跳过 LLM 提供商配置，之后可在网页端配置")
            return True

        api_key = input("  API Key（sk-...）: ").strip()
        if not api_key:
            skip("已跳过 LLM 提供商配置，之后可在网页端配置")
            return True

        # 测试连接：GET /models
        test_url = base_url.rstrip("/") + "/models"
        print(f"  ↻ 正在请求 {test_url} ...")
        try:
            req = urllib.request.Request(
                test_url,
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            hint = ""
            if isinstance(e, urllib.error.HTTPError) and e.code == 401:
                hint = "——可能是 API Key 错误"
            elif isinstance(e, urllib.error.HTTPError) and e.code == 404:
                hint = "——可能是 Base URL 错误"
            print(f"  [✗] 连接失败: {e}{hint}")
            print()
            choice = input("  按 Enter 重试，或输入 q 跳过: ").strip().lower()
            if choice == "q":
                skip("已跳过 LLM 提供商配置")
                return True
            continue

        models = [
            m["id"]
            for m in data.get("data", [])
            if isinstance(m, dict) and "id" in m
        ]
        if not models:
            print("  [✗] 连接成功但未获取到模型列表，请检查 Base URL 是否正确")
            print()
            choice = input("  按 Enter 重试，或输入 q 跳过: ").strip().lower()
            if choice == "q":
                skip("已跳过 LLM 提供商配置")
                return True
            continue

        ok(f"连接成功！获取到 {len(models)} 个模型")
        for m in models:
            print(f"      · {m}")
        break

    # 从 URL 提取 label / id
    parsed = urlparse(base_url)
    host = parsed.hostname or "unknown"
    label = host.split(".")[0].capitalize() if host != "unknown" else "Provider"
    provider_id = re.sub(r"[^a-z0-9-]", "", host.split(".")[0].lower()[:30])
    if not provider_id:
        provider_id = "custom-provider"

    # 写入 providers.yaml
    yaml_path = os.path.join(PROJECT_ROOT, "providers.yaml")
    models_block = "\n".join(f"  - {m}" for m in models)
    entry = f"""- api_key: {api_key}
  base_url: {base_url}
  context_window: 256000
  enabled: true
  id: {provider_id}
  label: {label}
  models:
{models_block}
  provider_type: openai
"""

    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.rstrip() + "\n" + entry
    else:
        content = "providers:\n" + entry

    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)

    ok(f"提供商「{label}」已保存至 providers.yaml")
    return True


def setup_persona():
    """询问用户称呼，从模板创建个性文件并替换占位符。"""
    PERSONAS = "config/personas"
    TEMPLATES = {
        "USER.md": "USER.example.md",
        "SOUL.md": "SOUL.example.md",
    }

    print()
    name = input('  你希望 Sonetto 怎么称呼你？（直接按 Enter 则默认为”朋友”）: ').strip()
    if not name:
        name = "朋友"
    ok(f"好的，Sonetto 之后会称呼你为「{name}」")

    for target, src in TEMPLATES.items():
        target_path = os.path.join(PROJECT_ROOT, PERSONAS, target)
        src_path = os.path.join(PROJECT_ROOT, PERSONAS, src)

        if not os.path.exists(src_path):
            print(f"  [!] 模板文件 {src} 不存在，跳过")
            continue

        # 从模板复制/覆盖
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换 {{USER_NAME}} 占位符
        content = content.replace("{{USER_NAME}}", name)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        ok(f"{target} 已就绪")

    print("  提示：以后可以随时编辑 config/personas/ 下的文件来调整设定")
    return True


def summary():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    env_ok = os.path.exists(env_path)
    prov_path = os.path.join(PROJECT_ROOT, "providers.yaml")
    prov_ok = os.path.exists(prov_path) and os.path.getsize(prov_path) > 20
    print()
    print("=" * 48)
    print("  初始化完成")
    print("=" * 48)
    print()
    print("  [✓] Python 依赖已安装")
    print("  [✓] 前端依赖已安装")
    print(f"  [{'✓' if env_ok else '−'}] .env "
          f"{'已就绪' if env_ok else '— 请从 .env.example 创建'}")
    print(f"  [{'✓' if prov_ok else '−'}] LLM 提供商 "
          f"{'已配置' if prov_ok else '— 请启动后在 /providers 页面添加'}")
    print("  [✓] AI 个性文件已配置")
    print()
    print("  接下来：")
    print()
    print("  1. 启动程序：")
    print("       start.bat")
    print("     或者在资源管理器中双击 start.bat")
    print()
    print("  2. 若未配置 LLM 提供商，启动后访问")
    print("     http://localhost:5173/providers 添加")
    print()
    print("  3.（可选）定制 AI 个性：")
    print("     编辑 config\\personas\\USER.md  — 你的自我介绍")
    print("     编辑 config\\personas\\SOUL.md  — AI 人设")
    print()


def main():
    header()
    total = 6

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

    step(5, total, "LLM 提供商")
    setup_provider()

    step(6, total, "AI 个性配置")
    setup_persona()

    summary()


if __name__ == "__main__":
    main()
