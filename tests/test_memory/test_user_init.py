"""memory/user_init.py 测试。"""

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


class TestEnsureSoulMd:
    """ensure_soul_md 测试。"""

    def test_creates_soul_md_from_example(self, monkeypatch, tmp_path):
        """SOUL.md 不存在时从 example 复制。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        example = persona_dir / "SOUL.example.md"
        example.write_text("人设模板内容。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        soul_md = persona_dir / "SOUL.md"
        assert not soul_md.exists()

        user_init.ensure_soul_md()

        assert soul_md.exists()
        assert soul_md.read_text(encoding="utf-8") == "人设模板内容。"

    def test_soul_md_not_overwritten(self, monkeypatch, tmp_path):
        """SOUL.md 已存在时不覆盖。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        example = persona_dir / "SOUL.example.md"
        example.write_text("新模板。", encoding="utf-8")

        soul_md = persona_dir / "SOUL.md"
        soul_md.write_text("用户自定义人设。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        user_init.ensure_soul_md()

        assert soul_md.read_text(encoding="utf-8") == "用户自定义人设。"

    def test_soul_no_example_does_nothing(self, monkeypatch, tmp_path):
        """example 文件不存在时什么都不做。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)

        user_init.ensure_soul_md()

        soul_md = persona_dir / "SOUL.md"
        assert not soul_md.exists()


class TestEnsureEnvFile:
    """ensure_env_file 测试。"""

    def test_creates_env_from_example(self, monkeypatch, tmp_path):
        """.env 不存在时从 example 复制。"""
        project_root = tmp_path
        example = project_root / ".env.example"
        example.write_text("API_KEY=test", encoding="utf-8")

        monkeypatch.setattr(user_init, "PROJECT_ROOT", project_root)

        env_file = project_root / ".env"
        assert not env_file.exists()

        user_init.ensure_env_file()

        assert env_file.exists()
        assert env_file.read_text(encoding="utf-8") == "API_KEY=test"

    def test_env_not_overwritten(self, monkeypatch, tmp_path):
        """.env 已存在时不覆盖。"""
        project_root = tmp_path
        example = project_root / ".env.example"
        example.write_text("新内容。", encoding="utf-8")

        env_file = project_root / ".env"
        env_file.write_text("用户已有的配置。", encoding="utf-8")

        monkeypatch.setattr(user_init, "PROJECT_ROOT", project_root)

        user_init.ensure_env_file()

        assert env_file.read_text(encoding="utf-8") == "用户已有的配置。"

    def test_env_no_example_does_nothing(self, monkeypatch, tmp_path):
        """example 文件不存在时什么都不做。"""
        project_root = tmp_path
        monkeypatch.setattr(user_init, "PROJECT_ROOT", project_root)

        user_init.ensure_env_file()

        env_file = project_root / ".env"
        assert not env_file.exists()


class TestEnsureAll:
    """ensure_all 集成测试。"""

    def test_ensure_all_calls_all_three(self, monkeypatch, tmp_path):
        """ensure_all 依次调用三个 ensure 函数。"""
        persona_dir = tmp_path / "personas"
        persona_dir.mkdir(parents=True)
        project_root = tmp_path

        # 准备所有 example 文件
        (persona_dir / "USER.example.md").write_text("user", encoding="utf-8")
        (persona_dir / "SOUL.example.md").write_text("soul", encoding="utf-8")
        (project_root / ".env.example").write_text("env", encoding="utf-8")

        monkeypatch.setattr(user_init, "PERSONAS_DIR", persona_dir)
        monkeypatch.setattr(user_init, "PROJECT_ROOT", project_root)

        user_init.ensure_all()

        # 三个目标文件都应被创建
        assert (persona_dir / "USER.md").exists()
        assert (persona_dir / "SOUL.md").exists()
        assert (project_root / ".env").exists()
