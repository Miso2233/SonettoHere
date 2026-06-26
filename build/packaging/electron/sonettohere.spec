# -*- mode: python ; coding: utf-8 -*-
"""SonettoHere Desktop — PyInstaller 打包配置。

用法: pyinstaller build/packaging/electron/sonettohere.spec --clean
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# ── 收集运行时数据文件 ──────────────────────────────────────


def _collect_data() -> list[tuple[str, str]]:
    """返回 (source_path, dest_within_bundle) 列表。

    只包含只读数据（代码、模板），不包含用户数据
    （用户数据由 SONETTO_HOME 管理）。
    """
    data: list[tuple[str, str]] = []

    # Agent 核心代码（在 bundle 中保持目录结构）
    data.append((str(ROOT / "agent"), "agent"))
    data.append((str(ROOT / "memory"), "memory"))

    # Anthropic Skills / Macros（只读参考，写入到用户数据目录的副本）
    skills_src = ROOT / "anthropic_skills"
    if skills_src.is_dir():
        data.append((str(skills_src), "anthropic_skills"))
    macros_src = ROOT / "macros"
    if macros_src.is_dir():
        data.append((str(macros_src), "macros"))

    # 人设模板（只读示例文件，不包含用户实际数据）
    persona_src = ROOT / "config" / "personas"
    for name in ("SOUL.example.md", "USER.example.md", "AGENTS.md"):
        p = persona_src / name
        if p.exists():
            data.append((str(p), "config/personas"))

    # .env.example 模板
    env_example = ROOT / ".env.example"
    if env_example.exists():
        data.append((str(env_example), "."))

    # 前端构建产物
    web_dist = ROOT / "web" / "dist"
    if web_dist.is_dir():
        for f in web_dist.rglob("*"):
            if f.is_file():
                rel = f.relative_to(ROOT)
                data.append((str(f), str(rel.parent)))

    return data


# ── 隐式导入 ───────────────────────────────────────────────

_HIDDEN_IMPORTS = [
    # FastAPI / Starlette 生态
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "starlette.middleware.cors",
    "starlette.routing",
    # LangChain / LangGraph
    "langchain_openai",
    "langchain_mcp_adapters",
    "langgraph.checkpoint.memory",
    "langgraph.prebuilt",
    "langgraph.graph",
    "langchain_core.tools",
    "langchain_core.messages",
    "langchain.agents",
    "langchain.schema",
    "pydantic",
    "pydantic_settings",
    # 第三方服务 SDK
    "yaml",
    "portalocker",
    "dotenv",
    "requests",
    "todoist_api_python",
    "uapi",
    "platformdirs",
    # Tkinter（文件选择器）
    "tkinter",
    "tkinter.filedialog",
]

# ── 排除项（缩小体积） ───────────────────────────────────────

_EXCLUDES = [
    "playwright",
    "moviepy",
    "tkinter.test",
    "unittest",
    "distutils",
    "setuptools",
    "Cython",
    "PyInstaller",
    "pdb",
    "zoneinfo",
]

# ── PyInstaller Analysis ───────────────────────────────────

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=_collect_data(),
    hiddenimports=_HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    excludes=_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sonettohere-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 生产环境可设为 False（无窗口）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
