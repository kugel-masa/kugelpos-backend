# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
reportサービス固有のエラーコードとエラーメッセージの定義
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class ReportErrorCode:
    """
    reportサービス固有のエラーコード定義

    コード体系: XXYYZZ
    XX: エラーカテゴリ
    YY: サブカテゴリ
    ZZ: 詳細コード

    reportサービス用に予約された範囲:
    - 412xx: レポート基本操作関連
    - 413xx: その他のレポート関連エラー
    """

    # レポート基本操作関連 (4120x)
    REPORT_NOT_FOUND = "412001"  # レポートが見つからない
    REPORT_VALIDATION_ERROR = "412002"  # レポートのバリデーションエラー
    REPORT_GENERATION_ERROR = "412003"  # レポート生成エラー
    REPORT_TYPE_ERROR = "412004"  # レポートタイプエラー
    REPORT_SCOPE_ERROR = "412005"  # レポートスコープエラー
    REPORT_DATE_ERROR = "412006"  # レポート日付エラー
    REPORT_DATA_ERROR = "412007"  # レポートデータエラー

    # レポート検証関連 (4121x)
    TERMINAL_NOT_CLOSED = "412101"  # 端末がクローズされていない
    LOGS_MISSING = "412102"  # ログが欠落している
    LOG_COUNT_MISMATCH = "412103"  # ログ数の不一致
    TRANSACTION_MISSING = "412104"  # トランザクションが欠落している
    CASH_IN_OUT_MISSING = "412105"  # 入出金ログが欠落している
    OPEN_CLOSE_LOG_MISSING = "412106"  # 開閉店ログが欠落している
    VERIFICATION_FAILED = "412107"  # 検証失敗

    # その他のレポート関連エラー (413xx)
    RECEIPT_GENERATION_ERROR = "413001"  # レシート生成エラー
    JOURNAL_GENERATION_ERROR = "413002"  # ジャーナル生成エラー
    EXPORT_ERROR = "413003"  # エクスポートエラー
    IMPORT_ERROR = "413004"  # インポートエラー
    DAILY_INFO_ERROR = "413005"  # 日次情報エラー
    EXTERNAL_SERVICE_ERROR = "413006"  # 外部サービスエラー


class ReportErrorMessage:
    """
    reportサービス固有のエラーメッセージ定義
    """

    # 各言語のエラーメッセージ
    MESSAGES = {
        # 日本語のエラーメッセージ
        "ja": {
            # レポート基本操作関連
            ReportErrorCode.REPORT_NOT_FOUND: "レポートが見つかりません",
            ReportErrorCode.REPORT_VALIDATION_ERROR: "レポートのバリデーションエラーが発生しました",
            ReportErrorCode.REPORT_GENERATION_ERROR: "レポートの生成に失敗しました",
            ReportErrorCode.REPORT_TYPE_ERROR: "不正なレポートタイプです",
            ReportErrorCode.REPORT_SCOPE_ERROR: "不正なレポートスコープです",
            ReportErrorCode.REPORT_DATE_ERROR: "レポート日付に問題があります",
            ReportErrorCode.REPORT_DATA_ERROR: "レポートデータに問題があります",
            # レポート検証関連
            ReportErrorCode.TERMINAL_NOT_CLOSED: "端末がクローズされていないため、レポートを生成できません",
            ReportErrorCode.LOGS_MISSING: "必要なログが欠落しています",
            ReportErrorCode.LOG_COUNT_MISMATCH: "ログの数が一致しません",
            ReportErrorCode.TRANSACTION_MISSING: "トランザクションログが欠落しています",
            ReportErrorCode.CASH_IN_OUT_MISSING: "入出金ログが欠落しています",
            ReportErrorCode.OPEN_CLOSE_LOG_MISSING: "開閉店ログが欠落しています",
            ReportErrorCode.VERIFICATION_FAILED: "データ検証に失敗しました",
            # その他のレポート関連エラー
            ReportErrorCode.RECEIPT_GENERATION_ERROR: "レシートの生成に失敗しました",
            ReportErrorCode.JOURNAL_GENERATION_ERROR: "ジャーナルの生成に失敗しました",
            ReportErrorCode.EXPORT_ERROR: "データのエクスポートに失敗しました",
            ReportErrorCode.IMPORT_ERROR: "データのインポートに失敗しました",
            ReportErrorCode.DAILY_INFO_ERROR: "日次情報の処理に失敗しました",
            ReportErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスエラーが発生しました",
        },
        # 英語のエラーメッセージ
        "en": {
            # レポート基本操作関連
            ReportErrorCode.REPORT_NOT_FOUND: "Report not found",
            ReportErrorCode.REPORT_VALIDATION_ERROR: "Report validation error occurred",
            ReportErrorCode.REPORT_GENERATION_ERROR: "Failed to generate report",
            ReportErrorCode.REPORT_TYPE_ERROR: "Invalid report type",
            ReportErrorCode.REPORT_SCOPE_ERROR: "Invalid report scope",
            ReportErrorCode.REPORT_DATE_ERROR: "Issue with report date",
            ReportErrorCode.REPORT_DATA_ERROR: "Issue with report data",
            # レポート検証関連
            ReportErrorCode.TERMINAL_NOT_CLOSED: "Terminal is not closed, cannot generate report",
            ReportErrorCode.LOGS_MISSING: "Required logs are missing",
            ReportErrorCode.LOG_COUNT_MISMATCH: "Log count mismatch",
            ReportErrorCode.TRANSACTION_MISSING: "Transaction logs are missing",
            ReportErrorCode.CASH_IN_OUT_MISSING: "Cash in/out logs are missing",
            ReportErrorCode.OPEN_CLOSE_LOG_MISSING: "Open/close logs are missing",
            ReportErrorCode.VERIFICATION_FAILED: "Data verification failed",
            # その他のレポート関連エラー
            ReportErrorCode.RECEIPT_GENERATION_ERROR: "Failed to generate receipt",
            ReportErrorCode.JOURNAL_GENERATION_ERROR: "Failed to generate journal",
            ReportErrorCode.EXPORT_ERROR: "Failed to export data",
            ReportErrorCode.IMPORT_ERROR: "Failed to import data",
            ReportErrorCode.DAILY_INFO_ERROR: "Failed to process daily information",
            ReportErrorCode.EXTERNAL_SERVICE_ERROR: "External service error occurred",
        },
    }

    # 共通エラーメッセージクラスを拡張
    @classmethod
    def extend_messages(cls):
        """
        共通エラーメッセージに、reportサービス固有のエラーメッセージを追加する
        """
        # 共通エラーメッセージに拡張
        CommonErrorMessage.MESSAGES["ja"].update(cls.MESSAGES["ja"])
        CommonErrorMessage.MESSAGES["en"].update(cls.MESSAGES["en"])

    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None):
        """
        エラーコードに対応するメッセージを取得する

        Args:
            error_code: エラーコード
            default_message: デフォルトメッセージ（コードに対応するメッセージがない場合）
            lang: 言語コード（"ja"または"en"、Noneの場合はデフォルト言語を使用）

        Returns:
            対応するエラーメッセージ
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


# アプリケーション起動時にreportサービス固有のエラーメッセージを共通エラーメッセージに追加
ReportErrorMessage.extend_messages()
