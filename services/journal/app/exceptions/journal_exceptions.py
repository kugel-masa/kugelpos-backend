# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Definition of exception classes specific to the journal service
"""
from fastapi import status
from logging import getLogger

from kugel_common.exceptions import ServiceException
from app.exceptions.journal_error_codes import JournalErrorCode, JournalErrorMessage

logger = getLogger(__name__)


class JournalNotFoundException(ServiceException):
    """
    Exception raised when the requested journal is not found
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_NOT_FOUND,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class JournalValidationException(ServiceException):
    """
    Exception raised when journal validation fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_VALIDATION_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_VALIDATION_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class JournalCreationException(ServiceException):
    """
    Exception raised when journal creation fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_CREATION_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_CREATION_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class JournalQueryException(ServiceException):
    """
    Exception raised when journal query fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_QUERY_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_QUERY_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class JournalFormatException(ServiceException):
    """
    Exception raised when journal format is invalid
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_FORMAT_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_FORMAT_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class JournalDateException(ServiceException):
    """
    Exception raised when there is an issue with the journal date
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_DATE_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_DATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class JournalDataException(ServiceException):
    """
    Exception raised when there is an issue with the journal data
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_DATA_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_DATA_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class TerminalNotFoundException(ServiceException):
    """
    Exception raised when the terminal is not found
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.TERMINAL_NOT_FOUND,
            JournalErrorMessage.get_message(JournalErrorCode.TERMINAL_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class StoreNotFoundException(ServiceException):
    """
    Exception raised when the store is not found
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.STORE_NOT_FOUND,
            JournalErrorMessage.get_message(JournalErrorCode.STORE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class LogsMissingException(ServiceException):
    """
    Exception raised when required logs are missing
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.LOGS_MISSING,
            JournalErrorMessage.get_message(JournalErrorCode.LOGS_MISSING),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class LogSequenceException(ServiceException):
    """
    Exception raised when there is an issue with the log sequence
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.LOG_SEQUENCE_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.LOG_SEQUENCE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TransactionValidationException(ServiceException):
    """
    Exception raised when transaction validation fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.TRANSACTION_VALIDATION_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.TRANSACTION_VALIDATION_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReceiptGenerationException(ServiceException):
    """
    Exception raised when receipt generation fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.RECEIPT_GENERATION_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.RECEIPT_GENERATION_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class JournalTextException(ServiceException):
    """
    Exception raised when journal text generation fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.JOURNAL_TEXT_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.JOURNAL_TEXT_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExportException(ServiceException):
    """
    Exception raised when data export fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.EXPORT_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.EXPORT_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ImportException(ServiceException):
    """
    Exception raised when data import fails
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.IMPORT_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.IMPORT_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TransactionReceiptException(ServiceException):
    """
    Exception raised when there is an issue with the transaction receipt
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.TRANSACTION_RECEIPT_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.TRANSACTION_RECEIPT_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExternalServiceException(ServiceException):
    """
    Exception raised when there is an issue with an external service
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            JournalErrorCode.EXTERNAL_SERVICE_ERROR,
            JournalErrorMessage.get_message(JournalErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
