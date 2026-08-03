#!/usr/bin/env python3
"""工作室（studio）YAML 校验 — 用 yamale 固定字段与类型。

供 Agent 以 Python import 方式调用：
    import sys
    sys.path.insert(0, "<SKILL_DIR>/scripts")
    from validate_studio import validate_studio_file
    errors = validate_studio_file("studios/xxx.yaml")   # [] = 通过，非空 = 错误列表

也可命令行：python validate_studio.py <studio.yaml>
"""
import sys
from pathlib import Path

import yaml
import yamale

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "references" / "studio_schema.yaml"
)

# 管理页会把空列表/空映射存为 null，校验前规范化为空容器
_LIST_FIELDS = ("main_folder", "additional_folders", "tools", "macros", "skills")
_MAP_FIELDS = ("meta", "body")


def _normalize(data: dict) -> dict:
    for key in _LIST_FIELDS:
        if data.get(key) is None:
            data[key] = []
    for key in _MAP_FIELDS:
        if data.get(key) is None:
            data[key] = {}
    return data


def validate_studio_file(target: str | Path) -> list[str]:
    """校验一个 studio YAML；返回错误消息列表，空列表 = 通过。"""
    path = Path(target)
    if not path.exists():
        return [f"文件不存在: {path}"]
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return [f"YAML 解析失败: {exc}"]
    if not isinstance(raw, dict):
        return ["根节点必须为 YAML 映射（dict）"]

    schema = yamale.make_schema(SCHEMA_PATH)
    try:
        yamale.validate(schema, [(_normalize(raw), str(path))])
    except yamale.YamaleError as exc:
        errors: list[str] = []
        for result in exc.results:
            for err in result.errors:
                errors.append(str(err))
        return errors
    return []


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: validate_studio.py <studio.yaml>", file=sys.stderr)
        return 2
    name = Path(sys.argv[1]).name
    errors = validate_studio_file(sys.argv[1])
    if errors:
        print(f"校验失败: {name}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✓ {name} 通过校验（{SCHEMA_PATH.name}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
