# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.exceptions.base_exceptions import ServiceException, RepositoryException
from .terminal_error_codes import TerminalErrorCode, TerminalErrorMessage
from fastapi import status

"""
terminal サービス固有の例外クラスを定義します
"""


# 端末基本操作関連の例外
class TerminalNotFoundException(ServiceException):
    """
    Exception raised when a terminal is not found.
    端末が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_NOT_FOUND,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TerminalAlreadyExistsException(ServiceException):
    """
    Exception raised when a terminal already exists.
    端末がすでに存在する場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_ALREADY_EXISTS,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_ALREADY_EXISTS),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 端末状態関連の例外
class TerminalStatusException(ServiceException):
    """
    Exception raised when a terminal status error is received.
    端末のステータスエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_STATUS_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_STATUS_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalOpenException(ServiceException):
    """
    Exception raised when failing to open a terminal.
    端末のオープン処理に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_OPEN_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_OPEN_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalCloseException(ServiceException):
    """
    Exception raised when failing to close a terminal.
    端末のクローズ処理に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_CLOSE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_CLOSE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalAlreadyOpenedException(ServiceException):
    """
    Exception raised when a terminal is already in open state.
    端末がすでにオープン状態の場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_ALREADY_OPENED,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_ALREADY_OPENED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalAlreadyClosedException(ServiceException):
    """
    Exception raised when a terminal is already in closed state.
    端末がすでにクローズ状態の場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_ALREADY_CLOSED,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_ALREADY_CLOSED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalBusyException(ServiceException):
    """
    Exception raised when a terminal is busy processing another operation.
    端末が他の処理実行中の場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_BUSY,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_BUSY),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalFunctionModeException(ServiceException):
    """
    Exception raised when failing to change terminal function mode.
    機能モード変更に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_FUNCTION_MODE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_FUNCTION_MODE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalNotSignedInException(ServiceException):
    """
    Exception raised when a terminal is not signed in.
    端末がサインインされていない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_NOT_SIGNED_IN,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_NOT_SIGNED_IN),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class TerminalAlreadySignedInException(ServiceException):
    """
    Exception raised when a terminal is already signed in.
    端末がすでにサインイン済みの場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_ALREADY_SIGNED_IN,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_ALREADY_SIGNED_IN),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TerminalSignedOutException(ServiceException):
    """
    Exception raised when a terminal is already signed out.
    端末がサインアウト済みの場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TERMINAL_SIGNED_OUT,
            TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_SIGNED_OUT),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


# サインイン関連の例外
class SignInOutException(ServiceException):
    """
    Exception raised when a sign in/out status error is received.
    サインイン/サインアウトのステータスエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.SIGN_IN_OUT_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.SIGN_IN_OUT_ERROR),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class SignInRequiredException(ServiceException):
    """
    Exception raised when sign in is required.
    サインインが必要な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.SIGN_IN_REQUIRED,
            TerminalErrorMessage.get_message(TerminalErrorCode.SIGN_IN_REQUIRED),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidCredentialsException(ServiceException):
    """
    Exception raised when credentials are invalid.
    認証情報が無効な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.INVALID_CREDENTIALS,
            TerminalErrorMessage.get_message(TerminalErrorCode.INVALID_CREDENTIALS),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


# 金銭出納関連の例外
class CashInOutException(ServiceException):
    """
    Exception raised when a cash in/out operation fails.
    入出金処理に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.CASH_IN_OUT_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.CASH_IN_OUT_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class CashAmountInvalidException(ServiceException):
    """
    Exception raised when an invalid cash amount is provided.
    不正な金額が指定された場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.CASH_AMOUNT_INVALID,
            TerminalErrorMessage.get_message(TerminalErrorCode.CASH_AMOUNT_INVALID),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class CashDrawerClosedException(ServiceException):
    """
    Exception raised when attempting to use a closed cash drawer.
    キャッシュドロワーがクローズ状態の場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.CASH_DRAWER_CLOSED,
            TerminalErrorMessage.get_message(TerminalErrorCode.CASH_DRAWER_CLOSED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class OverMaxAmountException(ServiceException):
    """
    Exception raised when an amount exceeds the maximum limit.
    最大金額を超過した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.OVER_MAX_AMOUNT,
            TerminalErrorMessage.get_message(TerminalErrorCode.OVER_MAX_AMOUNT),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class UnderMinAmountException(ServiceException):
    """
    Exception raised when an amount is below the minimum limit.
    最小金額を下回った場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.UNDER_MIN_AMOUNT,
            TerminalErrorMessage.get_message(TerminalErrorCode.UNDER_MIN_AMOUNT),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class PhysicalAmountMismatchException(ServiceException):
    """
    Exception raised when the physical amount does not match the recorded amount.
    実在高と記録金額が一致しない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.PHYSICAL_AMOUNT_MISMATCH,
            TerminalErrorMessage.get_message(TerminalErrorCode.PHYSICAL_AMOUNT_MISMATCH),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# テナント関連の例外
class TenantNotFoundException(ServiceException):
    """
    Exception raised when a tenant is not found.
    テナントが見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_NOT_FOUND,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TenantAlreadyExistsException(ServiceException):
    """
    Exception raised when a tenant already exists.
    テナントがすでに存在する場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_ALREADY_EXISTS,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_ALREADY_EXISTS),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TenantUpdateException(ServiceException):
    """
    Exception raised when failing to update tenant information.
    テナント情報の更新に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_UPDATE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_UPDATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TenantDeleteException(ServiceException):
    """
    Exception raised when failing to delete a tenant.
    テナントの削除に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_DELETE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_DELETE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TenantConfigException(ServiceException):
    """
    Exception raised when a tenant configuration error occurs.
    テナント設定に問題がある場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_CONFIG_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_CONFIG_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TenantCreateException(ServiceException):
    """
    Exception raised when failing to create a tenant.
    テナントの作成に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.TENANT_CREATE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.TENANT_CREATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 店舗関連の例外
class StoreNotFoundException(ServiceException):
    """
    Exception raised when a store is not found.
    店舗が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.STORE_NOT_FOUND,
            TerminalErrorMessage.get_message(TerminalErrorCode.STORE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class StoreAlreadyExistsException(ServiceException):
    """
    Exception raised when a store already exists.
    店舗がすでに存在する場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.STORE_ALREADY_EXISTS,
            TerminalErrorMessage.get_message(TerminalErrorCode.STORE_ALREADY_EXISTS),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class StoreUpdateException(ServiceException):
    """
    Exception raised when failing to update store information.
    店舗情報の更新に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.STORE_UPDATE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.STORE_UPDATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class StoreDeleteException(ServiceException):
    """
    Exception raised when failing to delete a store.
    店舗の削除に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.STORE_DELETE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.STORE_DELETE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class StoreConfigException(ServiceException):
    """
    Exception raised when a store configuration error occurs.
    店舗設定に問題がある場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.STORE_CONFIG_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.STORE_CONFIG_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class BusinessDateException(ServiceException):
    """
    Exception raised when a business date error occurs.
    営業日に関するエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.BUSINESS_DATE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.BUSINESS_DATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 外部サービス関連の例外
class ExternalServiceException(ServiceException):
    """
    Exception raised when an external service integration error occurs.
    外部サービスとの連携に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.EXTERNAL_SERVICE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class MasterDataServiceException(ServiceException):
    """
    Exception raised when a master data service error occurs.
    マスターデータサービスとの連携に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.MASTER_DATA_SERVICE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.MASTER_DATA_SERVICE_ERROR),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class CartServiceException(ServiceException):
    """
    Exception raised when a cart service error occurs.
    カートサービスとの連携に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.CART_SERVICE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.CART_SERVICE_ERROR),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class JournalServiceException(ServiceException):
    """
    Exception raised when a journal service error occurs.
    ジャーナルサービスとの連携に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.JOURNAL_SERVICE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.JOURNAL_SERVICE_ERROR),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class ReportServiceException(ServiceException):
    """
    Exception raised when a report service error occurs.
    レポートサービスとの連携に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.REPORT_SERVICE_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.REPORT_SERVICE_ERROR),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class InternalErrorException(ServiceException):
    """
    Exception raised when an internal processing error occurs.
    内部処理でエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.INTERNAL_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.INTERNAL_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class UnexpectedErrorException(ServiceException):
    """
    Exception raised when an unexpected error occurs.
    想定外のエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            TerminalErrorCode.UNEXPECTED_ERROR,
            TerminalErrorMessage.get_message(TerminalErrorCode.UNEXPECTED_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
