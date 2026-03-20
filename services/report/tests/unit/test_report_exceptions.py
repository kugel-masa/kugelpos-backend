"""Unit tests for app/exceptions/report_exceptions.py and report_error_codes.py"""
import pytest
from unittest.mock import MagicMock
from fastapi import status

from app.exceptions.report_error_codes import ReportErrorCode, ReportErrorMessage
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


# ---------------------------------------------------------------------------
# Task 3a: Test all exception classes in report_exceptions.py
# ---------------------------------------------------------------------------

EXCEPTION_TEST_CASES = [
    ("ReportNotFoundException", ReportErrorCode.REPORT_NOT_FOUND, status.HTTP_404_NOT_FOUND),
    ("ReportValidationException", ReportErrorCode.REPORT_VALIDATION_ERROR, status.HTTP_400_BAD_REQUEST),
    ("ReportGenerationException", ReportErrorCode.REPORT_GENERATION_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ReportTypeException", ReportErrorCode.REPORT_TYPE_ERROR, status.HTTP_400_BAD_REQUEST),
    ("ReportScopeException", ReportErrorCode.REPORT_SCOPE_ERROR, status.HTTP_400_BAD_REQUEST),
    ("ReportDateException", ReportErrorCode.REPORT_DATE_ERROR, status.HTTP_400_BAD_REQUEST),
    ("ReportDataException", ReportErrorCode.REPORT_DATA_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("TerminalNotClosedException", ReportErrorCode.TERMINAL_NOT_CLOSED, status.HTTP_403_FORBIDDEN),
    ("LogsMissingException", ReportErrorCode.LOGS_MISSING, status.HTTP_400_BAD_REQUEST),
    ("LogCountMismatchException", ReportErrorCode.LOG_COUNT_MISMATCH, status.HTTP_400_BAD_REQUEST),
    ("TransactionMissingException", ReportErrorCode.TRANSACTION_MISSING, status.HTTP_400_BAD_REQUEST),
    ("CashInOutMissingException", ReportErrorCode.CASH_IN_OUT_MISSING, status.HTTP_400_BAD_REQUEST),
    ("OpenCloseLogMissingException", ReportErrorCode.OPEN_CLOSE_LOG_MISSING, status.HTTP_400_BAD_REQUEST),
    ("VerificationFailedException", ReportErrorCode.VERIFICATION_FAILED, status.HTTP_400_BAD_REQUEST),
    ("ReceiptGenerationException", ReportErrorCode.RECEIPT_GENERATION_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("JournalGenerationException", ReportErrorCode.JOURNAL_GENERATION_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ExportException", ReportErrorCode.EXPORT_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ImportException", ReportErrorCode.IMPORT_ERROR, status.HTTP_400_BAD_REQUEST),
    ("DailyInfoException", ReportErrorCode.DAILY_INFO_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ExternalServiceException", ReportErrorCode.EXTERNAL_SERVICE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("CategoryMasterDataNotFoundException", ReportErrorCode.EXTERNAL_SERVICE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ("ItemMasterDataNotFoundException", ReportErrorCode.EXTERNAL_SERVICE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
]


@pytest.mark.parametrize("class_name,expected_code,expected_status", EXCEPTION_TEST_CASES)
def test_exception_basic(class_name, expected_code, expected_status):
    """Each exception should set error_code, status_code, and user_message."""
    import app.exceptions.report_exceptions as mod

    exc_class = getattr(mod, class_name)
    exc = exc_class("test error message")

    assert exc.error_code == expected_code
    assert exc.status_code == expected_status
    assert exc.user_message is not None
    assert str(exc) == "test error message"


@pytest.mark.parametrize("class_name,expected_code,expected_status", EXCEPTION_TEST_CASES)
def test_exception_with_original_exception(class_name, expected_code, expected_status):
    """Each exception should accept and store an original_exception."""
    import app.exceptions.report_exceptions as mod

    exc_class = getattr(mod, class_name)
    orig = ValueError("original cause")
    exc = exc_class("wrapper message", original_exception=orig)

    assert exc.original_exception is orig
    assert "original cause" in exc.message


@pytest.mark.parametrize("class_name,expected_code,expected_status", EXCEPTION_TEST_CASES)
def test_exception_with_logger(class_name, expected_code, expected_status):
    """Each exception should log via the provided logger."""
    import app.exceptions.report_exceptions as mod

    exc_class = getattr(mod, class_name)
    mock_logger = MagicMock()
    exc = exc_class("log this", logger=mock_logger)

    mock_logger.log.assert_called_once()


# ---------------------------------------------------------------------------
# Task 3b: Test ReportErrorMessage.get_message() fallback paths
# ---------------------------------------------------------------------------

class TestReportErrorMessageGetMessage:
    """Test the get_message classmethod covering uncovered fallback lines."""

    def test_known_code_default_lang(self):
        """Known code with default language should return the Japanese message."""
        msg = ReportErrorMessage.get_message(ReportErrorCode.REPORT_NOT_FOUND)
        assert msg == "レポートが見つかりません"

    def test_known_code_explicit_ja(self):
        """Known code with explicit 'ja' should return the Japanese message."""
        msg = ReportErrorMessage.get_message(ReportErrorCode.REPORT_NOT_FOUND, lang="ja")
        assert msg == "レポートが見つかりません"

    def test_known_code_explicit_en(self):
        """Known code with explicit 'en' should return the English message."""
        msg = ReportErrorMessage.get_message(ReportErrorCode.REPORT_NOT_FOUND, lang="en")
        assert msg == "Report not found"

    def test_unsupported_language_falls_back_to_default(self):
        """Unsupported language code should fall back to default language (ja)."""
        # Line 138-139: unsupported lang -> reset to default
        msg = ReportErrorMessage.get_message(ReportErrorCode.REPORT_NOT_FOUND, lang="fr")
        assert msg == "レポートが見つかりません"

    def test_unknown_code_with_default_message(self):
        """Unknown error code with a default_message should return that default."""
        # Line 147-148: message is None, default_message provided
        msg = ReportErrorMessage.get_message("999999", default_message="custom fallback")
        assert msg == "custom fallback"

    def test_unknown_code_no_default_message_default_lang(self):
        """Unknown code, no default_message, default lang -> DEFAULT_ERROR_MESSAGES."""
        # Lines 155-158: message is None, no default_message, lang == DEFAULT_LANGUAGE
        # so it skips the retry block and hits the final fallback
        msg = ReportErrorMessage.get_message("999999")
        expected = CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(
            CommonErrorMessage.DEFAULT_LANGUAGE
        )
        assert msg == expected

    def test_unknown_code_en_lang_retries_default_lang(self):
        """Unknown code in 'en' with no default_message.

        The code is not in 'en' MESSAGES, so it tries default lang (ja).
        If also not found in ja, returns DEFAULT_ERROR_MESSAGES for 'en'.
        """
        # Lines 151-152: lang != DEFAULT_LANGUAGE, retry with default lang
        # Lines 155-158: still None -> return default error message
        msg = ReportErrorMessage.get_message("999999", lang="en")
        expected = CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get("en")
        assert msg == expected

    def test_all_error_codes_have_messages_ja(self):
        """Every ReportErrorCode should have a corresponding 'ja' message."""
        for attr in dir(ReportErrorCode):
            if attr.startswith("_"):
                continue
            code = getattr(ReportErrorCode, attr)
            msg = ReportErrorMessage.get_message(code, lang="ja")
            assert msg is not None
            # Should not be the generic fallback
            assert msg != CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get("ja")

    def test_all_error_codes_have_messages_en(self):
        """Every ReportErrorCode should have a corresponding 'en' message."""
        for attr in dir(ReportErrorCode):
            if attr.startswith("_"):
                continue
            code = getattr(ReportErrorCode, attr)
            msg = ReportErrorMessage.get_message(code, lang="en")
            assert msg is not None
            assert msg != CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get("en")
