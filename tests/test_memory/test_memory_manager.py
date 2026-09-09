"""memory/memory_manager.py 测试 — YamlMemoryManager 直接测试。"""

import re

import pytest

from api.memory.manager import MemoryItem, YamlMemoryManager
from api.memory.theme import THEME_LABELS


def _read(path):
    """读取 YAML 文件为 dict（测试辅助）。"""
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestMemoryItem:
    """MemoryItem 单元测试（无 history/hit，含 related）。"""

    def test_init_sets_defaults(self):
        item = MemoryItem("test description", "USER")
        assert item.description == "test description"
        assert item.theme == "USER"
        assert item.related == []
        assert item.latest_update_time is not None
        # history/hit 已彻底移除
        assert not hasattr(item, "history")
        assert not hasattr(item, "hit")

    def test_update_description_no_history(self):
        item = MemoryItem("old", "USER")
        item.update("信息过时", new_description="new")
        assert item.description == "new"
        assert item.theme == "USER"
        assert item.related == []
        assert not hasattr(item, "history")

    def test_update_theme(self):
        item = MemoryItem("desc", "USER")
        item.update("重新分类", new_theme="PROJECT")
        assert item.theme == "PROJECT"
        assert item.description == "desc"

    def test_merge_unions_related_minus_involved(self):
        item1 = MemoryItem("A", "USER", related=["x", "id2", "id2"])
        item2 = MemoryItem("B", "USER", related=["id1", "y", "x"])
        item1.merge(
            item2,
            "合并",
            "merged",
            "USER",
            self_id="id1",
            other_id="id2",
        )
        assert item1.description == "merged"
        assert item1.related == ["x", "y"]
        assert not hasattr(item1, "history")

    def test_add_related_dedupes(self):
        item = MemoryItem("d", "USER")
        item.add_related("aaa")
        item.add_related("aaa")
        item.add_related("bbb")
        assert item.related == ["aaa", "bbb"]

    def test_remove_related(self):
        item = MemoryItem("d", "USER", related=["aaa", "bbb"])
        item.remove_related("aaa")
        assert item.related == ["bbb"]
        item.remove_related("aaa")  # 幂等
        assert item.related == ["bbb"]


class TestYamlMemoryManager:
    """YamlMemoryManager CRUD 测试。"""

    def test_init_creates_yaml_file(self, tmp_path):
        """初始化时创建 yaml 文件。"""
        path = tmp_path / "memory_v6.yaml"
        YamlMemoryManager(yaml_file=str(path))
        assert path.exists()
        assert _read(path) == {}

    def test_init_creates_parent_dir(self, tmp_path):
        """初始化时创建父目录。"""
        path = tmp_path / "subdir" / "memory_v6.yaml"
        YamlMemoryManager(yaml_file=str(path))
        assert path.exists()

    def test_add_returns_id(self, tmp_path):
        """add 返回非空字符串。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        item_id = mm.add(description="测试", theme="USER")
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_add_and_show(self, tmp_path):
        """add 后 show 能查到。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        mm.add(description="测试描述", theme="USER")
        items = mm.show()
        assert len(items) == 1
        assert items[0]["description"] == "测试描述"
        assert items[0]["theme"] == "USER"
        assert re.match(r"^[a-f0-9]{8}$", items[0]["id"])

    def test_add_invalid_theme_raises(self, tmp_path):
        """V6 非九种主题 add → ValueError。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        with pytest.raises(ValueError, match="仅允许"):
            mm.add(description="测试", theme="身份")
        assert mm.show() == []

    def test_delete_removes_item(self, tmp_path):
        """delete 后 show 为空。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        item_id = mm.add(description="待删除", theme="USER")
        mm.delete(item_id)
        assert mm.show() == []

    def test_delete_nonexistent_raises(self, tmp_path):
        """删除不存在的 ID → ValueError。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        with pytest.raises(ValueError, match="not found"):
            mm.delete("nonexistent-id")

    def test_update_changes_description(self, tmp_path):
        """update 后描述变更。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        item_id = mm.add(description="旧描述", theme="USER")
        mm.update(id=item_id, reason="更新", new_description="新描述")
        items = mm.show()
        assert items[0]["description"] == "新描述"

    def test_update_invalid_theme_raises(self, tmp_path):
        """new_theme 非九种主题 → ValueError 且条目不变。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        item_id = mm.add(description="旧描述", theme="USER")
        with pytest.raises(ValueError, match="仅允许"):
            mm.update(id=item_id, reason="重新分类", new_theme="坏主题")
        assert mm.show()[0]["theme"] == "USER"

    def test_update_nonexistent_raises(self, tmp_path):
        """更新不存在的 ID → ValueError。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        with pytest.raises(ValueError, match="not found"):
            mm.update(id="nonexistent-id", reason="测试")

    def test_merge_combines_and_removes(self, tmp_path):
        """merge 合并两个条目，删除第二个。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        id1 = mm.add(description="条目A", theme="USER")
        id2 = mm.add(description="条目B", theme="USER")
        mm.merge(id1, id2, "合并后描述", "USER", "重复")
        items = mm.show()
        assert len(items) == 1
        assert items[0]["id"] == id1
        assert items[0]["description"] == "合并后描述"

    def test_merge_invalid_theme_raises(self, tmp_path):
        """merged_theme 非九种主题 → ValueError 且文件不变。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        id1 = mm.add(description="A", theme="USER")
        id2 = mm.add(description="B", theme="USER")
        with pytest.raises(ValueError, match="仅允许"):
            mm.merge(id1, id2, "合并", "身份", "原因")
        assert len(mm.show()) == 2

    def test_merge_nonexistent_raises(self, tmp_path):
        """合并包含不存在 ID → ValueError。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        id1 = mm.add(description="A", theme="USER")
        with pytest.raises(ValueError, match="not found"):
            mm.merge(id1, "bad-id", "desc", "USER", "原因")

    def test_link_symmetric(self, tmp_path):
        """link 建立双向对称关联并落盘。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        b = mm.add(description="B", theme="PREFERENCE")
        mm.link(a, b)
        data = _read(path)
        assert b in data[a]["related"]
        assert a in data[b]["related"]
        assert data[a]["related"] == data[a]["related"][:1]  # 去重

    def test_link_self_raises(self, tmp_path):
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        with pytest.raises(ValueError, match="itself"):
            mm.link(a, a)

    def test_link_missing_id_raises(self, tmp_path):
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        with pytest.raises(ValueError, match="not found"):
            mm.link(a, "bad-id")

    def test_delete_cleans_dangling_edges(self, tmp_path):
        """删除条目后其余条目的 related 不再悬空。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        b = mm.add(description="B", theme="PREFERENCE")
        c = mm.add(description="C", theme="PREFERENCE")
        mm.link(a, b)
        mm.link(a, c)
        mm.delete(a)
        data = _read(path)
        assert data[b]["related"] == []
        assert data[c]["related"] == []

    def test_merge_remaps_edges(self, tmp_path):
        """merge 后，其余条目中指向 id2 的 related 重定向到 id1。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        b = mm.add(description="B", theme="USER")
        c = mm.add(description="C", theme="PREFERENCE")
        mm.link(a, c)
        mm.link(b, c)
        mm.merge(a, b, "A+B", "USER", "重复")
        data = _read(path)
        assert a in data
        assert b not in data
        assert data[a]["related"] == [c]
        assert data[c]["related"] == [a]

    def test_self_check_repairs_invalid_theme(self, tmp_path):
        """self_check 将非法主题修复为 DEFAULT_THEME（MOMENT），且容忍 history/hit 残留。"""
        import yaml

        path = tmp_path / "memory_v6.yaml"
        raw = {
            "abcd1234": {
                "description": "旧格式记忆",
                "theme": "身份",
                "history": [{"reason": "x", "old_description": "o", "new_description": "n"}],
                "hit": 5,
                "latest_update_time": "2026-01-01 00:00:00",
            }
        }
        path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        mm = YamlMemoryManager(yaml_file=str(path))
        report = mm.self_check()
        assert report["status"] == "WARN"
        assert mm.show()[0]["theme"] == "MOMENT"

    def test_load_ignores_legacy_history_hit_and_rewrites_clean(self, tmp_path):
        """旧 YAML 残留 history/hit 可加载；重写后字段干净且含 related。"""
        import yaml

        path = tmp_path / "memory_v6.yaml"
        raw = {
            "aaaa0001": {
                "description": "旧A",
                "theme": "USER",
                "history": [{"reason": "x", "old_description": "o", "old_time": "t"}],
                "hit": 5,
                "latest_update_time": "2026-01-01 00:00:00",
            }
        }
        path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        mm = YamlMemoryManager(yaml_file=str(path))
        # 能加载且校验 OK（不抛 TypeError）
        report = mm.self_check()
        assert report["status"] == "OK"
        # 全量重写后不再含 history/hit，并带 related
        with mm._write_lock():
            items = mm._load_all()
            mm._save_all(items)
        entry = _read(path)["aaaa0001"]
        assert "history" not in entry
        assert "hit" not in entry
        assert "related" in entry
        assert entry["related"] == []

    def test_self_check_repairs_symmetry(self, tmp_path):
        """self_check 补齐单向 related 为双向对称。"""
        import yaml

        path = tmp_path / "memory_v6.yaml"
        raw = {
            "aaaa0001": {
                "description": "A",
                "theme": "USER",
                "related": ["bbbb0002"],
                "latest_update_time": "2026-01-01 00:00:00",
            },
            "bbbb0002": {
                "description": "B",
                "theme": "PREFERENCE",
                "related": [],
                "latest_update_time": "2026-01-01 00:00:00",
            },
        }
        path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        mm = YamlMemoryManager(yaml_file=str(path))
        report = mm.self_check()
        assert report["status"] == "WARN"
        data = _read(path)
        assert "aaaa0001" in data["bbbb0002"]["related"]

    def test_self_check_ok_on_empty_file(self, tmp_path):
        """空 V6 文件 self_check → OK。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        report = mm.self_check()
        assert report["status"] == "OK"
        assert report["item_count"] == 0


class TestYamlMemoryManagerGrouping:
    """get_memories_grouped 测试。"""

    def test_memories_grouped_by_theme(self, tmp_path):
        """按 theme 分组，并附带 theme_label。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        mm.add(description="学生", theme="USER")
        mm.add(description="网络安全", theme="USER")
        mm.add(description="洛天依", theme="PREFERENCE")
        result = mm.get_memories_grouped()
        sections = result["sections"]
        assert len(sections) == 2
        by_theme = {s["theme"]: s for s in sections}
        assert set(by_theme) == {"USER", "PREFERENCE"}
        assert by_theme["USER"]["theme_label"] == THEME_LABELS["USER"]
        assert by_theme["PREFERENCE"]["theme_label"] == THEME_LABELS["PREFERENCE"]

    def test_memories_grouped_item_shape(self, tmp_path):
        """每项载荷只含 id/description/related/_sort_time。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        a = mm.add(description="A", theme="USER")
        b = mm.add(description="B", theme="USER")
        mm.link(a, b)
        items = mm.get_memories_grouped()["sections"][0]["items"]
        assert set(items[0].keys()) == {"id", "description", "related", "_sort_time"}
        by_id = {it["id"]: it for it in items}
        assert by_id[a]["related"] == [b]
        assert by_id[b]["related"] == [a]

    def test_memories_grouped_empty(self, tmp_path):
        """空文件时返回空 sections。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        result = mm.get_memories_grouped()
        assert result == {"sections": []}
