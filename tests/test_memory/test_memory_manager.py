"""memory/memory_manager.py 测试 — YamlMemoryManager 直接测试。"""

import re

import pytest

from api.memory.manager import YamlMemoryManager, MemoryItem
from api.memory.theme import THEME_LABELS


class TestMemoryItem:
    """MemoryItem 单元测试。"""

    def test_init_sets_defaults(self):
        item = MemoryItem("test description", "test theme")
        assert item.description == "test description"
        assert item.theme == "test theme"
        assert item.history == []
        assert item.latest_update_time is not None

    def test_update_description(self):
        item = MemoryItem("old", "theme")
        item.update("信息过时", new_description="new")
        assert item.description == "new"
        assert len(item.history) == 1
        assert item.history[0]["old_description"] == "old"

    def test_update_theme(self):
        item = MemoryItem("desc", "旧主题")
        item.update("重新分类", new_theme="USER")
        assert item.theme == "USER"

    def test_merge_combines_history(self):
        item1 = MemoryItem("A", "USER")
        item2 = MemoryItem("B", "USER")
        item1.merge(item2, "合并", "merged", "USER")
        assert item1.description == "merged"
        # merge → update 产生一条历史记录
        assert len(item1.history) == 1
        assert item1.history[0]["reason"] == "合并"

    def test_show_description_history_order(self):
        item = MemoryItem("initial", "USER")
        item.update("第一次", new_description="second")
        item.update("第二次", new_description="third")
        history = item.show_description_history()
        # 第一项是当前值
        assert history[0]["description"] == "third"
        # 后续是逆序的历史值
        assert history[1]["description"] == "second"
        assert history[2]["description"] == "initial"


class TestYamlMemoryManager:
    """YamlMemoryManager CRUD 测试。"""

    def test_init_creates_yaml_file(self, tmp_path):
        """初始化时创建 yaml 文件。"""
        path = tmp_path / "memory_v6.yaml"
        YamlMemoryManager(yaml_file=str(path))
        assert path.exists()
        # 文件内容应为有效 yaml
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data == {}

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
        # id 是 8 字符十六进制
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

    def test_self_check_repairs_invalid_theme(self, tmp_path):
        """self_check 将非法主题修复为 DEFAULT_THEME（MOMENT）。"""
        import yaml

        path = tmp_path / "memory_v6.yaml"
        raw = {
            "abcd1234": {
                "description": "旧格式记忆",
                "theme": "身份",
                "history": [],
                "hit": 0,
                "latest_update_time": "2026-01-01 00:00:00",
            }
        }
        path.write_text(
            yaml.dump(raw, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        mm = YamlMemoryManager(yaml_file=str(path))
        report = mm.self_check()
        assert report["status"] == "WARN"
        assert mm.show()[0]["theme"] == "MOMENT"

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
        """get_memories_grouped() 按 theme 分组，并附带 theme_label。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        mm.add(description="学生", theme="USER")
        mm.add(description="网络安全", theme="USER")
        mm.add(description="洛天依", theme="PREFERENCE")
        result = mm.get_memories_grouped()
        assert "sections" in result
        sections = result["sections"]
        assert len(sections) == 2
        by_theme = {s["theme"]: s for s in sections}
        assert set(by_theme) == {"USER", "PREFERENCE"}
        assert by_theme["USER"]["theme_label"] == THEME_LABELS["USER"]
        assert by_theme["PREFERENCE"]["theme_label"] == THEME_LABELS["PREFERENCE"]

    def test_memories_grouped_empty(self, tmp_path):
        """空文件时返回空 sections。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        result = mm.get_memories_grouped()
        assert result == {"sections": []}

    def test_description_history(self, tmp_path):
        """show_description_history 返回正确顺序。"""
        path = tmp_path / "memory_v6.yaml"
        mm = YamlMemoryManager(yaml_file=str(path))
        item_id = mm.add(description="初始", theme="USER")
        mm.update(item_id, "第一次更新", new_description="第一次")
        mm.update(item_id, "第二次更新", new_description="第二次")
        history = mm.show_description_history(item_id)
        # 从当前到最早
        assert history[0]["description"] == "第二次"
        assert history[1]["description"] == "第一次"
        assert history[2]["description"] == "初始"
