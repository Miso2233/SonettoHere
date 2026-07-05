#!/usr/bin/env python3
"""SonettoHere — 本地配置自动升级器

工作流程：
  1. 读取当前配置版本号（local-config-manifest.yaml）
  2. git pull 拉取最新代码
  3. 读取新版本号
  4. 发现并依次执行 scripts/migrations/from{X}to{X+1}.py
  5. 验证最终版本号

用法:
  python upgrade.py
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "local-config-manifest.yaml"
MIGRATIONS_DIR = PROJECT_ROOT / "scripts" / "migrations"


def read_version() -> int:
    """从 manifest 解析 version 字段。"""
    import yaml

    if not MANIFEST_PATH.exists():
        print("[upgrade] 未找到 local-config-manifest.yaml，跳过升级")
        sys.exit(0)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    version = data.get("version")
    if version is None:
        print("[upgrade] manifest 中缺少 version 字段")
        sys.exit(1)
    return int(version)


def git_pull() -> bool:
    """执行 git pull，返回是否有新提交拉取。"""
    print("[upgrade] git pull ...")
    result = subprocess.run(
        ["git", "pull"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[upgrade] git pull 失败:\n{result.stderr}")
        sys.exit(1)

    stdout = result.stdout.strip()
    if "Already up to date" in stdout:
        print("[upgrade] 已是最新，无需升级")
        return False
    print(f"[upgrade] 已拉取更新")
    return True


def discover_scripts(old_version: int, new_version: int) -> list[Path]:
    """扫描迁移目录，找出 old→new 之间所有需要执行的脚本。

    匹配 scripts/migrations/from{X}to{X+1}.py 文件名。
    """
    if not MIGRATIONS_DIR.is_dir():
        print(f"[upgrade] 迁移脚本目录不存在: {MIGRATIONS_DIR}")
        return []

    pattern = re.compile(r"^from(\d+)to(\d+)\.py$")
    available: dict[tuple[int, int], Path] = {}

    for fpath in MIGRATIONS_DIR.iterdir():
        if not fpath.is_file():
            continue
        m = pattern.match(fpath.name)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if end == start + 1:
                available[(start, end)] = fpath

    # 按起始版本排序
    scripts: list[Path] = []
    for v in range(old_version, new_version):
        key = (v, v + 1)
        if key not in available:
            print(f"[upgrade] 缺少迁移脚本: from{v}to{v+1}.py，跳过")
            continue
        scripts.append(available[key])

    return scripts


def run_script(script: Path) -> None:
    """执行单个迁移脚本。"""
    print(f"[upgrade] 执行 {script.name} ...")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    if result.returncode != 0:
        print(f"[upgrade] {script.name} 失败 (exit={result.returncode})")
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"  ERR: {line}")
        sys.exit(1)


def main():
    print("=" * 48)
    print("  SonettoHere — 配置升级")
    print("=" * 48)
    print()

    # 1. 读取当前版本
    old_version = read_version()
    print(f"[upgrade] 当前版本: {old_version}")

    # 2. git pull
    has_update = git_pull()
    if not has_update:
        sys.exit(0)

    # 3. 读取新版本
    new_version = read_version()
    print(f"[upgrade] 新版本:   {new_version}")

    if new_version <= old_version:
        print("[upgrade] 版本号未变化，无需迁移")
        sys.exit(0)

    # 4. 发现并执行迁移脚本
    scripts = discover_scripts(old_version, new_version)
    if not scripts:
        print(f"[upgrade] 未找到从 v{old_version} 升级所需的迁移脚本")
        sys.exit(0)

    print(f"[upgrade] 计划执行 {len(scripts)} 个迁移脚本: "
          f"v{old_version} → v{new_version}")
    for script in scripts:
        run_script(script)

    # 5. 验证最终版本
    final_version = read_version()
    if final_version == new_version:
        print(f"\n[upgrade] ✅ 升级完成: v{old_version} → v{final_version}")
    else:
        print(f"\n[upgrade] ⚠️  最终版本 ({final_version}) "
              f"与预期 ({new_version}) 不一致")
        sys.exit(1)


if __name__ == "__main__":
    main()
