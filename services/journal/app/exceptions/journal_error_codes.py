# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Definition of error codes and error messages specific to the journal service
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class JournalErrorCode:
    """
    Definition of error codes specific to the journal service

    Code format: XXYYZZ
    XX: Error category
    YY: Subcategory
    ZZ: Detail code

    Reserved range for journal service:
    - 410xx: Journal basic operation related
    - 411xx: Other journal related errors
    """

    # ジャーナル基本操作関連 (4100x)
    JOURNAL_NOT_FOUND = "410001"  # ジャーナルが見つからない
    JOURNAL_VALIDATION_ERROR = "410002"  # ジャーナルのバリデーションエラー
    JOURNAL_CREATION_ERROR = "410003"  # ジャーナル作成エラー
    JOURNAL_QUERY_ERROR = "410004"  # ジャーナル検索エラー
    JOURNAL_FORMAT_ERROR = "410005"  # ジャーナルフォーマットエラー
    JOURNAL_DATE_ERROR = "410006"  # ジャーナル日付エラー
    JOURNAL_DATA_ERROR = "410007"  # ジャーナルデータエラー

    # ジャーナル検証関連 (4101x)
    TERMINAL_NOT_FOUND = "410101"  # 端末が見つからない
    STORE_NOT_FOUND = "410102"  # 店舗が見つからない
    LOGS_MISSING = "410103"  # ログが欠落している
    LOG_SEQUENCE_ERROR = "410104"  # ログシーケンスエラー
    TRANSACTION_VALIDATION_ERROR = "410105"  # トランザクション検証エラー

    # その他のジャーナル関連エラー (411xx)
    RECEIPT_GENERATION_ERROR = "411001"  # レシート生成エラー
    JOURNAL_TEXT_ERROR = "411002"  # ジャーナルテキスト生成エラー
    EXPORT_ERROR = "411003"  # エクスポートエラー
    IMPORT_ERROR = "411004"  # インポートエラー
    TRANSACTION_RECEIPT_ERROR = "411005"  # トランザクションレシートエラー
    EXTERNAL_SERVICE_ERROR = "411006"  # 外部サービスエラー


class JournalErrorMessage:
    """
    Definition of error messages specific to the journal service
    """

    # Error messages for each language
    MESSAGES = {
        # Japanese error messages
        "ja": {
            # Journal basic operation related
            JournalErrorCode.JOURNAL_NOT_FOUND: "ジャーナルが見つかりません",
            JournalErrorCode.JOURNAL_VALIDATION_ERROR: "ジャーナルのバリデーションエラーが発生しました",
            JournalErrorCode.JOURNAL_CREATION_ERROR: "ジャーナルの作成に失敗しました",
            JournalErrorCode.JOURNAL_QUERY_ERROR: "ジャーナルの検索に失敗しました",
            JournalErrorCode.JOURNAL_FORMAT_ERROR: "ジャーナルの形式が不正です",
            JournalErrorCode.JOURNAL_DATE_ERROR: "ジャーナルの日付に問題があります",
            JournalErrorCode.JOURNAL_DATA_ERROR: "ジャーナルデータに問題があります",
            # Journal validation related
            JournalErrorCode.TERMINAL_NOT_FOUND: "端末が見つかりません",
            JournalErrorCode.STORE_NOT_FOUND: "店舗が見つかりません",
            JournalErrorCode.LOGS_MISSING: "必要なログが欠落しています",
            JournalErrorCode.LOG_SEQUENCE_ERROR: "ログシーケンスに問題があります",
            JournalErrorCode.TRANSACTION_VALIDATION_ERROR: "トランザクションの検証に失敗しました",
            # Other journal related errors
            JournalErrorCode.RECEIPT_GENERATION_ERROR: "レシートの生成に失敗しました",
            JournalErrorCode.JOURNAL_TEXT_ERROR: "ジャーナルテキストの生成に失敗しました",
            JournalErrorCode.EXPORT_ERROR: "データのエクスポートに失敗しました",
            JournalErrorCode.IMPORT_ERROR: "データのインポートに失敗しました",
            JournalErrorCode.TRANSACTION_RECEIPT_ERROR: "トランザクションレシートに問題があります",
            JournalErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスエラーが発生しました",
        },
        # English error messages
        "en": {
            # Journal basic operation related
            JournalErrorCode.JOURNAL_NOT_FOUND: "Journal not found",
            JournalErrorCode.JOURNAL_VALIDATION_ERROR: "Journal validation error occurred",
            JournalErrorCode.JOURNAL_CREATION_ERROR: "Failed to create journal",
            JournalErrorCode.JOURNAL_QUERY_ERROR: "Failed to query journals",
            JournalErrorCode.JOURNAL_FORMAT_ERROR: "Invalid journal format",
            JournalErrorCode.JOURNAL_DATE_ERROR: "Issue with journal date",
            JournalErrorCode.JOURNAL_DATA_ERROR: "Issue with journal data",
            # Journal validation related
            JournalErrorCode.TERMINAL_NOT_FOUND: "Terminal not found",
            JournalErrorCode.STORE_NOT_FOUND: "Store not found",
            JournalErrorCode.LOGS_MISSING: "Required logs are missing",
            JournalErrorCode.LOG_SEQUENCE_ERROR: "Issue with log sequence",
            JournalErrorCode.TRANSACTION_VALIDATION_ERROR: "Transaction validation failed",
            # Other journal related errors
            JournalErrorCode.RECEIPT_GENERATION_ERROR: "Failed to generate receipt",
            JournalErrorCode.JOURNAL_TEXT_ERROR: "Failed to generate journal text",
            JournalErrorCode.EXPORT_ERROR: "Failed to export data",
            JournalErrorCode.IMPORT_ERROR: "Failed to import data",
            JournalErrorCode.TRANSACTION_RECEIPT_ERROR: "Issue with transaction receipt",
            JournalErrorCode.EXTERNAL_SERVICE_ERROR: "External service error occurred",
        },
    }

    # 共通エラーメッセージクラスを拡張
    @classmethod
    def extend_messages(cls):
        """
        Add journal service specific error messages to the common error messages at application startup
        """
        # 共通エラーメッセージに拡張
        CommonErrorMessage.MESSAGES["ja"].update(cls.MESSAGES["ja"])
        CommonErrorMessage.MESSAGES["en"].update(cls.MESSAGES["en"])

    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None):
        """
        Get the message corresponding to the error code

        Args:
            error_code: Error code
            default_message: Default message (if there is no message for the code)
            lang: Language code ("ja" or "en", if None, use default language)

        Returns:
            Corresponding error message
        """
        # デフォルト言語の設定
        if lang is None:
            lang = CommonErrorMessage.DEFAULT_LANGUAGE

        # サポートされていない言語の場合はデフォルト言語を使用
        if lang not in CommonErrorMessage.SUPPORTED_LANGUAGES:
            lang = CommonErrorMessage.DEFAULT_LANGUAGE

        # 指定された言語でエラーコードに対応するメッセージを取得
        message = cls.MESSAGES.get(lang, {}).get(error_code)

        # メッセージが見つからない場合
        if message is None:
            # 指定されたデフォルトメッセージがある場合はそれを使用
            if default_message:
                return default_message

            # デフォルト言語で再試行
            if lang != CommonErrorMessage.DEFAULT_LANGUAGE:
                message = cls.MESSAGES.get(CommonErrorMessage.DEFAULT_LANGUAGE, {}).get(error_code)

            # それでも見つからない場合はデフォルトエラーメッセージを使用
            if message is None:
                return CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(
                    lang, CommonErrorMessage.DEFAULT_ERROR_MESSAGES.get(CommonErrorMessage.DEFAULT_LANGUAGE)
                )

        return message


# アプリケーション起動時にjournalサービス固有のエラーメッセージを共通エラーメッセージに追加
JournalErrorMessage.extend_messages()
