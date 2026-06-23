"""memory/memory_manager.py 测试 — MemoryManager 直接测试。"""

import re

import pytest

from memory.memory_manager import MemoryManager, MemoryItem


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
        item.update("重新分类", new_theme="新主题")
        assert item.theme == "新主题"

    def test_merge_combines_history(self):
        item1 = MemoryItem("A", "主题")
        item2 = MemoryItem("B", "主题")
        item1.merge(item2, "合并", "merged", "主题")
        assert item1.description == "merged"
        # merge → update 产生一条历史记录
        assert len(item1.history) == 1
        assert item1.history[0]["reason"] == "合并"

    def test_show_description_history_order(self):
        item = MemoryItem("initial", "theme")
        item.update("第一次", new_description="second")
        item.update("第二次", new_description="third")
        history = item.show_description_history()
        # 第一项是当前值
        assert history[0]["description"] == "third"
        # 后续是逆序的历史值
        assert history[1]["description"] == "second"
        assert history[2]["description"] == "initial"


class TestMemoryManager:
    """MemoryManager CRUD 测试。"""

    def test_init_creates_yaml_file(self, tmp_path):
        """初始化时创建 yaml 文件。"""
        path = tmp_path / "test_memory.yaml"
        MemoryManager(yaml_file=str(path))
        assert path.exists()
        # 文件内容应为有效 yaml
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data == {}

    def test_init_creates_parent_dir(self, tmp_path):
        """初始化时创建父目录。"""
        path = tmp_path / "subdir" / "memory.yaml"
        MemoryManager(yaml_file=str(path))
        assert path.exists()

    def test_add_returns_id(self, tmp_path):
        """add 返回非空字符串。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        item_id = mm.add(description="测试", theme="身份")
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_add_and_show(self, tmp_path):
        """add 后 show 能查到。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        mm.add(description="测试描述", theme="测试主题")
        items = mm.show()
        assert len(items) == 1
        assert items[0]["description"] == "测试描述"
        assert items[0]["theme"] == "测试主题"
        # id 是 8 字符十六进制
        assert re.match(r"^[a-f0-9]{8}$", items[0]["id"])

    def test_delete_removes_item(self, tmp_path):
        """delete 后 show 为空。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        item_id = mm.add(description="待删除", theme="身份")
        mm.delete(item_id)
        assert mm.show() == []

    def test_delete_nonexistent_raises(self, tmp_path):
        """删除不存在的 ID → ValueError。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        with pytest.raises(ValueError, match="not found"):
            mm.delete("nonexistent-id")

    def test_update_changes_description(self, tmp_path):
        """update 后描述变更。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        item_id = mm.add(description="旧描述", theme="身份")
        mm.update(id=item_id, reason="更新", new_description="新描述")
        items = mm.show()
        assert items[0]["description"] == "新描述"

    def test_update_nonexistent_raises(self, tmp_path):
        """更新不存在的 ID → ValueError。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        with pytest.raises(ValueError, match="not found"):
            mm.update(id="nonexistent-id", reason="测试")

    def test_merge_combines_and_removes(self, tmp_path):
        """merge 合并两个条目，删除第二个。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        id1 = mm.add(description="条目A", theme="身份")
        id2 = mm.add(description="条目B", theme="身份")
        mm.merge(id1, id2, "合并后描述", "身份", "重复")
        items = mm.show()
        assert len(items) == 1
        assert items[0]["id"] == id1
        assert items[0]["description"] == "合并后描述"

    def test_merge_nonexistent_raises(self, tmp_path):
        """合并包含不存在 ID → ValueError。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        id1 = mm.add(description="A", theme="身份")
        with pytest.raises(ValueError, match="not found"):
            mm.merge(id1, "bad-id", "desc", "主题", "原因")


class TestMemoryManagerGrouping:
    """get_memories_grouped 测试。"""

    def test_memories_grouped_by_theme(self, tmp_path):
        """get_memories_grouped() 按 theme 分组。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        mm.add(description="学生", theme="身份")
        mm.add(description="网络安全", theme="身份")
        mm.add(description="洛天依", theme="音乐")
        result = mm.get_memories_grouped()
        assert "sections" in result
        sections = result["sections"]
        assert len(sections) == 2
        theme_names = [s["theme"] for s in sections]
        assert "身份" in theme_names
        assert "音乐" in theme_names

    def test_memories_grouped_empty(self, tmp_path):
        """空文件时返回空 sections。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        result = mm.get_memories_grouped()
        assert result == {"sections": []}

    def test_description_history(self, tmp_path):
        """show_description_history 返回正确顺序。"""
        path = tmp_path / "memory.yaml"
        mm = MemoryManager(yaml_file=str(path))
        item_id = mm.add(description="初始", theme="身份")
        mm.update(item_id, "第一次更新", new_description="第一次")
        mm.update(item_id, "第二次更新", new_description="第二次")
        history = mm.show_description_history(item_id)
        # 从当前到最早
        assert history[0]["description"] == "第二次"
        assert history[1]["description"] == "第一次"
        assert history[2]["description"] == "初始"
