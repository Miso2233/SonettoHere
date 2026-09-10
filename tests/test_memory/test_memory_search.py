"""api/memory/search.py 测试 — 主题+正则命中与 related 多级闭包。"""

import re

import pytest

from api.memory.search import render_search_result, search_with_closure

# A(USER,命中源) → B(USER) → C(PREFERENCE)；D 孤立；E 另一主题也含命中词
ADJ = {
    "aaaa": {
        "id": "aaaa",
        "theme": "USER",
        "description": "Miso 喜欢打网球。",
        "related": ["bbbb", "missing", "aaaa"],
        "_sort_time": "2026-09-01 10:00:00",
    },
    "bbbb": {
        "id": "bbbb",
        "theme": "USER",
        "description": "Miso 常去沙河打球馆。",
        "related": ["aaaa", "cccc"],
        "_sort_time": "2026-09-02 10:00:00",
    },
    "cccc": {
        "id": "cccc",
        "theme": "PREFERENCE",
        "description": "Miso 关注网球球星。",
        "related": ["bbbb"],
        "_sort_time": "2026-09-04 10:00:00",
    },
    "dddd": {
        "id": "dddd",
        "theme": "MOMENT",
        "description": "与天气无关的旧事。",
        "related": [],
        "_sort_time": "2026-09-05 10:00:00",
    },
}


class TestSearchWithClosure:
    def test_theme_filter_and_multilevel_closure(self):
        result = search_with_closure(ADJ, theme="USER", regex="网球")
        matched_ids = [item["id"] for item in result["matched"]]
        assert matched_ids == ["aaaa"]
        related = {item["id"]: item["depth"] for item in result["related"]}
        # A 命中 → B 第 1 级 → C 第 2 级；悬空(missing)与自引用(aaaa)被跳过
        assert related == {"bbbb": 1, "cccc": 2}
        assert result["truncated"] is False

    def test_no_theme_searches_all(self):
        result = search_with_closure(ADJ, theme=None, regex="网球")
        matched = [item["id"] for item in result["matched"]]
        # A 与 C（不同主题）都命中；按 _sort_time 降序 C 在前
        assert set(matched) == {"aaaa", "cccc"}
        assert matched[0] == "cccc"
        related_ids = [item["id"] for item in result["related"]]
        assert related_ids == ["bbbb"]

    def test_dangling_and_self_references_skipped(self):
        result = search_with_closure(ADJ, theme="USER", regex="喜欢打网球")
        # A.related 含 missing 与自身 aaaa，均不会进入闭包
        assert [item["id"] for item in result["related"]] == ["bbbb", "cccc"]

    def test_invalid_theme_raises(self):
        with pytest.raises(ValueError, match="仅允许"):
            search_with_closure(ADJ, theme="身份", regex="网球")

    def test_invalid_regex_raises(self):
        with pytest.raises(re.error):
            search_with_closure(ADJ, theme=None, regex="[unclosed")

    def test_no_match_empty(self):
        result = search_with_closure(ADJ, theme=None, regex="气象预报")
        assert result["matched"] == []
        assert result["related"] == []
        assert render_search_result(result) == "（无匹配记忆）"


class TestRenderSearchResult:
    def test_render_sections_and_depth(self):
        result = search_with_closure(ADJ, theme="USER", regex="网球")
        text = render_search_result(result)
        assert "## 匹配条目（1）" in text
        assert "[aaaa] (USER)" in text
        assert "## 关联条目（多级，2）" in text
        assert "[bbbb] (USER)" in text and "第 1 级关联" in text
        assert "[cccc] (PREFERENCE)" in text and "第 2 级关联" in text
