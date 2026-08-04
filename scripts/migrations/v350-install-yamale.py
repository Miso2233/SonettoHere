#!/usr/bin/env python3
"""配置迁移 — 确保 yamale 已安装（v3.5.0 工作坊 schema 校验依赖）。

v3.5.0（工作坊体系 #277）引入 yamale 用于 studios/*.yaml 的 schema 校验，
但旧版本升级用户可能缺失该依赖。本脚本幂等：
- 已安装且版本 >= 5.0 → 直接通过
- 未安装或版本过低 → 用当前解释器（upgrade.py 保证为 .venv）pip 安装

依赖安装失败时以非零码退出，upgrade.py 会中止并提示。
"""

import importlib.metadata
import importlib.util
import subprocess
import sys

MIN_YAMALE_VERSION = (5, 0)


def _yamale_ok() -> bool:
    """检测 yamale 是否已安装且版本满足要求。"""
    if importlib.util.find_spec("yamale") is None:
        return False
    try:
        version = importlib.metadata.version("yamale")
    except importlib.metadata.PackageNotFoundError:
        return False
    try:
        parts = tuple(int(part) for part in version.split(".")[:2])
    except ValueError:
        # 非数字版本号（如 4.9.2rc1 这类 pre-release 后缀）无法确认满足
        # requirements.txt 的 >= 5.0，保守视为未满足，触发一次 pip 安装
        # （pip 会自行判断已装版本是否满足，多余执行无害且幂等）
        return False
    return parts >= MIN_YAMALE_VERSION


def main() -> None:
    if _yamale_ok():
        print("[migration] yamale 已安装且版本满足要求，跳过")
        return
    print("[migration] 未检测到 yamale（>= 5.0），正在安装 ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "yamale>=5.0"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[migration] yamale 安装失败:\n{result.stderr}")
        sys.exit(1)
    print("[migration] ✔ yamale 安装完成")


if __name__ == "__main__":
    main()
