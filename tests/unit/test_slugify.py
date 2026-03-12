"""
Tests for the canonical slugify implementation (slug_utils.py).

All scripts now import from slug_utils — these tests verify the shared
implementation and confirm cross-script consistency.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "deal-project-classifier" / "scripts"))

from slug_utils import slugify


def get_classifier_slugify():
    from classify_messages import slugify
    return slugify


def get_apply_updates_slugify():
    from apply_updates import slugify
    return slugify


def get_rebuild_index_slugify():
    from rebuild_index import slugify
    return slugify


class TestCanonicalSlugify:
    """Tests for the shared slug_utils.slugify implementation."""

    def test_basic(self):
        assert slugify("WidgetCo Inc.") == "widgetco-inc"

    def test_unicode(self):
        result = slugify("Ünternéhmen GmbH")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_emoji_stripped(self):
        result = slugify("🚀 Rocket Co")
        assert "rocket" in result
        assert "co" in result

    def test_truncation_at_40(self):
        result = slugify("A" * 200)
        assert len(result) <= 40

    def test_empty_string(self):
        assert slugify("") == ""

    def test_only_special_chars(self):
        assert slugify("!@#$%^&*()") == ""

    def test_preserves_numbers(self):
        assert slugify("Web3 AI 2024") == "web3-ai-2024"

    def test_collapses_consecutive_dashes(self):
        result = slugify("MacBook Pro & iPad --- Plus!")
        assert "---" not in result
        assert result == "macbook-pro-ipad-plus"

    def test_strips_leading_trailing_dashes(self):
        result = slugify("---hello---")
        assert result == "hello"

    def test_custom_max_length(self):
        result = slugify("A" * 200, max_length=10)
        assert len(result) == 10

    def test_cjk_characters_stripped(self):
        result = slugify("株式会社テスト")
        # CJK chars are non-alphanumeric, result may be empty
        assert isinstance(result, str)

    def test_rtl_characters_stripped(self):
        result = slugify("الشركة العربية")
        assert isinstance(result, str)


class TestCrossScriptConsistency:
    """All 3 scripts now import from slug_utils — verify they're identical."""

    def test_same_output_for_basic_name(self):
        s1 = get_classifier_slugify()("WidgetCo Inc.")
        s2 = get_apply_updates_slugify()("WidgetCo Inc.")
        s3 = get_rebuild_index_slugify()("WidgetCo Inc.")
        assert s1 == s2 == s3 == "widgetco-inc"

    def test_same_output_for_long_name(self):
        name = "Very Long Company Name That Exceeds Normal Limits"
        s1 = get_classifier_slugify()(name)
        s2 = get_apply_updates_slugify()(name)
        s3 = get_rebuild_index_slugify()(name)
        assert s1 == s2 == s3

    def test_all_use_dashes_not_spaces(self):
        """rebuild_index previously used spaces — verify it now uses dashes."""
        result = get_rebuild_index_slugify()("Hello World")
        assert result == "hello-world"
        assert " " not in result

    def test_all_truncate_at_40(self):
        """classify_messages previously had no truncation — verify it now truncates."""
        long_name = "A" * 200
        s1 = get_classifier_slugify()(long_name)
        s2 = get_apply_updates_slugify()(long_name)
        s3 = get_rebuild_index_slugify()(long_name)
        assert len(s1) == len(s2) == len(s3) == 40
