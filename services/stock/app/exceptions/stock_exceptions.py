# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
stockサービス固有の例外クラス定義
"""
from typing import Optional
from logging import Logger
from fastapi import status

from kugel_common.exceptions.service_exceptions import ServiceException
from app.exceptions.stock_error_codes import StockErrorCode, get_message


class StockNotFoundError(ServiceException):
    """在庫が見つからない場合に発生する例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_NOT_FOUND,
            user_message=get_message(StockErrorCode.STOCK_NOT_FOUND),
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            logger=logger,
            original_exception=original_exception,
        )


class InsufficientStockError(ServiceException):
    """在庫が不足している場合に発生する例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.INSUFFICIENT_STOCK,
            user_message=get_message(StockErrorCode.INSUFFICIENT_STOCK),
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            logger=logger,
            original_exception=original_exception,
        )


class StockValidationError(ServiceException):
    """在庫情報のバリデーションエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_VALIDATION_ERROR,
            user_message=get_message(StockErrorCode.STOCK_VALIDATION_ERROR),
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            logger=logger,
            original_exception=original_exception,
        )


class StockAccessDeniedError(ServiceException):
    """在庫情報へのアクセスが拒否された場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_ACCESS_DENIED,
            user_message=get_message(StockErrorCode.STOCK_ACCESS_DENIED),
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            logger=logger,
            original_exception=original_exception,
        )


class StockDatabaseError(ServiceException):
    """在庫データベースエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_DATABASE_ERROR,
            user_message=get_message(StockErrorCode.STOCK_DATABASE_ERROR),
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            logger=logger,
            original_exception=original_exception,
        )


class StockUpdateFailedError(ServiceException):
    """在庫更新に失敗した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_UPDATE_FAILED,
            user_message=get_message(StockErrorCode.STOCK_UPDATE_FAILED),
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            logger=logger,
            original_exception=original_exception,
        )


class StockUpdateValidationError(ServiceException):
    """在庫更新のバリデーションエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_UPDATE_VALIDATION_ERROR,
            user_message=get_message(StockErrorCode.STOCK_UPDATE_VALIDATION_ERROR),
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            logger=logger,
            original_exception=original_exception,
        )


class StockUpdateConflictError(ServiceException):
    """在庫更新で競合が発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STOCK_UPDATE_CONFLICT,
            user_message=get_message(StockErrorCode.STOCK_UPDATE_CONFLICT),
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            logger=logger,
            original_exception=original_exception,
        )


class SnapshotCreationFailedError(ServiceException):
    """スナップショット作成に失敗した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.SNAPSHOT_CREATION_FAILED,
            user_message=get_message(StockErrorCode.SNAPSHOT_CREATION_FAILED),
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            logger=logger,
            original_exception=original_exception,
        )


class SnapshotNotFoundError(ServiceException):
    """スナップショットが見つからない場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.SNAPSHOT_NOT_FOUND,
            user_message=get_message(StockErrorCode.SNAPSHOT_NOT_FOUND),
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            logger=logger,
            original_exception=original_exception,
        )


class ExternalServiceError(ServiceException):
    """外部サービスエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.EXTERNAL_SERVICE_ERROR,
            user_message=get_message(StockErrorCode.EXTERNAL_SERVICE_ERROR),
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            logger=logger,
            original_exception=original_exception,
        )


class PubSubError(ServiceException):
    """Pub/Subエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.PUBSUB_ERROR,
            user_message=get_message(StockErrorCode.PUBSUB_ERROR),
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            logger=logger,
            original_exception=original_exception,
        )


class StateStoreError(ServiceException):
    """ステートストアエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.STATE_STORE_ERROR,
            user_message=get_message(StockErrorCode.STATE_STORE_ERROR),
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            logger=logger,
            original_exception=original_exception,
        )


class TransactionProcessingError(ServiceException):
    """トランザクション処理エラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.TRANSACTION_PROCESSING_ERROR,
            user_message=get_message(StockErrorCode.TRANSACTION_PROCESSING_ERROR),
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            logger=logger,
            original_exception=original_exception,
        )


class TransactionValidationError(ServiceException):
    """トランザクションバリデーションエラーが発生した場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.TRANSACTION_VALIDATION_ERROR,
            user_message=get_message(StockErrorCode.TRANSACTION_VALIDATION_ERROR),
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            logger=logger,
            original_exception=original_exception,
        )


class TransactionDuplicateError(ServiceException):
    """重複トランザクションの場合の例外"""

    def __init__(self, message: str, logger: Optional[Logger] = None, original_exception: Optional[Exception] = None):
        super().__init__(
            error_code=StockErrorCode.TRANSACTION_DUPLICATE,
            user_message=get_message(StockErrorCode.TRANSACTION_DUPLICATE),
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            logger=logger,
            original_exception=original_exception,
        )
