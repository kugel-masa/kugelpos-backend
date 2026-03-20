"""
Tests for journal exception classes and error code messages.
"""
import pytest
from fastapi import status

from app.exceptions.journal_error_codes import JournalErrorCode, JournalErrorMessage
from app.exceptions.journal_exceptions import (
    ExportException,
    ExternalServiceException,
    ImportException,
    JournalCreationException,
    JournalDataException,
    JournalDateException,
    JournalFormatException,
    JournalNotFoundException,
    JournalQueryException,
    JournalTextException,
    JournalValidationException,
    LogSequenceException,
    LogsMissingException,
    ReceiptGenerationException,
    StoreNotFoundException,
    TerminalNotFoundException,
    TransactionReceiptException,
    TransactionValidationException,
)


# ---------------------------------------------------------------------------
# Target 1: All 14 uncovered exception __init__ methods (lines 84-292)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exception_class, expected_error_code, expected_status_code",
    [
        (JournalFormatException, JournalErrorCode.JOURNAL_FORMAT_ERROR, status.HTTP_400_BAD_REQUEST),
        (JournalDateException, JournalErrorCode.JOURNAL_DATE_ERROR, status.HTTP_400_BAD_REQUEST),
        (JournalDataException, JournalErrorCode.JOURNAL_DATA_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (TerminalNotFoundException, JournalErrorCode.TERMINAL_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (StoreNotFoundException, JournalErrorCode.STORE_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (LogsMissingException, JournalErrorCode.LOGS_MISSING, status.HTTP_400_BAD_REQUEST),
        (LogSequenceException, JournalErrorCode.LOG_SEQUENCE_ERROR, status.HTTP_400_BAD_REQUEST),
        (TransactionValidationException, JournalErrorCode.TRANSACTION_VALIDATION_ERROR, status.HTTP_400_BAD_REQUEST),
        (ReceiptGenerationException, JournalErrorCode.RECEIPT_GENERATION_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JournalTextException, JournalErrorCode.JOURNAL_TEXT_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (ExportException, JournalErrorCode.EXPORT_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (ImportException, JournalErrorCode.IMPORT_ERROR, status.HTTP_400_BAD_REQUEST),
        (TransactionReceiptException, JournalErrorCode.TRANSACTION_RECEIPT_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (ExternalServiceException, JournalErrorCode.EXTERNAL_SERVICE_ERROR, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda val: val.__name__ if isinstance(val, type) else str(val),
)
def test_exception_instantiation(exception_class, expected_error_code, expected_status_code):
    """Each exception can be instantiated and carries the correct error code and status."""
    exc = exception_class("test error message")
    assert exc.error_code == expected_error_code
    assert exc.status_code == expected_status_code


@pytest.mark.parametrize(
    "exception_class",
    [
        JournalFormatException,
        JournalDateException,
        JournalDataException,
        TerminalNotFoundException,
        StoreNotFoundException,
        LogsMissingException,
        LogSequenceException,
        TransactionValidationException,
        ReceiptGenerationException,
        JournalTextException,
        ExportException,
        ImportException,
        TransactionReceiptException,
        ExternalServiceException,
    ],
    ids=lambda val: val.__name__,
)
def test_exception_with_original_exception(exception_class):
    """Each exception accepts an original_exception parameter."""
    original = ValueError("original cause")
    exc = exception_class("wrapped error", original_exception=original)
    assert exc.original_exception is original


# Also cover the 4 already-covered classes to ensure consistency
@pytest.mark.parametrize(
    "exception_class, expected_status_code",
    [
        (JournalNotFoundException, status.HTTP_404_NOT_FOUND),
        (JournalValidationException, status.HTTP_400_BAD_REQUEST),
        (JournalCreationException, status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JournalQueryException, status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda val: val.__name__ if isinstance(val, type) else str(val),
)
def test_already_covered_exceptions(exception_class, expected_status_code):
    """Verify the first 4 exception classes as well."""
    exc = exception_class("msg")
    assert exc.status_code == expected_status_code


# ---------------------------------------------------------------------------
# Target 2: JournalErrorMessage.get_message() fallback paths
# ---------------------------------------------------------------------------

class TestJournalErrorMessageGetMessage:
    """Tests for get_message fallback logic (lines 133, 141-150)."""

    def test_unsupported_language_falls_back_to_default(self):
        """Unsupported language code should fall back to the default language (ja)."""
        msg = JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_NOT_FOUND, lang="fr")
        expected_ja = JournalErrorMessage.MESSAGES["ja"][JournalErrorCode.JOURNAL_NOT_FOUND]
        assert msg == expected_ja

    def test_default_message_returned_when_code_unknown(self):
        """When error code is unknown and default_message is provided, return it."""
        msg = JournalErrorMessage.get_message("999999", default_message="custom fallback")
        assert msg == "custom fallback"

    def test_invalid_code_no_default_returns_generic_error(self):
        """When error code is unknown and no default_message, return generic error."""
        msg = JournalErrorMessage.get_message("999999")
        # Should return the DEFAULT_ERROR_MESSAGES for the default language (ja)
        assert msg == "不明なエラーが発生しました"

    def test_invalid_code_english_lang_returns_generic_error(self):
        """When error code is unknown, lang=en, no default_message, return English generic."""
        msg = JournalErrorMessage.get_message("999999", lang="en")
        assert msg == "An unknown error occurred"

    def test_valid_code_english(self):
        """get_message with lang='en' returns the English message."""
        msg = JournalErrorMessage.get_message(JournalErrorCode.EXPORT_ERROR, lang="en")
        assert msg == "Failed to export data"

    def test_valid_code_default_language(self):
        """get_message with no lang returns the default (ja) message."""
        msg = JournalErrorMessage.get_message(JournalErrorCode.EXPORT_ERROR)
        assert msg == "データのエクスポートに失敗しました"
