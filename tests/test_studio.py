"""工作坊（Studio）渲染器与加载器测试。"""

import yaml
from pathlib import Path

import pytest

from agent.prompts import get_system_prompt_parts
from agent.studio import (
    _get_path,
    _render_field,
    _sanitize_filename,
    create_studio,
    delete_studio,
    get_studio,
    load_all_studios,
    load_studio_file,
    render_studio,
    render_studio_by_name,
    StudioFieldSpec,
    studio_schema,
    update_studio,
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
    assert studios[0].filename == "obsidian-km-workshop.yaml"


def test_studio_schema_shape():
    fields = studio_schema()
    assert isinstance(fields, list)
    assert len(fields) == len((
        "description", "role", "main_folder", "additional_folders", "tools",
        "macros", "skills", "meta", "body.structure", "body.workflow",
        "body.rules", "body.notes",
    ))
    kinds = {"text", "code", "list", "keyval", "join"}
    for f in fields:
        assert set(f) >= {"key", "label", "kind"}
        assert f["kind"] in kinds
    # 点路径字段（body.*）
    assert any(f["key"] == "body.structure" for f in fields)


def test_sanitize_filename():
    assert _sanitize_filename("本地 Obsidian 知识管理工作坊") == "本地 Obsidian 知识管理工作坊"
    assert _sanitize_filename('a<b>:"c/d\\e|f?g*h') == "abcdefgh"
    assert _sanitize_filename("  abc  ") == "abc"
    assert _sanitize_filename("abc...") == "abc"
    assert _sanitize_filename("") == ""
    assert _sanitize_filename(":::") == ""


def test_get_studio_by_name_and_stem(monkeypatch, tmp_path: Path):
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    # 按 name 命中
    data = get_studio("测试工坊")
    assert data is not None and data["name"] == "测试工坊"
    # 按文件名 stem 回退命中（obsidian-km-workshop）
    data = get_studio("obsidian-km-workshop")
    assert data is not None and data["name"] == "测试工坊"
    assert get_studio("不存在") is None


def test_create_studio(monkeypatch, tmp_path: Path):
    d = tmp_path / "studios"
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    info = create_studio({"name": "  新建工坊  ", "description": "描述"})
    assert info.name == "新建工坊"
    assert info.filename == "新建工坊.yaml"
    assert (d / "新建工坊.yaml").exists()
    # 重复创建抛 ValueError
    with pytest.raises(ValueError):
        create_studio({"name": "新建工坊"})
    # 非法名抛 ValueError
    with pytest.raises(ValueError):
        create_studio({"name": ""})
    with pytest.raises(ValueError):
        create_studio({"name": ":::"})


def test_update_studio_rewrite_and_rename(monkeypatch, tmp_path: Path):
    d = tmp_path / "studios"
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    create_studio({"name": "旧名", "description": "旧描述"})

    # 仅改内容，不改名 → 原文件重写
    info = update_studio("旧名", {"name": "旧名", "description": "新描述"})
    assert info.filename == "旧名.yaml"
    assert get_studio("旧名")["description"] == "新描述"

    # 改名 → 文件重命名
    info = update_studio("旧名", {"name": "新名", "description": "描述"})
    assert info.filename == "新名.yaml"
    assert (d / "新名.yaml").exists()
    assert not (d / "旧名.yaml").exists()
    assert get_studio("新名")["name"] == "新名"

    # 不存在的工坊 → ValueError
    with pytest.raises(ValueError):
        update_studio("不存在", {"name": "其他"})
    # 新名与他人冲突 → ValueError
    create_studio({"name": "他人"})
    with pytest.raises(ValueError):
        update_studio("新名", {"name": "他人"})


def test_delete_studio(monkeypatch, tmp_path: Path):
    d = tmp_path / "studios"
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    create_studio({"name": "要删的"})
    assert delete_studio("要删的") is True
    assert not (d / "要删的.yaml").exists()
    assert delete_studio("要删的") is False


def test_render_studio_by_name_refactored(monkeypatch, tmp_path: Path):
    """重构成 get_studio 后行为不变（name 与 stem 均命中）。"""
    d = _write_fixture(tmp_path)
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)
    assert "## 工作坊：测试工坊" in render_studio_by_name("测试工坊")
    assert "## 工作坊：测试工坊" in render_studio_by_name("obsidian-km-workshop")
    assert render_studio_by_name("不存在的工坊") == ""


def test_studios_route_crud(monkeypatch, tmp_path: Path):
    """route 级闭环：schema → create → list → get → put(改名) → delete。"""
    from urllib.parse import quote

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes.studios import router

    d = tmp_path / "studios"
    monkeypatch.setattr("agent.studio.STUDIOS_DIR", d)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 空列表 + schema
    assert client.get("/studios").json() == {"studios": []}
    schema = client.get("/studios/schema").json()
    assert "fields" in schema and len(schema["fields"]) > 0

    # create
    r = client.post("/studios", json={"document": {"name": "路由工坊", "description": "d"}})
    assert r.status_code == 200
    assert r.json() == {"name": "路由工坊", "description": "d", "filename": "路由工坊.yaml"}

    # list 含 filename
    lst = client.get("/studios").json()["studios"]
    assert lst == [{"name": "路由工坊", "description": "d", "filename": "路由工坊.yaml"}]

    # get one / get missing
    enc = quote("路由工坊")
    assert client.get(f"/studios/{enc}").json()["name"] == "路由工坊"
    assert client.get("/studios/%E4%B8%8D%E5%AD%98%E5%9C%A8").status_code == 404

    # put 改名 → 文件重命名
    new_enc = quote("新路由工坊")
    r = client.put(
        f"/studios/{enc}",
        json={"document": {"name": "新路由工坊", "description": "d2"}},
    )
    assert r.status_code == 200
    assert r.json()["filename"] == "新路由工坊.yaml"
    assert not (d / "路由工坊.yaml").exists()

    # delete / 重复 delete 404
    assert client.delete(f"/studios/{new_enc}").status_code == 200
    assert client.delete(f"/studios/{new_enc}").status_code == 404
    assert client.get("/studios").json() == {"studios": []}


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
