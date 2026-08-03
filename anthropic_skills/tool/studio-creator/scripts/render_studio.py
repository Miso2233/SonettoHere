#!/usr/bin/env python3
"""工作室（studio）YAML 渲染 — 复用 agent.studio.render_studio，输出即注入用 Markdown。

供 Agent 以 Python import 方式调用：
    import sys
    sys.path.insert(0, "<SKILL_DIR>/scripts")
    from render_studio import render_studio_file
    md = render_studio_file("studios/xxx.yaml")   # 渲染失败返回空串

也可命令行：python render_studio.py <studio.yaml>
"""
import sys
from pathlib import Path

# 项目根目录：scripts/ → studio-creator → tool → anthropic_skills → 根，向上五级
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agent.studio import load_studio_file, render_studio  # noqa: E402


def render_studio_file(target: str | Path) -> str:
    """渲染一个 studio YAML 为注入用 Markdown；文件缺失/解析失败返回空串。"""
    data = load_studio_file(Path(target))
    if data is None:
        return ""
    return render_studio(data)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: render_studio.py <studio.yaml>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    if not target.exists():
        print(f"文件不存在: {target}", file=sys.stderr)
        return 2
    md = render_studio_file(target)
    if not md:
        print(f"无法解析 YAML: {target.name}", file=sys.stderr)
        return 1
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
