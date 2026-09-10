"""api.memory.theme 测试 — V6 九大固定语义主题的枚举与工具函数。"""

import pytest

from api.memory.theme import (
    DEFAULT_THEME,
    REVIEW_THEMES,
    THEME_LABELS,
    VALID_THEMES,
    MemoryTheme,
    is_valid_theme,
    needs_review,
    require_theme,
    theme_display,
    theme_label,
)


class TestMemoryTheme:
    """九大主题枚举与标签表的一致性。"""

    def test_has_nine_themes(self) -> None:
        assert len(MemoryTheme) == 9

    def test_keys_match_labels(self) -> None:
        """枚举值集合必须与 THEME_LABELS 键集一致，防止静默漂移。"""
        assert {m.value for m in MemoryTheme} == set(THEME_LABELS)

    def test_valid_themes_matches_labels(self) -> None:
        assert VALID_THEMES == frozenset(THEME_LABELS)

    def test_default_theme_is_valid(self) -> None:
        assert is_valid_theme(DEFAULT_THEME)


class TestValidators:
    """is_valid_theme / require_theme。"""

    @pytest.mark.parametrize("key", list(THEME_LABELS))
    def test_accepts_all_valid_keys(self, key: str) -> None:
        assert is_valid_theme(key) is True
        assert require_theme(key) == key

    @pytest.mark.parametrize("bad", ["身份", "音乐", "健康", "", "   ", "user", "PROJECT "])
    def test_rejects_invalid(self, bad: str) -> None:
        assert is_valid_theme(bad) is False
        with pytest.raises(ValueError):
            require_theme(bad)

    def test_rejects_non_string(self) -> None:
        assert is_valid_theme(None) is False
        assert is_valid_theme(123) is False

    def test_require_theme_message_lists_allowed_keys(self) -> None:
        with pytest.raises(ValueError, match="USER"):
            require_theme("身份", who="add(theme)")


class TestReviewThemes:
    """REVIEW_THEMES / needs_review —— 写入后需用户复核的三主题。"""

    #: 需复核的三主题，独立于实现写死，防止跟着实现一起漂移。
    _EXPECTED = {"TECH", "PROJECT", "MOMENT"}

    def test_subset_of_valid_themes(self) -> None:
        """复核主题必须是合法主题的子集，否则 needs_review 会永远返回 False。"""
        assert REVIEW_THEMES <= VALID_THEMES

    def test_exact_membership(self) -> None:
        assert REVIEW_THEMES == frozenset(self._EXPECTED)

    @pytest.mark.parametrize("key", sorted(_EXPECTED))
    def test_needs_review_true(self, key: str) -> None:
        assert needs_review(key) is True

    @pytest.mark.parametrize(
        "key", sorted(set(THEME_LABELS) - _EXPECTED)
    )
    def test_needs_review_false_for_other_themes(self, key: str) -> None:
        assert needs_review(key) is False

    @pytest.mark.parametrize("bad", ["", "tech", "TECH ", "健康", None, 123, ["TECH"]])
    def test_needs_review_rejects_non_review_values(self, bad: object) -> None:
        """非法 / 不可哈希入参一律 False，不抛 TypeError。"""
        assert needs_review(bad) is False


class TestLabels:
    """theme_label / theme_display。"""

    def test_theme_label_known(self) -> None:
        assert theme_label("USER") == THEME_LABELS["USER"]

    def test_theme_label_unknown_fallback(self) -> None:
        assert theme_label("健康") == "健康"

    def test_theme_display_known(self) -> None:
        assert theme_display("PROJECT") == "PROJECT（学业与创作产出）"

    def test_theme_display_unknown_fallback(self) -> None:
        assert theme_display("健康") == "健康"
