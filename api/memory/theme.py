"""记忆 V6 语义主题 — 九大固定枚举的唯一权威源。

主题以英文 KEY 作为存储与 API 的权威值（写入 memory_v6.yaml 的 ``theme``
字段），中文标签仅用于提示词与界面展示。本模块只依赖标准库，
不得反向 import 任何 ``api.memory`` 子模块，以免循环依赖。
"""

from enum import Enum


class MemoryTheme(str, Enum):
    """V6 固定九大语义主题。

    每条记忆有且只有一个主题。存储/序列化时一律使用枚举的
    ``value``（英文 KEY）而非 Enum 对象本身。
    """

    USER = "USER"
    PREFERENCE = "PREFERENCE"
    PROJECT = "PROJECT"
    PATH = "PATH"
    LOCATION = "LOCATION"
    TODO = "TODO"
    TECH = "TECH"
    SELF = "SELF"
    MOMENT = "MOMENT"


#: 英文 KEY → 中文标签。字典插入顺序即规范展示顺序，须与 MemoryTheme 一一对应。
THEME_LABELS: dict[str, str] = {
    "USER": "用户档案",
    "PREFERENCE": "用户喜好",
    "PROJECT": "学业与创作产出",
    "PATH": "文件与配置路径",
    "LOCATION": "现实地理地点",
    "TODO": "计划目标承诺",
    "TECH": "技术事实与结论",
    "SELF": "Sonetto与SonettoHere",
    "MOMENT": "事件与经历",
}

#: self_check 遇到空/非法主题时自动修复到的兜底主题。
DEFAULT_THEME: str = "MOMENT"

#: 合法主题集合，作为成员判定的唯一数据源。
VALID_THEMES: frozenset[str] = frozenset(THEME_LABELS)


def is_valid_theme(value: object) -> bool:
    """判断值是否为合法的 V6 主题 KEY。"""
    return isinstance(value, str) and value in THEME_LABELS


def require_theme(value: str, *, who: str = "theme") -> str:
    """校验主题；非法时抛出列出全部合法 KEY 的 ValueError。

    Args:
        value: 待校验的主题值。
        who: 出错时用于定位调用方的标签（如 ``add(theme)``）。

    Returns:
        原样返回合法主题。

    Raises:
        ValueError: 当主题不是九种固定 KEY 之一时。
    """
    if not is_valid_theme(value):
        allowed = "、".join(f"{key}（{label}）" for key, label in THEME_LABELS.items())
        raise ValueError(
            f"{who} 非法主题 {value!r}：V6 仅允许固定九种主题——{allowed}"
        )
    return value


def theme_label(key: str) -> str:
    """返回主题的中文标签；未知键原样回退，避免前端/下游崩溃。"""
    return THEME_LABELS.get(key, key)


def theme_display(key: str) -> str:
    """返回 ``KEY（中文标签）`` 的展示形式；未知键原样回退。"""
    if key in THEME_LABELS:
        return f"{key}（{THEME_LABELS[key]}）"
    return key
