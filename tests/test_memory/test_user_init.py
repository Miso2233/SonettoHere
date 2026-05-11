"""memory/user_init.py 测试。"""

import shutil
from pathlib import Path

import memory.user_init as user_init


class TestEnsureUserMd:
    """ensure_user_md 测试。"""

    def test_creates_user_md_from_example(self, monkeypatch, tmp_path):
        """USER.md 不存在时从 example 复制。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        example = persona_dir / "USER.example.md"
        example.write_text("这是模板内容。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        user_md = persona_dir / "USER.md"
        assert not user_md.exists()

        user_init.ensure_user_md()

        assert user_md.exists()
        assert user_md.read_text(encoding="utf-8") == "这是模板内容。"

    def test_does_not_overwrite_existing(self, monkeypatch, tmp_path):
        """USER.md 已存在时不覆盖。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        example = persona_dir / "USER.example.md"
        example.write_text("模板。", encoding="utf-8")

        user_md = persona_dir / "USER.md"
        user_md.write_text("用户自己写的内容。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        user_init.ensure_user_md()

        # 内容未被覆盖
        assert user_md.read_text(encoding="utf-8") == "用户自己写的内容。"

    def test_no_example_file_does_nothing(self, monkeypatch, tmp_path):
        """example 文件不存在时什么都不做。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        # 不应抛异常
        user_init.ensure_user_md()

        user_md = persona_dir / "USER.md"
        assert not user_md.exists()

    def test_both_exist_does_not_copy(self, monkeypatch, tmp_path):
        """两个文件都存在时不进行复制。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        example = persona_dir / "USER.example.md"
        example.write_text("新模板。", encoding="utf-8")

        user_md = persona_dir / "USER.md"
        user_md.write_text("旧内容。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        user_init.ensure_user_md()

        assert user_md.read_text(encoding="utf-8") == "旧内容。"
