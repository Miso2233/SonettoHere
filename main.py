"""SonettoHere v2.6.0 — LangGraph ReAct AI Agent Web 入口。"""

import os
import sys
from pathlib import Path

import uvicorn

from _appdirs import ensure_data_dirs, get_sonetto_home
from api.server import create_app
from memory.user_init import ensure_all

# 默认监听端口，可通过 SONETTO_PORT 环境变量覆盖
DEFAULT_PORT = int(os.environ.get("SONETTO_PORT", "8000"))


def _is_frozen() -> bool:
    """检测是否在 PyInstaller 打包环境中运行。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _maybe_migrate_legacy_data() -> None:
    """首次在打包模式下运行时，将旧项目根目录的数据迁移到统一数据目录。

    检测条件：旧项目根目录（sys._MEIPASS 的父级或同级的可能位置）
    存在 ``config/personas/`` 或 ``api/data/auth_token.yaml`` 等用户数据文件。

    迁移策略：仅复制不存在的文件，不覆盖已有文件。
    """
    data_dir = get_sonetto_home()
    migrated_flag = data_dir / ".migrated"
    if migrated_flag.exists():
        return  # 已迁移过

    # 可能的老数据位置：打包文件所在目录
    if _is_frozen():
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path.cwd()

    candidate_dirs = [
        exe_dir,
        exe_dir.parent,
    ]

    import shutil

    _LEGACY_DATA_PATHS = [
        ("config", "personas", "SOUL.md"),
        ("config", "personas", "USER.md"),
        ("config", "personas", "AGENTS.md"),
        ("config", "personas", "memory.yaml"),
        ("api", "data", "auth_token.yaml"),
        ("api", "data", "path_whitelist.yaml"),
        ("api", "data", "sonetto_blocker.yaml"),
        ("api", "data", "news.yaml"),
    ]

    migrated_any = False
    for base in candidate_dirs:
        if not base.is_dir():
            continue
        for *parts, filename in _LEGACY_DATA_PATHS:
            src = base.joinpath(*parts, filename)
            if not src.exists():
                continue
            # 相对路径镜像到数据目录
            rel = Path(*parts)
            dst = data_dir / rel / filename
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src, dst)
                    print(f"[migrate] 已迁移: {filename}")
                    migrated_any = True
                except OSError as e:
                    print(f"[migrate] 迁移 {filename} 失败: {e}")

    # 迁移 .env 和 providers.yaml（根级文件）
    for base in candidate_dirs:
        if not base.is_dir():
            continue
        for filename in (".env", "providers.yaml"):
            src = base / filename
            if src.exists():
                dst = data_dir / filename
                if not dst.exists():
                    try:
                        shutil.copy2(src, dst)
                        print(f"[migrate] 已迁移: {filename}")
                        migrated_any = True
                    except OSError as e:
                        print(f"[migrate] 迁移 {filename} 失败: {e}")

    # 迁移 anthropic_skills/ 和 macros/（只复制目录结构，不覆盖）
    for subdir in ("anthropic_skills", "macros"):
        for base in candidate_dirs:
            src = base / subdir
            if src.is_dir():
                dst = data_dir / subdir
                if not dst.exists():
                    try:
                        shutil.copytree(src, dst, dirs_exist_ok=False)
                        print(f"[migrate] 已迁移目录: {subdir}/")
                        migrated_any = True
                    except OSError as e:
                        print(f"[migrate] 迁移 {subdir}/ 失败: {e}")

    if migrated_any:
        migrated_flag.write_text("", encoding="utf-8")
        print(f"[migrate] 数据已迁移至: {data_dir}")
    else:
        # 即使没有数据可迁移，也写入标记避免重复扫描
        migrated_flag.write_text("", encoding="utf-8")


def main():
    # CLI：轮换 Token
    if "--rotate-token" in sys.argv:
        from api.auth import rotate_token

        rotated = rotate_token()
        print(f"[auth] Token rotated: {rotated}")
        return

    print("SonettoHere v2.6.0")
    print()

    # 打包模式下执行迁移和数据目录初始化
    if _is_frozen():
        _maybe_migrate_legacy_data()
        ensure_data_dirs()

    ensure_all()

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
