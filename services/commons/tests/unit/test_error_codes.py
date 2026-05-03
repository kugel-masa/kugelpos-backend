# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.exceptions.error_codes."""
import pytest

from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage


class TestErrorCodeFormat:
    """Ensure all defined error codes follow the XXYYZZ 6-digit format."""

    def test_all_codes_are_six_digit_strings(self):
        codes = [
            v for k, v in vars(ErrorCode).items()
            if not k.startswith("_") and isinstance(v, str)
        ]
        assert codes, "no codes found on ErrorCode"
        for code in codes:
            assert isinstance(code, str)
            assert len(code) == 6, f"{code} is not 6 chars"
            assert code.isdigit(), f"{code} is not all digits"

    def test_codes_are_unique(self):
        codes = [
            v for k, v in vars(ErrorCode).items()
            if not k.startswith("_") and isinstance(v, str)
        ]
        assert len(codes) == len(set(codes)), "duplicate error codes"


class TestGetMessageDefaults:
    def test_default_language_is_japanese(self):
        # Assumes ja messages are populated
        msg = ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR)
        # Japanese-only check: contains a CJK char
        assert any("぀" <= ch <= "鿿" for ch in msg)

    def test_explicit_japanese(self):
        msg = ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR, lang="ja")
        assert msg == "システムエラーが発生しました"

    def test_explicit_english(self):
        msg = ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR, lang="en")
        assert msg == "System error occurred"


class TestGetMessageFallbacks:
    def test_unsupported_language_falls_back_to_default(self):
        msg = ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR, lang="fr")
        # fr unsupported → uses ja default
        assert msg == ErrorMessage.MESSAGES["ja"][ErrorCode.SYSTEM_ERROR]

    def test_unknown_code_returns_default_error_message(self):
        msg = ErrorMessage.get_message("999998", lang="ja")
        assert msg == ErrorMessage.DEFAULT_ERROR_MESSAGES["ja"]

    def test_unknown_code_with_explicit_default(self):
        msg = ErrorMessage.get_message("999998", default_message="custom default")
        assert msg == "custom default"

    def test_unknown_code_falls_through_to_default_language_messages(self):
        # If a code exists in 'ja' but not in 'en', requesting 'en' falls back
        # to the 'ja' message. Find or fabricate such a code.
        # All defined codes have both 'ja' and 'en' messages currently, so we
        # test the explicit fallback path with a code present only in 'ja'
        # by patching MESSAGES temporarily.
        import copy
        original = copy.deepcopy(ErrorMessage.MESSAGES)
        try:
            ErrorMessage.MESSAGES["ja"]["TEST_ONLY"] = "ja-only message"
            # 'en' lookup should fall through to ja
            msg = ErrorMessage.get_message("TEST_ONLY", lang="en")
            assert msg == "ja-only message"
        finally:
            ErrorMessage.MESSAGES = original


class TestSpecificCodeValues:
    """Spot-check a few well-known codes don't drift."""

    def test_general_error_code(self):
        assert ErrorCode.GENERAL_ERROR == "100000"

    def test_resource_not_found_code(self):
        assert ErrorCode.RESOURCE_NOT_FOUND == "100001"

    def test_authentication_error_code(self):
        assert ErrorCode.AUTHENTICATION_ERROR == "200001"

    def test_validation_error_code(self):
        assert ErrorCode.VALIDATION_ERROR == "300001"

    def test_database_error_code(self):
        assert ErrorCode.DATABASE_ERROR == "500001"

    def test_unexpected_error_code(self):
        assert ErrorCode.UNEXPECTED_ERROR == "900999"
