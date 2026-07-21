"""记忆条目的数据模型（MemoryItem）及辅助函数。

MemoryItem 是 BaseMemoryManager 体系中所有后端的统一数据载体，
独立于具体存储介质。后端（YAML、数据库等）的 _load_all / _save_all
均序列化为此类型，实现存储层与业务逻辑的解耦。
"""

import datetime


def _now() -> str:
    """返回当前时间的格式化字符串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryItem:
    """单条记忆的数据模型。不依赖具体存储后端。

    每个 MemoryItem 实例代表一条独立的记忆条目，包含描述内容、
    分类主题、变更历史以及引用计数。通过其 update / merge 方法
    记录每次变更的完整轨迹，供 show_description_history() 追溯。
    """

    def __init__(
        self,
        description: str,
        theme: str,
        history: list[dict[str, str]] | None = None,
        latest_update_time: str | None = None,
        hit: int = 0,
    ) -> None:
        self.description = description
        self.theme = theme
        self.history = history if history is not None else []
        self.latest_update_time = latest_update_time if latest_update_time is not None else _now()
        self.hit = hit

    def update(
        self,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新记忆内容并记录历史。"""
        new_history: dict[str, str] = {"reason": reason}
        if new_description is not None:
            new_history["new_description"] = new_description
            new_history["old_description"] = self.description
            self.description = new_description
        if new_theme is not None:
            new_history["new_theme"] = new_theme
            new_history["old_theme"] = self.theme
            self.theme = new_theme
        new_history["old_time"] = self.latest_update_time
        self.latest_update_time = _now()
        self.history.append(new_history)

    def show_description_history(self) -> list[dict[str, str]]:
        """返回描述变更历史（从当前到最早）。"""
        result: list[dict[str, str]] = [
            {"description": self.description, "time": self.latest_update_time}
        ]
        for entry in reversed(self.history):
            if "old_description" in entry:
                result.append(
                    {
                        "description": entry["old_description"],
                        "time": entry["old_time"],
                    }
                )
        return result

    def merge(
        self,
        another: "MemoryItem",
        reason: str,
        merged_description: str,
        merged_theme: str,
    ) -> None:
        """合并另一条记忆的历史到本条。"""
        self.history += another.history
        self.hit = max(self.hit, another.hit)
        self.update(reason, merged_description, merged_theme)
