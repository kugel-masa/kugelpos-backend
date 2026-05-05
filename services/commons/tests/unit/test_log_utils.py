"""Unit tests for kugel_common.utils.log_utils."""
import os

import pytest

from kugel_common.utils.log_utils import mask_api_key, mask_dict_api_key


@pytest.fixture(autouse=True)
def _ensure_masking_enabled(monkeypatch):
    """Default: masking enabled. Tests that need it disabled override locally."""
    monkeypatch.delenv("DISABLE_API_KEY_MASKING", raising=False)


class TestMaskApiKey:
    def test_none_returns_stars(self):
        assert mask_api_key(None) == "****"

    def test_empty_string_returns_stars(self):
        assert mask_api_key("") == "****"

    def test_short_key_returns_stars(self):
        # Boundary: 8 chars is treated as short
        assert mask_api_key("12345678") == "****"

    def test_one_char_returns_stars(self):
        assert mask_api_key("a") == "****"

    def test_nine_char_key_truncated(self):
        # First boundary case where masking reveals first4...last4
        assert mask_api_key("abcdefghi") == "abcd...fghi"

    def test_long_key_truncated(self):
        assert mask_api_key("abcd1234efgh5678") == "abcd...5678"

    def test_very_long_key_truncated(self):
        key = "sk_live_" + "x" * 40 + "_end1234"
        assert mask_api_key(key) == "sk_l...1234"


class TestMaskApiKeyDisabled:
    """When DISABLE_API_KEY_MASKING=True, the original key passes through."""

    def test_long_key_unmasked(self, monkeypatch):
        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "True")
        assert mask_api_key("abcd1234efgh5678") == "abcd1234efgh5678"

    def test_short_key_unmasked(self, monkeypatch):
        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "True")
        assert mask_api_key("short") == "short"

    def test_none_still_returns_stars(self, monkeypatch):
        # Even when masking is disabled, None has no plaintext to surface
        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "True")
        assert mask_api_key(None) == "****"

    def test_other_truthy_env_value_does_not_disable(self, monkeypatch):
        # Only the literal string "True" disables masking
        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "true")
        assert mask_api_key("abcd1234efgh5678") == "abcd...5678"

        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "1")
        assert mask_api_key("abcd1234efgh5678") == "abcd...5678"


class TestMaskDictApiKey:
    def test_none_returns_none(self):
        assert mask_dict_api_key(None) is None

    def test_empty_dict_returns_empty(self):
        assert mask_dict_api_key({}) == {}

    def test_dict_without_api_key_unchanged(self):
        data = {"name": "alice", "tenant_id": "T001"}
        assert mask_dict_api_key(data) == data

    def test_lowercase_api_key_masked(self):
        result = mask_dict_api_key({"api_key": "abcd1234efgh5678", "other": "x"})
        assert result == {"api_key": "abcd...5678", "other": "x"}

    def test_uppercase_api_key_masked(self):
        result = mask_dict_api_key({"API_KEY": "abcd1234efgh5678"})
        assert result == {"API_KEY": "abcd...5678"}

    def test_both_variants_masked(self):
        result = mask_dict_api_key(
            {"api_key": "abcd1234efgh5678", "API_KEY": "qrst1234uvwx5678"}
        )
        assert result == {"api_key": "abcd...5678", "API_KEY": "qrst...5678"}

    def test_original_dict_not_mutated(self):
        # Critical: callers in security.py rely on the original dict's
        # api_key being intact for the post-log auth comparison.
        original = {"api_key": "abcd1234efgh5678", "name": "alice"}
        mask_dict_api_key(original)
        assert original == {"api_key": "abcd1234efgh5678", "name": "alice"}

    def test_short_key_in_dict_masked_to_stars(self):
        result = mask_dict_api_key({"api_key": "short"})
        assert result == {"api_key": "****"}

    def test_none_value_in_dict_masked_to_stars(self):
        result = mask_dict_api_key({"api_key": None})
        assert result == {"api_key": "****"}

    def test_disabled_passes_through_dict(self, monkeypatch):
        monkeypatch.setenv("DISABLE_API_KEY_MASKING", "True")
        result = mask_dict_api_key({"api_key": "abcd1234efgh5678"})
        assert result == {"api_key": "abcd1234efgh5678"}
