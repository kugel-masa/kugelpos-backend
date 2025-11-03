# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
reportサービス固有の例外クラスの定義
"""
from fastapi import status
from logging import getLogger

from kugel_common.exceptions import ServiceException
from app.exceptions.report_error_codes import ReportErrorCode, ReportErrorMessage

logger = getLogger(__name__)


class ReportNotFoundException(ServiceException):
    """
    要求されたレポートが見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_NOT_FOUND,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ReportValidationException(ServiceException):
    """
    レポートのバリデーションに失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_VALIDATION_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_VALIDATION_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReportGenerationException(ServiceException):
    """
    レポートの生成に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_GENERATION_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_GENERATION_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ReportTypeException(ServiceException):
    """
    無効なレポートタイプが指定された場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_TYPE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_TYPE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReportScopeException(ServiceException):
    """
    無効なレポートスコープが指定された場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_SCOPE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_SCOPE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReportDateException(ServiceException):
    """
    レポート日付に問題がある場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_DATE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_DATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReportDataException(ServiceException):
    """
    レポートデータに問題がある場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.REPORT_DATA_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.REPORT_DATA_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class TerminalNotClosedException(ServiceException):
    """
    端末がクローズされていないため、レポートを生成できない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.TERMINAL_NOT_CLOSED,
            ReportErrorMessage.get_message(ReportErrorCode.TERMINAL_NOT_CLOSED),
            status_code=status.HTTP_403_FORBIDDEN,
        )


class LogsMissingException(ServiceException):
    """
    必要なログが欠落している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.LOGS_MISSING,
            ReportErrorMessage.get_message(ReportErrorCode.LOGS_MISSING),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class LogCountMismatchException(ServiceException):
    """
    ログの数が一致しない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.LOG_COUNT_MISMATCH,
            ReportErrorMessage.get_message(ReportErrorCode.LOG_COUNT_MISMATCH),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TransactionMissingException(ServiceException):
    """
    トランザクションログが欠落している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.TRANSACTION_MISSING,
            ReportErrorMessage.get_message(ReportErrorCode.TRANSACTION_MISSING),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class CashInOutMissingException(ServiceException):
    """
    入出金ログが欠落している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.CASH_IN_OUT_MISSING,
            ReportErrorMessage.get_message(ReportErrorCode.CASH_IN_OUT_MISSING),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class OpenCloseLogMissingException(ServiceException):
    """
    開閉店ログが欠落している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.OPEN_CLOSE_LOG_MISSING,
            ReportErrorMessage.get_message(ReportErrorCode.OPEN_CLOSE_LOG_MISSING),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class VerificationFailedException(ServiceException):
    """
    データ検証に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.VERIFICATION_FAILED,
            ReportErrorMessage.get_message(ReportErrorCode.VERIFICATION_FAILED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReceiptGenerationException(ServiceException):
    """
    レシートの生成に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.RECEIPT_GENERATION_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.RECEIPT_GENERATION_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class JournalGenerationException(ServiceException):
    """
    ジャーナルの生成に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.JOURNAL_GENERATION_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.JOURNAL_GENERATION_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExportException(ServiceException):
    """
    データのエクスポートに失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.EXPORT_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.EXPORT_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ImportException(ServiceException):
    """
    データのインポートに失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.IMPORT_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.IMPORT_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class DailyInfoException(ServiceException):
    """
    日次情報の処理に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.DAILY_INFO_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.DAILY_INFO_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExternalServiceException(ServiceException):
    """
    外部サービスの呼び出しに失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.EXTERNAL_SERVICE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class CategoryMasterDataNotFoundException(ServiceException):
    """
    カテゴリーマスタデータの取得に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.EXTERNAL_SERVICE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ItemMasterDataNotFoundException(ServiceException):
    """
    商品マスタデータの取得に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            ReportErrorCode.EXTERNAL_SERVICE_ERROR,
            ReportErrorMessage.get_message(ReportErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
