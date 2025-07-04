# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.exceptions.base_exceptions import ServiceException
from .cart_error_codes import CartErrorCode, CartErrorMessage
from fastapi import status

"""
cart サービス固有の例外クラスを定義します
"""


# Cart固有のリポジトリ例外
class CartCannotCreateException(ServiceException):
    """
    Exception raised when a cart cannot be created.
    カートが作成できない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.CART_CREATE_ERROR,
            CartErrorMessage.get_message(CartErrorCode.CART_CREATE_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class CartNotFoundException(ServiceException):
    """
    Exception raised when a cart is not found.
    カートが見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.CART_NOT_FOUND,
            CartErrorMessage.get_message(CartErrorCode.CART_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class CartCannotSaveException(ServiceException):
    """
    Exception raised when a cart cannot be saved.
    カートが保存できない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.CART_SAVE_ERROR,
            CartErrorMessage.get_message(CartErrorCode.CART_SAVE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# 商品関連の例外
class ItemNotFoundException(ServiceException):
    """
    Exception raised when an item is not found.
    商品が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.ITEM_NOT_FOUND,
            CartErrorMessage.get_message(CartErrorCode.ITEM_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


# 残高関連の例外
class BalanceZeroException(ServiceException):
    """
    Exception raised when the balance is zero.
    残高がゼロの場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.BALANCE_ZERO,
            CartErrorMessage.get_message(CartErrorCode.BALANCE_ZERO),
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
        )


class BalanceMinusException(ServiceException):
    """
    Exception raised when the balance is minus.
    残高がマイナスの場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.BALANCE_MINUS,
            CartErrorMessage.get_message(CartErrorCode.BALANCE_MINUS),
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
        )


class BalanceGreaterThanZeroException(ServiceException):
    """
    Exception raised when the balance is greater than zero.
    残高がプラスの場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.BALANCE_GREATER_THAN_ZERO,
            CartErrorMessage.get_message(CartErrorCode.BALANCE_GREATER_THAN_ZERO),
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
        )


class DepositOverException(ServiceException):
    """
    Exception raised when the deposit amount is more than the balance.
    預かり金額が残高より多い場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.DEPOSIT_OVER,
            CartErrorMessage.get_message(CartErrorCode.DEPOSIT_OVER),
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
        )


# 端末関連の例外
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
            CartErrorCode.TERMINAL_STATUS_ERROR,
            CartErrorMessage.get_message(CartErrorCode.TERMINAL_STATUS_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class SignInOutException(ServiceException):
    """
    Exception raised when a sign in status error is received.
    サインイン/サインアウトのステータスエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.SIGN_IN_OUT_ERROR,
            CartErrorMessage.get_message(CartErrorCode.SIGN_IN_OUT_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ディスカウント関連の例外
class AmountLessThanDiscountException(ServiceException):
    """
    Exception raised when the item amount is less than the discount value.
    商品金額が値引金額より小さい場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.AMOUNT_LESS_THAN_DISCOUNT,
            CartErrorMessage.get_message(CartErrorCode.AMOUNT_LESS_THAN_DISCOUNT),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class BalanceLessThanDiscountException(ServiceException):
    """
    Exception raised when the cart balance is less than the discount value.
    カートの残高が値引金額より小さい場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.BALANCE_LESS_THAN_DISCOUNT,
            CartErrorMessage.get_message(CartErrorCode.BALANCE_LESS_THAN_DISCOUNT),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class DiscountAllocationException(ServiceException):
    """
    Exception raised when there is an error allocating discounts to line items.
    値引きの按分処理に失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.DISCOUNT_ALLOCATION_ERROR,
            CartErrorMessage.get_message(CartErrorCode.DISCOUNT_ALLOCATION_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class DiscountRestrictionException(ServiceException):
    """
    Exception raised when a discount is applied to a restricted item.
    値引禁止商品に値引が適用された場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.DISCOUNT_RESTRICTION,
            CartErrorMessage.get_message(CartErrorCode.DISCOUNT_RESTRICTION),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# その他のエラー
class ExternalServiceException(ServiceException):
    """
    Exception raised when an external service error occurs.
    外部サービスでエラーが発生した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.EXTERNAL_SERVICE_ERROR,
            CartErrorMessage.get_message(CartErrorCode.EXTERNAL_SERVICE_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            CartErrorCode.INTERNAL_ERROR,
            CartErrorMessage.get_message(CartErrorCode.INTERNAL_ERROR),
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
            CartErrorCode.UNEXPECTED_ERROR,
            CartErrorMessage.get_message(CartErrorCode.UNEXPECTED_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class AlreadyVoidedException(ServiceException):
    """
    Exception raised when a transaction has already been voided.
    既に取消処理が完了している取引に対して、再度取消を実行しようとした場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.ALREADY_VOIDED,
            CartErrorMessage.get_message(CartErrorCode.ALREADY_VOIDED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AlreadyRefundedException(ServiceException):
    """
    Exception raised when a transaction has already been refunded.
    既に返品処理が完了している取引に対して、再度返品を実行しようとした場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            CartErrorCode.ALREADY_REFUNDED,
            CartErrorMessage.get_message(CartErrorCode.ALREADY_REFUNDED),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
