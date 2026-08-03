"""工作坊（Studio）渲染器与加载器测试。"""

import yaml
from pathlib import Path

import pytest

from agent.prompts import get_system_prompt_parts
from agent.studio import (
    _get_path,
    _render_field,
    load_all_studios,
    load_studio_file,
    render_studio,
    render_studio_by_name,
    StudioFieldSpec,
)
from api.agent.context_usage import estimate_context_usage_from_session
from api.session.manager import SessionState


def _sample_data() -> dict:
    return {
        "name": "测试工坊",
        "description": "一个测试工坊",
        "role": "测试角色",
        "main_folder": [
            {"path": "C:\\vault", "note": "根目录"},
        ],
        "additional_folders": [
            {"path": "C:\\归档", "note": ""},
        ],
        "tools": ["file_read", "file_write"],
        "macros": ["宏一", "宏二"],
        "skills": ["技能甲"],
        "meta": {"version": "0.1.0", "author": "tester"},
        "body": {
            "structure": "vault/\n  └── note.md",
            "workflow": ["先浏览", "再执行"],
            "rules": ["规则一", "规则二"],
            "notes": ["备注一"],
        },
    }


def test_get_path_nested():
    assert _get_path(_sample_data(), "body.workflow") == ["先浏览", "再执行"]
    assert _get_path(_sample_data(), "body.missing") is None
    assert _get_path(_sample_data(), "tools") == ["file_read", "file_write"]


def test_render_studio_kinds():
    text = render_studio(_sample_data())
    assert text.startswith("## 工作坊：测试工坊")
    assert "## 简介\n一个测试工坊" in text
    assert "## 角色定位\n测试角色" in text
    assert "## 主要文件夹\n你只可以对此文件夹进行写操作。\n\n- C:\\vault\n  （根目录）" in text
    assert "## 参考文件夹\n你可以可选地从以下文件夹读取更多信息\n\n- C:\\归档" in text  # 无附注时不带括号
    assert "## 推荐工具\n推荐关注以下工具进行工作\n\nfile_read、file_write" in text
    assert "## 推荐宏\n推荐关注以下宏进行工作\n\n宏一、宏二" in text
    assert "## 推荐技能\n推荐关注以下技能进行工作\n\n技能甲" in text
    assert "## 元信息\n- version: 0.1.0" in text
    assert "## 目录结构\n```\nvault/" in text
    assert "## 工作流程\n- 先浏览\n- 再执行" in text
    assert "## 工作规则\n- 规则一\n- 规则二" in text
    assert "## 注意事项\n- 备注一" in text


def test_render_field_description():
    """description 渲染在标题之后、内容之前；为空时保持原有格式。"""
    with_desc = StudioFieldSpec(key="role", label="角色定位", kind="text",
                                description="这是该字段的说明文本")
    assert _render_field(with_desc, "测试角色") == "## 角色定位\n这是该字段的说明文本\n\n测试角色"

    no_desc = StudioFieldSpec(key="role", label="角色定位", kind="text")
    assert _render_field(no_desc, "测试角色") == "## 角色定位\n测试角色"


def test_render_field_empty_placeholder():
    """字段缺失或为空时渲染（无）占位；empty_text 为空串则整段跳过。"""
    spec = StudioFieldSpec(key="folders", label="文件夹", kind="list",
                           item_key="path", item_note="note")
    # 字段缺失
    assert _render_field(spec, None) == "## 文件夹\n（无）"
    # 列表字段为空
    assert _render_field(spec, []) == "## 文件夹\n（无）"
    # empty_text 置空 → 跳过
    skip = StudioFieldSpec(key="x", label="X", kind="text", empty_text="")
    assert _render_field(skip, None) == ""
    # 自定义占位文案
    custom = StudioFieldSpec(key="x", label="X", kind="text", empty_text="暂无")
    assert _render_field(custom, None) == "## X\n暂无"


def test_render_studio_empty():
    # 无任何字段时，各 spec 段落渲染（无）占位而非跳过
    text = render_studio({})
    assert "## 工作坊：未命名" in text
    assert "## 简介\n（无）" in text
    assert "## 主要文件夹\n（无）" in text


def test_load_studio_file(tmp_path: Path):
    good = tmp_path / "good.yaml"
    good.write_text("name: ok\n", encoding="utf-8")
    assert load_studio_file(good) == {"name": "ok"}

    bad = tmp_path / "bad.yaml"
    bad.write_text(": : :", encoding="utf-8")  # 损坏
    assert load_studio_file(bad) is None

    missing = tmp_path / "nope.yaml"
    assert load_studio_file(missing) is None

    list_root = tmp_path / "list.yaml"
    list_root.write_text("- a\n- b\n", encoding="utf-8")
    assert load_studio_file(list_root) is None  # 根非 dict


def _write_fixture(tmp_path: Path) -> Path:
    """在 tmp_path 下写入一个合法 studio 夹具目录，返回该目录。"""
    d = tmp_path / "studios"
    d.mkdir()
    (d / "obsidian-km-workshop.yaml").write_text(
        yaml.safe_dump(_sample_data(), allow_unicode=True), encoding="utf-8"
    )
    return d


def test_load_all_studios(monkeypatch, tmp_path: Path):
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    studios = load_all_studios()
    assert len(studios) == 1
    assert studios[0].name == "测试工坊"
    assert studios[0].description == "一个测试工坊"


def test_render_studio_by_name(monkeypatch, tmp_path: Path):
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    assert "## 工作坊：测试工坊" in render_studio_by_name("测试工坊")
    assert render_studio_by_name("不存在的工坊") == ""
    assert render_studio_by_name("") == ""
    assert render_studio_by_name(None) == ""


def test_get_system_prompt_parts_studio(monkeypatch, tmp_path: Path):
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)

    parts = get_system_prompt_parts("测试工坊")
    studio_parts = [p for p in parts if p["key"] == "studio"]
    assert len(studio_parts) == 1
    assert "## 工作坊：测试工坊" in studio_parts[0]["content"]

    # 默认（未选中）不注入 studio 段
    assert all(p["key"] != "studio" for p in get_system_prompt_parts())


@pytest.mark.asyncio
async def test_estimate_context_usage_breakdown_includes_studio(monkeypatch, tmp_path: Path):
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)

    session = SessionState(session_id="usage-sid")
    result = await estimate_context_usage_from_session(
        session, "system prompt", max_tokens=1000, model_name="test", studio_name="测试工坊"
    )
    parts = result["breakdown"]["system_prompt"]["parts"]
    keys = [p["key"] for p in parts]
    assert "studio" in keys
