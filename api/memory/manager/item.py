"""记忆条目的数据模型（MemoryItem）及辅助函数。

MemoryItem 是 BaseMemoryManager 体系中所有后端的统一数据载体，
独立于具体存储介质。后端（YAML、数据库等）的 _load_all / _save_all
均序列化为此类型，实现存储层与业务逻辑的解耦。

字段：description / theme / latest_update_time / related（无向关联 id 列表）。
已移除 history 与 hit（V6.1）。
"""

import datetime


def _now() -> str:
    """返回当前时间的格式化字符串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:
    """单条记忆的数据模型。不依赖具体存储后端。

    ``theme`` 为 V6 九大固定语义主题的英文 KEY（见 api.memory.theme），
    合法性由 BaseMemoryManager 写入时强制校验。

    ``related`` 保存与之关联的其他记忆 id（无向图边，双向对称），
    对称性由 BaseMemoryManager 层保证；本对象只提供幂等的列表操作。
    """

    def __init__(
        self,
        description: str,
        theme: str,
        latest_update_time: str | None = None,
        related: list[str] | None = None,
    ) -> None:
        self.description = description
        self.theme = theme
        self.latest_update_time = latest_update_time if latest_update_time is not None else _now()
        self.related: list[str] = related if related is not None else []

    def update(
        self,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新描述/主题并刷新 latest_update_time。

        Args:
            reason: 更新原因。已不写入任何历史字段，保留仅维持调用签名。
        """
        if new_description is not None:
            self.description = new_description
        if new_theme is not None:
            self.theme = new_theme
        self.latest_update_time = _now()

    def merge(
        self,
        another: "MemoryItem",
        reason: str,
        merged_description: str,
        merged_theme: str,
        *,
        self_id: str,
        other_id: str,
    ) -> None:
        """把另一条记忆并入本条。

        更新内容/主题/时间；``related`` 取两者并集，去掉涉事的两条 id（self_id/other_id）后去重。
        本对象不保存自身 id，故两条涉事 id 必须由调用方（manager）显式传入。

        Args:
            another: 被并入的记忆（随后将被删除）。
            reason: 合并原因。已不写入任何历史字段，保留仅维持调用签名。
            merged_description: 合并后的内容。
            merged_theme: 合并后的主题。
            self_id: 保留条目（self）的记忆 id。
            other_id: 被并入条目的记忆 id。
        """
        seen: set[str] = set()
        merged_related: list[str] = []
        for rid in list(self.related) + list(another.related):
            if rid in (self_id, other_id) or rid in seen:
                continue
            seen.add(rid)
            merged_related.append(rid)
        self.related = merged_related
        self.update(reason, merged_description, merged_theme)

    def add_related(self, other_id: str) -> None:
        """幂等添加关联 id（去重）。对"自引用"的防护由 manager 层负责。"""
        if other_id and other_id not in self.related:
            self.related.append(other_id)

    def remove_related(self, other_id: str) -> None:
        """幂等移除所有指向 other_id 的关联。"""
        self.related = [rid for rid in self.related if rid != other_id]
