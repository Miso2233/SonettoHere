"""记忆管理器抽象基类 — 基于三个原语的泛化 CRUD 框架。

所有记忆存储后端均应继承 BaseMemoryManager，
仅需实现 _load_all / _save_all / _write_lock 三个抽象原语，
即可免费获得完整的 CRUD、字段校验和查询方法。
"""

import datetime
import secrets
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, TypedDict

from api.memory.manager.item import MemoryItem
from api.memory.theme import DEFAULT_THEME, THEME_LABELS, is_valid_theme, require_theme, theme_label


class SelfCheckReport(TypedDict):
    """``self_check()`` 的返回类型。"""

    status: str
    """``"OK"`` | ``"WARN"`` | ``"FAIL"``"""
    issues: list[str]
    """不可自动修复的问题列表。"""
    repaired: list[str]
    """已自动修复的问题描述列表。"""
    item_count: int
    """有效条目总数。"""


class BaseMemoryManager(ABC):
    """记忆管理器抽象接口 — 基于三个原语的泛化 CRUD 框架。

    所有记忆存储后端（YAML、数据库等）均应继承此类。

    ## 子类需实现的最小原语集

    必须实现以下三个抽象方法，即可免费获得完整的 CRUD、字段校验和查询能力：

    - ``_load_all() -> dict[str, MemoryItem]`` — **全量读取**。返回当前所有条目的 ID→对象映射。
      默认 CRUD 的每次写操作都会调用此方法获取最新快照。

    - ``_save_all(items) -> None`` — **全量覆写**。将整个条目字典持久化到后端。
      YAML 后端使用 ``yaml.dump`` 写整个文件；数据库后端可保存单个快照表。

    - ``_write_lock() -> AbstractContextManager[None]`` — **写操作锁上下文**。
      所有 CRUD 方法在锁内执行 ``_load_all → 修改 → _save_all`` 序列。
      YAML 后端以 ``portalocker.Lock`` 实现；数据库后端可使用事务。

    ## 覆写 CRUD 以获得超越全量更新的性能

    默认 CRUD 的模式是「加锁 → **_load_all 全量加载** → 修改 → **_save_all 全量覆写」。
    这对 YAML 等文件后端合理，但对支持定点读写的后端（SQL、Redis 等）效率低下。
    子类可直接覆写 CRUD 方法，利用后端的原生操作避免全量读写：

    .. code-block:: python

        class DbManager(BaseMemoryManager):
            def update(self, id, reason, new_description=None, new_theme=None):
                with self._write_lock():
                    item = self._db.fetch_one(id)    # 定点读取
                    item.update(reason, ...)
                    self._db.update_one(id, item)     # 定点写入
                    # 无需 _load_all / _save_all

    注意：即使覆写了部分 CRUD，仍建议通过 ``_write_lock`` 保持并发语义一致性。

    ## 基类提供的默认工具方法

    ===  ================================
    类别  方法                               说明
    ===  ================================
    查询  ``show()``                        返回 ``[{id, description, theme}]`` 列表
    查询  ``get_memories_grouped()``        按 theme 分组，供前端瀑布流展示
    ID    ``_generate_id()``                默认 `secrets.token_hex(4)`，子类可覆写
    校验  ``_validate_all_items(items)``    校验/修复字段与 related 对称性，返回 (issues, repaired)
    CRUD  ``add(description, theme)``       添加条目
    CRUD  ``delete(id)``                    删除条目并清理他人 related 中的悬空引用
    CRUD  ``update(id, reason, ...)``       更新条目（可改描述和/或主题）
    CRUD  ``merge(id1, id2, ...)``          合并两条记忆（related 并集，id2 删除并重定向引用）
    CRUD  ``link(id1, id2)``                在两条记忆间建立双向（对称）关联
    ===  ================================
    """

    # ── 抽象存储原语 ────────────────────────────────────────

    @abstractmethod
    def _load_all(self) -> dict[str, MemoryItem]:
        """读取全部条目。子类须自行保证并发安全。"""
        ...

    @abstractmethod
    def _save_all(self, items: dict[str, MemoryItem]) -> None:
        """覆写全部条目。子类须自行保证并发安全。"""
        ...

    @abstractmethod
    def _write_lock(self) -> AbstractContextManager[None]:
        """写操作的锁上下文。子类必须覆盖以实现并发控制。"""
        ...

    # ── 启动自检 ────────────────────────────────────────────

    @abstractmethod
    def self_check(self) -> SelfCheckReport:
        """启动自检，验证存储后端状态正常。

        子类应检查：
        - 后端存储介质是否可达、可读写
        - 所有数据条目字段是否完整（description / theme / latest_update_time / related）
        - related 关联是否双向对称、是否存在悬空引用
        - 必要时自动修复可修复的问题（如空字符串、类型异常）

        Returns:
            SelfCheckReport 包含 status（"OK" / "WARN" / "FAIL"）、
            issues（不可修复问题）、repaired（已修复问题）、item_count（有效条目数）。
        """
        ...

    def _validate_all_items(
        self, items: dict[str, MemoryItem]
    ) -> tuple[list[str], list[str]]:
        """校验所有条目的字段完整性并修复 related 对称性，返回 (issues, repaired)。

        介质无关，子类的 self_check 可直接调用此方法以复用校验逻辑。
        校验范围：description/theme/latest_update_time 的类型与空值；
        related 仅保留本库中存在、非自引用的 str 且去重；
        最后补全双向对称（a.related 含 b ⇒ b.related 也含 a）。
        """
        issues: list[str] = []
        repaired: list[str] = []
        for id, item in items.items():
            if not isinstance(item.description, str) or not item.description.strip():
                item.description = "(空)"
                repaired.append(f"条目 {id}: description 为空，已重置")

            if (
                not isinstance(item.theme, str)
                or not item.theme.strip()
                or not is_valid_theme(item.theme)
            ):
                item.theme = DEFAULT_THEME
                repaired.append(
                    f"条目 {id}: theme 为空或非法（V6 仅允许固定九种主题），"
                    f"已重置为 {DEFAULT_THEME}（{THEME_LABELS[DEFAULT_THEME]}）"
                )

            if (
                not isinstance(item.latest_update_time, str)
                or not item.latest_update_time.strip()
            ):
                item.latest_update_time = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                repaired.append(f"条目 {id}: latest_update_time 无效，已重置")

            if not isinstance(item.related, list):
                item.related = []
                repaired.append(f"条目 {id}: related 非列表，已重置为 []")
                continue

            # 清理 related：仅保留本库中存在、非自引用的 str，并去重
            cleaned: list[str] = []
            seen: set[str] = set()
            for rid in item.related:
                if (
                    not isinstance(rid, str)
                    or rid == id
                    or rid not in items
                    or rid in seen
                ):
                    continue
                seen.add(rid)
                cleaned.append(rid)
            if len(cleaned) != len(item.related):
                item.related = cleaned
                repaired.append(
                    f"条目 {id}: related 含非字符串/自引用/悬空/重复项，已清理"
                )

        # 对称性补齐：a.related 含 b ⇒ b.related 必须含 a
        for id, item in items.items():
            for rid in item.related:
                if rid in items and id not in items[rid].related:
                    items[rid].add_related(id)
                    repaired.append(f"条目 {rid}: 缺少与 {id} 的双向关联，已补全")

        return issues, repaired

    # ── 默认 ID 生成 ────────────────────────────────────────

    def _generate_id(self) -> str:
        """生成唯一短 ID。子类可 override。"""
        return secrets.token_hex(4)

    # ── 公共查询方法（基于 _load_all） ───────────────────────

    def show(self) -> list[dict[str, Any]]:
        """返回所有记忆条目（大模型友好格式）。"""
        items = self._load_all()
        return [
            {"id": id, "description": item.description, "theme": item.theme}
            for id, item in items.items()
        ]

    def get_memories_grouped(self) -> dict[str, Any]:
        """按 theme 分组返回记忆数据，用于 Vignette 前端瀑布流展示。"""
        items = self._load_all()
        groups: dict[str, list[dict]] = {}
        for id, item in items.items():
            theme = item.theme
            if theme not in groups:
                groups[theme] = []
            groups[theme].append(
                {
                    "id": id,
                    "description": item.description,
                    "related": item.related,
                    "_sort_time": item.latest_update_time,
                }
            )
        # 每组内按更新时间倒序
        for theme in groups:
            groups[theme].sort(key=lambda x: x["_sort_time"], reverse=True)
        # 分区间按条目数降序
        sections = [
            {"theme": theme, "theme_label": theme_label(theme), "items": items}
            for theme, items in sorted(
                groups.items(), key=lambda x: len(x[1]), reverse=True
            )
        ]
        return {"sections": sections}

    # ── CRUD 方法（基于 _load_all / _save_all / _write_lock） ──

    def add(
        self,
        description: str,
        theme: str,
        related: list[str] | None = None,
    ) -> str:
        """添加一条新的记忆条目。

        可通过 ``related`` 传入若干**已存在**的记忆 id，在建条目的同一
        写事务内建立双向关联：新条目 related 记录这些 id，同时把新 id
        追加到每个目标条目的 related（对称、去重）。

        Args:
            description: 记忆内容。
            theme: V6 固定主题 KEY。
            related: 待关联的已存在记忆 id 列表；任一不存在则整次拒绝。

        Raises:
            ValueError: theme 非法，或 related 含不存在的 id。
        """
        theme = require_theme(theme, who="add(theme)")
        related = list(dict.fromkeys(related)) if related else []
        with self._write_lock():
            items = self._load_all()
            missing = [rid for rid in related if rid not in items]
            if missing:
                raise ValueError(
                    f"add(related) 含不存在的记忆 id: {missing}，请先确认这些记忆已存在"
                )
            new_id = self._generate_id()
            item = MemoryItem(description, theme)
            item.related = list(related)
            for rid in related:
                items[rid].add_related(new_id)
            items[new_id] = item
            self._save_all(items)
        return new_id

    def delete(self, id: str) -> str:
        """删除指定 ID 的记忆条目，返回被删除条目的描述。

        同时清理其余条目 related 中指向该 id 的悬空引用。
        """
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            removed = items.pop(id)
            for oitem in items.values():
                oitem.remove_related(id)
            self._save_all(items)
        return removed.description

    def merge(
        self,
        id1: str,
        id2: str,
        merged_description: str,
        merged_theme: str,
        reason: str,
    ) -> None:
        """将两条记忆合并为一条，id1 保留，id2 被删除。

        Raises:
            ValueError: merged_theme 不是 V6 九种固定主题之一时。
        """
        merged_theme = require_theme(merged_theme, who="merge(merged_theme)")
        with self._write_lock():
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(
                    f"Memory items with IDs {id1} and {id2} not found"
                )
            items[id1].merge(
                items[id2],
                reason,
                merged_description,
                merged_theme,
                self_id=id1,
                other_id=id2,
            )
            items.pop(id2)
            # 其余条目中指向 id2 的 related 重定向到 id1，并去重
            for oid, oitem in items.items():
                if oid == id1:
                    continue
                nxt: list[str] = []
                changed = False
                for rid in oitem.related:
                    if rid == id2:
                        changed = True
                        if id1 not in nxt:
                            nxt.append(id1)
                    else:
                        nxt.append(rid)
                if changed:
                    oitem.related = nxt
            self._save_all(items)

    def update(
        self,
        id: str,
        reason: str,
        new_description: str | None = None,
        new_theme: str | None = None,
    ) -> None:
        """更新指定记忆条目的内容和/或主题。

        Raises:
            ValueError: 传入的 new_theme 不是 V6 九种固定主题之一时。
        """
        if new_theme is not None:
            new_theme = require_theme(new_theme, who="update(new_theme)")
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._save_all(items)

    def link(self, id1: str, id2: str) -> None:
        """在两条记忆之间建立双向 related 关联（对称、去重）。

        Raises:
            ValueError: 两条 id 相同或任一不存在时。
        """
        if id1 == id2:
            raise ValueError("Cannot link a memory to itself")
        with self._write_lock():
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(
                    f"Memory items with IDs {id1} and {id2} not found"
                )
            items[id1].add_related(id2)
            items[id2].add_related(id1)
            self._save_all(items)
