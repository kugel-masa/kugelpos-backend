"""
Unit tests for cart exception classes and error code/message handling.
"""
import pytest
from unittest.mock import MagicMock
from fastapi import status

from app.exceptions.cart_error_codes import CartErrorCode, CartErrorMessage
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


# ---------------------------------------------------------------------------
# Task 2-1: Test all exception classes in cart_exceptions.py
# ---------------------------------------------------------------------------

# Each tuple: (ExceptionClass, expected_error_code, expected_status_code)
EXCEPTION_TEST_CASES = [
    ("CartCannotCreateException", CartErrorCode.CART_CREATE_ERROR, status.HTTP_400_BAD_REQUEST),
    ("CartNotFoundException", CartErrorCode.CART_NOT_FOUND, status.HTTP_404_NOT_FOUND),
    ("CartCannotSaveException", CartErrorCode.CART_SAVE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ItemNotFoundException", CartErrorCode.ITEM_NOT_FOUND, status.HTTP_404_NOT_FOUND),
    ("BalanceZeroException", CartErrorCode.BALANCE_ZERO, status.HTTP_406_NOT_ACCEPTABLE),
    ("BalanceMinusException", CartErrorCode.BALANCE_MINUS, status.HTTP_406_NOT_ACCEPTABLE),
    ("BalanceGreaterThanZeroException", CartErrorCode.BALANCE_GREATER_THAN_ZERO, status.HTTP_406_NOT_ACCEPTABLE),
    ("DepositOverException", CartErrorCode.DEPOSIT_OVER, status.HTTP_406_NOT_ACCEPTABLE),
    ("TerminalStatusException", CartErrorCode.TERMINAL_STATUS_ERROR, status.HTTP_400_BAD_REQUEST),
    ("SignInOutException", CartErrorCode.SIGN_IN_OUT_ERROR, status.HTTP_400_BAD_REQUEST),
    ("AmountLessThanDiscountException", CartErrorCode.AMOUNT_LESS_THAN_DISCOUNT, status.HTTP_400_BAD_REQUEST),
    ("BalanceLessThanDiscountException", CartErrorCode.BALANCE_LESS_THAN_DISCOUNT, status.HTTP_400_BAD_REQUEST),
    ("DiscountAllocationException", CartErrorCode.DISCOUNT_ALLOCATION_ERROR, status.HTTP_400_BAD_REQUEST),
    ("DiscountRestrictionException", CartErrorCode.DISCOUNT_RESTRICTION, status.HTTP_400_BAD_REQUEST),
    ("ExternalServiceException", CartErrorCode.EXTERNAL_SERVICE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("InternalErrorException", CartErrorCode.INTERNAL_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("UnexpectedErrorException", CartErrorCode.UNEXPECTED_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("AlreadyVoidedException", CartErrorCode.ALREADY_VOIDED, status.HTTP_400_BAD_REQUEST),
    ("AlreadyRefundedException", CartErrorCode.ALREADY_REFUNDED, status.HTTP_400_BAD_REQUEST),
]


class TestCartExceptions:
    """Tests for all exception classes in cart_exceptions.py"""

    @pytest.mark.parametrize(
        "class_name,expected_error_code,expected_status_code",
        EXCEPTION_TEST_CASES,
        ids=[t[0] for t in EXCEPTION_TEST_CASES],
    )
    def test_exception_init(self, class_name, expected_error_code, expected_status_code):
        """Each exception sets the correct error_code, status_code, and user_message."""
        import app.exceptions.cart_exceptions as mod

        ExcClass = getattr(mod, class_name)
        exc = ExcClass("test message")

        assert exc.error_code == expected_error_code
        assert exc.status_code == expected_status_code
        assert exc.user_message is not None
        assert "test message" in str(exc)

    @pytest.mark.parametrize(
        "class_name,expected_error_code,expected_status_code",
        EXCEPTION_TEST_CASES,
        ids=[f"{t[0]}_with_original" for t in EXCEPTION_TEST_CASES],
    )
    def test_exception_with_original_exception(self, class_name, expected_error_code, expected_status_code):
        """Each exception correctly wraps an original exception."""
        import app.exceptions.cart_exceptions as mod

        ExcClass = getattr(mod, class_name)
        original = ValueError("original error")
        exc = ExcClass("test message", original_exception=original)

        assert exc.original_exception is original
        assert exc.error_code == expected_error_code


# ---------------------------------------------------------------------------
# Task 2-2: Test CartErrorMessage.get_message() fallback paths
# ---------------------------------------------------------------------------

class TestCartErrorMessage:
    """Tests for CartErrorMessage.get_message() including fallback logic."""

    def test_get_message_default_language(self):
        """Returns Japanese message when lang is not specified (default)."""
        msg = CartErrorMessage.get_message(CartErrorCode.CART_NOT_FOUND)
        assert msg == "カートが見つかりません"

    def test_get_message_english(self):
        """Returns English message when lang='en'."""
        msg = CartErrorMessage.get_message(CartErrorCode.CART_NOT_FOUND, lang="en")
        assert msg == "Cart not found"

    def test_get_message_unsupported_language_falls_back(self):
        """Unsupported language falls back to default language (ja)."""
        msg = CartErrorMessage.get_message(CartErrorCode.CART_NOT_FOUND, lang="fr")
        assert msg == "カートが見つかりません"

    def test_get_message_unknown_code_with_default_message(self):
        """Unknown error code returns default_message if provided."""
        msg = CartErrorMessage.get_message("UNKNOWN_CODE", default_message="custom fallback")
        assert msg == "custom fallback"

    def test_get_message_unknown_code_no_default(self):
        """Unknown error code without default_message returns the common default error message."""
        msg = CartErrorMessage.get_message("UNKNOWN_CODE")
        # Should return the DEFAULT_ERROR_MESSAGES for the default language
        expected = CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(CommonErrorMessage.DEFAULT_LANGUAGE)
        assert msg == expected

    def test_get_message_unknown_code_en_fallback_to_default_lang(self):
        """Unknown code in 'en' tries default language, then falls back to default error message."""
        # Use a code that does not exist in any language
        msg = CartErrorMessage.get_message("TOTALLY_UNKNOWN", lang="en")
        # Since the code is not in 'en' MESSAGES, and not in default lang MESSAGES,
        # it should return DEFAULT_ERROR_MESSAGES for 'en'
        expected = CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get("en")
        assert msg == expected

    def test_get_message_all_codes_have_ja_and_en(self):
        """Verify every CartErrorCode has both ja and en messages."""
        codes = [
            v for k, v in vars(CartErrorCode).items()
            if not k.startswith("_")
        ]
        for code in codes:
            ja_msg = CartErrorMessage.get_message(code, lang="ja")
            en_msg = CartErrorMessage.get_message(code, lang="en")
            assert ja_msg is not None, f"Missing ja message for {code}"
            assert en_msg is not None, f"Missing en message for {code}"
