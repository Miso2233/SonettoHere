#!/usr/bin/env python3
"""SonettoHere — 本地配置自动升级器

工作流程：
  1. 读取已应用的迁移 ID 列表（scripts/migrations/.applied）
  2. git pull 拉取最新代码
  3. 扫描 scripts/migrations/，找出尚未应用的迁移脚本
  4. 按文件名字母序依次执行
  5. 每成功一个，将迁移 ID 追加到 .applied

用法:
  python upgrade.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = PROJECT_ROOT / "scripts" / "migrations"
APPLIED_PATH = MIGRATIONS_DIR / ".applied"


def _read_applied_file() -> list[str] | None:
    """读取 .applied。不存在返回 None。"""
    if not APPLIED_PATH.exists():
        return None
    content = APPLIED_PATH.read_text(encoding="utf-8").strip()
    return content.splitlines() if content else []


def _write_applied_file(values: list[str]) -> None:
    APPLIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPLIED_PATH.write_text("\n".join(values) + "\n", encoding="utf-8")


def read_applied_migrations() -> list[str]:
    """读取已应用的迁移 ID 列表。"""
    return _read_applied_file() or []


def _is_connection_error(stderr: str) -> bool:
    keywords = [
        "Failed to connect", "Could not resolve host", "Connection refused",
        "Network is unreachable", "Unable to access", "Couldn't connect",
        "连接失败", "无法连接", "网络不通",
    ]
    return any(k in stderr for k in keywords)


def _run_git_pull(proxy: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["git", "pull"]
    if proxy:
        cmd = ["git", "-c", f"http.proxy={proxy}", "-c", f"https.proxy={proxy}", "pull"]
    return subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


def git_pull() -> None:
    print("[upgrade] git pull ...")
    result = _run_git_pull()

    if result.returncode != 0 and _is_connection_error(result.stderr):
        print("[upgrade] 连接失败，将通过代理重试。")
        port = input("  代理端口（默认 7890，直接回车使用默认值）: ").strip()
        if not port:
            port = "7890"
        proxy = f"http://127.0.0.1:{port}"
        print(f"[upgrade] 尝试通过代理 {proxy} 拉取 ...")
        result = _run_git_pull(proxy)

    if result.returncode != 0:
        print(f"[upgrade] git pull 失败:\n{result.stderr}")
        sys.exit(1)

    if "Already up to date" in result.stdout.strip():
        print("[upgrade] 已是最新")
    else:
        print("[upgrade] 已拉取更新")


def discover_pending_migrations(applied: list[str]) -> list[Path]:
    if not MIGRATIONS_DIR.is_dir():
        print(f"[upgrade] 迁移脚本目录不存在: {MIGRATIONS_DIR}")
        return []

    pending = []
    for fpath in sorted(MIGRATIONS_DIR.iterdir()):
        if not fpath.is_file() or fpath.suffix != ".py" or fpath.name == "__init__.py":
            continue
        if fpath.stem not in applied:
            pending.append(fpath)
    return pending


def run_script(script: Path) -> None:
    mig_id = script.stem
    print(f"[upgrade] 执行 {script.name} ...")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
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

    applied = _read_applied_file() or []
    applied.append(mig_id)
    _write_applied_file(applied)
    print(f"[upgrade] ✔ {mig_id} 已记录")


def main():
    print("=" * 48)
    print("  SonettoHere — 配置升级")
    print("=" * 48)
    print()

    applied = read_applied_migrations()
    print(f"[upgrade] 已应用 {len(applied)} 个迁移")

    git_pull()

    pending = discover_pending_migrations(applied)
    if not pending:
        print("[upgrade] 无需执行新的迁移")
        sys.exit(0)

    print(f"[upgrade] 发现 {len(pending)} 个待执行迁移:")
    for script in pending:
        print(f"  - {script.name}")

    for script in pending:
        run_script(script)

    print(f"\n[upgrade] ✅ 升级完成")


if __name__ == "__main__":
    main()
