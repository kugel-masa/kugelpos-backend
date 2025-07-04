# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal service specific error codes and error messages definitions
This module defines error codes and corresponding error messages for the terminal service
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class TerminalErrorCode:
    """
    Terminal service specific error code definitions

    Code structure: XXYYZZ
    XX: Error category
    YY: Subcategory
    ZZ: Detailed code

    Ranges reserved for terminal service:
    - 406xx: Terminal operation related errors
    - 407xx: Other terminal related errors
    """

    # Terminal basic operation related (4060xx)
    TERMINAL_NOT_FOUND = "406001"  # Terminal not found
    TERMINAL_ALREADY_EXISTS = "406002"  # Terminal already exists
    TERMINAL_STATUS_ERROR = "406003"  # Terminal status error
    SIGN_IN_OUT_ERROR = "406004"  # Sign in/out error
    SIGN_IN_REQUIRED = "406005"  # Sign in required
    INVALID_CREDENTIALS = "406006"  # Invalid credentials
    TERMINAL_OPEN_ERROR = "406007"  # Terminal open error
    TERMINAL_CLOSE_ERROR = "406008"  # Terminal close error
    TERMINAL_ALREADY_OPENED = "406009"  # Terminal is already open
    TERMINAL_ALREADY_CLOSED = "406010"  # Terminal is already closed
    TERMINAL_BUSY = "406011"  # Terminal is busy (processing another operation)
    TERMINAL_FUNCTION_MODE_ERROR = "406012"  # Function mode change error
    TERMINAL_NOT_SIGNED_IN = "406013"  # Terminal is not signed in
    TERMINAL_ALREADY_SIGNED_IN = "406014"  # Terminal is already signed in
    TERMINAL_SIGNED_OUT = "406015"  # Terminal is signed out

    # Cash handling related (4061xx)
    CASH_IN_OUT_ERROR = "406101"  # Cash in/out general error
    CASH_AMOUNT_INVALID = "406102"  # Invalid cash amount
    CASH_DRAWER_CLOSED = "406103"  # Cash drawer is closed
    OVER_MAX_AMOUNT = "406104"  # Amount exceeds maximum limit
    UNDER_MIN_AMOUNT = "406105"  # Amount is below minimum limit
    PHYSICAL_AMOUNT_MISMATCH = "406106"  # Physical cash amount does not match recorded amount

    # Tenant related (4070xx)
    TENANT_NOT_FOUND = "407001"  # Tenant not found
    TENANT_ALREADY_EXISTS = "407002"  # Tenant already exists
    TENANT_UPDATE_ERROR = "407003"  # Tenant information update error
    TENANT_DELETE_ERROR = "407004"  # Tenant delete error
    TENANT_CONFIG_ERROR = "407005"  # Tenant configuration error
    TENANT_CREATE_ERROR = "407006"  # Tenant creation error

    # Store related (4071xx)
    STORE_NOT_FOUND = "407101"  # Store not found
    STORE_ALREADY_EXISTS = "407102"  # Store already exists
    STORE_UPDATE_ERROR = "407103"  # Store information update error
    STORE_DELETE_ERROR = "407104"  # Store delete error
    STORE_CONFIG_ERROR = "407105"  # Store configuration error
    BUSINESS_DATE_ERROR = "407106"  # Business date related error

    # External service related (4072xx)
    EXTERNAL_SERVICE_ERROR = "407201"  # External service integration error
    MASTER_DATA_SERVICE_ERROR = "407202"  # Master data service error
    CART_SERVICE_ERROR = "407203"  # Cart service error
    JOURNAL_SERVICE_ERROR = "407204"  # Journal service error
    REPORT_SERVICE_ERROR = "407205"  # Report service error

    # Other errors (4073xx)
    INTERNAL_ERROR = "407301"  # 内部処理エラー
    UNEXPECTED_ERROR = "407399"  # 想定外のエラー


class TerminalErrorMessage:
    """
    Terminal service specific error message definitions

    This class defines error messages corresponding to the error codes
    defined in TerminalErrorCode class. Messages are provided in multiple
    languages (currently Japanese and English).
    """

    # Error messages for each language
    MESSAGES = {
        # Japanese error messages
        "ja": {
            # Terminal related
            TerminalErrorCode.TERMINAL_NOT_FOUND: "端末が見つかりません",
            TerminalErrorCode.TERMINAL_ALREADY_EXISTS: "端末はすでに存在します",
            TerminalErrorCode.TERMINAL_STATUS_ERROR: "端末の状態を確認してください",
            TerminalErrorCode.SIGN_IN_OUT_ERROR: "担当者の登録状況を確認してください",
            TerminalErrorCode.SIGN_IN_REQUIRED: "サインインが必要です",
            TerminalErrorCode.INVALID_CREDENTIALS: "認証情報が無効です",
            TerminalErrorCode.TERMINAL_OPEN_ERROR: "端末オープン処理に失敗しました",
            TerminalErrorCode.TERMINAL_CLOSE_ERROR: "端末クローズ処理に失敗しました",
            TerminalErrorCode.TERMINAL_ALREADY_OPENED: "端末はすでにオープン状態です",
            TerminalErrorCode.TERMINAL_ALREADY_CLOSED: "端末はすでにクローズ状態です",
            TerminalErrorCode.TERMINAL_BUSY: "端末が他の処理を実行中です",
            TerminalErrorCode.TERMINAL_FUNCTION_MODE_ERROR: "機能モード変更に失敗しました",
            TerminalErrorCode.TERMINAL_NOT_SIGNED_IN: "端末にサインインしていません",
            TerminalErrorCode.TERMINAL_ALREADY_SIGNED_IN: "すでにサインインしています",
            TerminalErrorCode.TERMINAL_SIGNED_OUT: "サインアウトされています",
            # Cash handling related
            TerminalErrorCode.CASH_IN_OUT_ERROR: "入出金処理に失敗しました",
            TerminalErrorCode.CASH_AMOUNT_INVALID: "入力金額が不正です",
            TerminalErrorCode.CASH_DRAWER_CLOSED: "キャッシュドロワーがクローズ状態です",
            TerminalErrorCode.OVER_MAX_AMOUNT: "最大金額を超過しています",
            TerminalErrorCode.UNDER_MIN_AMOUNT: "最小金額を下回っています",
            TerminalErrorCode.PHYSICAL_AMOUNT_MISMATCH: "実在高と記録金額が一致しません",
            # Tenant related
            TerminalErrorCode.TENANT_NOT_FOUND: "テナントが見つかりません",
            TerminalErrorCode.TENANT_ALREADY_EXISTS: "テナントはすでに存在します",
            TerminalErrorCode.TENANT_UPDATE_ERROR: "テナント情報の更新に失敗しました",
            TerminalErrorCode.TENANT_DELETE_ERROR: "テナントの削除に失敗しました",
            TerminalErrorCode.TENANT_CONFIG_ERROR: "テナント設定に問題があります",
            TerminalErrorCode.TENANT_CREATE_ERROR: "テナントの作成に失敗しました",
            # Store related
            TerminalErrorCode.STORE_NOT_FOUND: "店舗が見つかりません",
            TerminalErrorCode.STORE_ALREADY_EXISTS: "店舗はすでに存在します",
            TerminalErrorCode.STORE_UPDATE_ERROR: "店舗情報の更新に失敗しました",
            TerminalErrorCode.STORE_DELETE_ERROR: "店舗の削除に失敗しました",
            TerminalErrorCode.STORE_CONFIG_ERROR: "店舗設定に問題があります",
            TerminalErrorCode.BUSINESS_DATE_ERROR: "営業日の設定に問題があります",
            # External service related
            TerminalErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスとの連携に失敗しました",
            TerminalErrorCode.MASTER_DATA_SERVICE_ERROR: "マスターデータサービスとの連携に失敗しました",
            TerminalErrorCode.CART_SERVICE_ERROR: "カートサービスとの連携に失敗しました",
            TerminalErrorCode.JOURNAL_SERVICE_ERROR: "ジャーナルサービスとの連携に失敗しました",
            TerminalErrorCode.REPORT_SERVICE_ERROR: "レポートサービスとの連携に失敗しました",
            TerminalErrorCode.INTERNAL_ERROR: "内部処理エラーが発生しました",
            TerminalErrorCode.UNEXPECTED_ERROR: "想定外のエラーが発生しました",
        },
        # English error messages
        "en": {
            # Terminal related
            TerminalErrorCode.TERMINAL_NOT_FOUND: "Terminal not found",
            TerminalErrorCode.TERMINAL_ALREADY_EXISTS: "Terminal already exists",
            TerminalErrorCode.TERMINAL_STATUS_ERROR: "Terminal status error occurred",
            TerminalErrorCode.SIGN_IN_OUT_ERROR: "Sign in/out error occurred",
            TerminalErrorCode.SIGN_IN_REQUIRED: "Sign in is required",
            TerminalErrorCode.INVALID_CREDENTIALS: "Invalid credentials",
            TerminalErrorCode.TERMINAL_OPEN_ERROR: "Failed to open the terminal",
            TerminalErrorCode.TERMINAL_CLOSE_ERROR: "Failed to close the terminal",
            TerminalErrorCode.TERMINAL_ALREADY_OPENED: "Terminal is already opened",
            TerminalErrorCode.TERMINAL_ALREADY_CLOSED: "Terminal is already closed",
            TerminalErrorCode.TERMINAL_BUSY: "Terminal is busy processing another operation",
            TerminalErrorCode.TERMINAL_FUNCTION_MODE_ERROR: "Failed to change function mode",
            TerminalErrorCode.TERMINAL_NOT_SIGNED_IN: "Terminal is not signed in",
            TerminalErrorCode.TERMINAL_ALREADY_SIGNED_IN: "Already signed in",
            TerminalErrorCode.TERMINAL_SIGNED_OUT: "Terminal is signed out",
            # Cash handling related
            TerminalErrorCode.CASH_IN_OUT_ERROR: "Cash in/out operation failed",
            TerminalErrorCode.CASH_AMOUNT_INVALID: "Invalid amount entered",
            TerminalErrorCode.CASH_DRAWER_CLOSED: "Cash drawer is closed",
            TerminalErrorCode.OVER_MAX_AMOUNT: "Amount exceeds maximum limit",
            TerminalErrorCode.UNDER_MIN_AMOUNT: "Amount is below minimum limit",
            TerminalErrorCode.PHYSICAL_AMOUNT_MISMATCH: "Physical amount does not match recorded amount",
            # Tenant related
            TerminalErrorCode.TENANT_NOT_FOUND: "Tenant not found",
            TerminalErrorCode.TENANT_ALREADY_EXISTS: "Tenant already exists",
            TerminalErrorCode.TENANT_UPDATE_ERROR: "Failed to update tenant information",
            TerminalErrorCode.TENANT_DELETE_ERROR: "Failed to delete tenant",
            TerminalErrorCode.TENANT_CONFIG_ERROR: "Tenant configuration error",
            TerminalErrorCode.TENANT_CREATE_ERROR: "Failed to create tenant",
            # Store related
            TerminalErrorCode.STORE_NOT_FOUND: "Store not found",
            TerminalErrorCode.STORE_ALREADY_EXISTS: "Store already exists",
            TerminalErrorCode.STORE_UPDATE_ERROR: "Failed to update store information",
            TerminalErrorCode.STORE_DELETE_ERROR: "Failed to delete store",
            TerminalErrorCode.STORE_CONFIG_ERROR: "Store configuration error",
            TerminalErrorCode.BUSINESS_DATE_ERROR: "Business date error",
            # External service related
            TerminalErrorCode.EXTERNAL_SERVICE_ERROR: "External service integration error",
            TerminalErrorCode.MASTER_DATA_SERVICE_ERROR: "Master data service error",
            TerminalErrorCode.CART_SERVICE_ERROR: "Cart service error",
            TerminalErrorCode.JOURNAL_SERVICE_ERROR: "Journal service error",
            TerminalErrorCode.REPORT_SERVICE_ERROR: "Report service error",
            TerminalErrorCode.INTERNAL_ERROR: "Internal processing error occurred",
            TerminalErrorCode.UNEXPECTED_ERROR: "Unexpected error occurred",
        },
    }

    # Extend common error messages with terminal-specific ones
    @classmethod
    def extend_messages(cls):
        """
        Extend the common error messages with terminal service-specific error messages

        This method adds terminal-specific error messages to the common error message
        dictionary, making them available throughout the application.
        """
        # Update common error messages with terminal-specific ones
        CommonErrorMessage.MESSAGES["ja"].update(cls.MESSAGES["ja"])
        CommonErrorMessage.MESSAGES["en"].update(cls.MESSAGES["en"])

    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None):
        """
        Get the message corresponding to an error code

        Args:
            error_code: The error code to get the message for
            default_message: The default message to return if no message is found for the code
            lang: Language code ("ja" or "en", None uses the default language)

        Returns:
            The error message corresponding to the error code in the specified language

        This method follows a fallback strategy:
        1. Try to get the message in the specified language
        2. If not found and a default message is provided, use that
        3. Otherwise, try to get the message in the default language
        4. If still not found, use a general default error message
        """
        # Set default language if none specified
        if lang is None:
            lang = CommonErrorMessage.DEFAULT_LANGUAGE

        # Use default language if unsupported language is specified
        if lang not in CommonErrorMessage.SUPPORTED_LANGUAGES:
            lang = CommonErrorMessage.DEFAULT_LANGUAGE

        # Try to get the message in the specified language
        message = cls.MESSAGES.get(lang, {}).get(error_code)

        # If message not found
        if message is None:
            # Use provided default message if available
            if default_message:
                return default_message

            # Try with default language if different from specified language
            if lang != CommonErrorMessage.DEFAULT_LANGUAGE:
                message = cls.MESSAGES.get(CommonErrorMessage.DEFAULT_LANGUAGE, {}).get(error_code)

            # If still not found, use a general default error message
            if message is None:
                return CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(
                    lang, CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(CommonErrorMessage.DEFAULT_LANGUAGE)
                )

        return message


# Extend common error messages with terminal-specific ones on application startup
TerminalErrorMessage.extend_messages()
