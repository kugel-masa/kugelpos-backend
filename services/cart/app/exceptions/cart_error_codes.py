# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
カートサービス固有のエラーコードとエラーメッセージの定義
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class CartErrorCode:
    """
    カートサービス固有のエラーコード定義

    コード体系: XXYYZZ
    XX: エラーカテゴリ
    YY: サブカテゴリ
    ZZ: 詳細コード

    カートサービス用に予約された範囲:
    - 401xx: カート操作関連
    - 402xx: 商品登録関連
    - 403xx: 支払関連
    - 404xx: その他
    """

    # カート操作関連エラー (401xx)
    CART_CREATE_ERROR = "401001"  # カートの作成に失敗
    CART_NOT_FOUND = "401002"  # カートが見つからない
    CART_SAVE_ERROR = "401003"  # カートの保存に失敗

    # 商品登録関連エラー (402xx)
    ITEM_NOT_FOUND = "402001"  # 対象商品が見つからない
    AMOUNT_LESS_THAN_DISCOUNT = "402002"  # 商品金額が値引金額より小さい
    BALANCE_LESS_THAN_DISCOUNT = "402003"  # 残高が値引金額より小さい
    DISCOUNT_ALLOCATION_ERROR = "402004"  # 値引の按分処理に失敗
    DISCOUNT_RESTRICTION = "402005"  # 値引禁止商品

    # 支払関連エラー (403xx)
    BALANCE_ZERO = "403001"  # 残高が既にゼロ
    BALANCE_GREATER_THAN_ZERO = "403002"  # 残高が残っている
    BALANCE_MINUS = "403003"  # 残高がマイナス
    DEPOSIT_OVER = "403004"  # 預かり金額が残高より多い
    ALREADY_VOIDED = "403005"  # 既に取消済み
    ALREADY_REFUNDED = "403006"  # 既に返品済み

    # その他エラー (404xx)
    TERMINAL_STATUS_ERROR = "404001"  # 端末ステータスエラー
    SIGN_IN_OUT_ERROR = "404002"  # サインイン・サインアウトエラー
    EXTERNAL_SERVICE_ERROR = "404003"  # 外部サービスエラー
    INTERNAL_ERROR = "404004"  # 内部処理エラー
    UNEXPECTED_ERROR = "404999"  # 想定外のエラー


class CartErrorMessage:
    """
    カートサービス固有のエラーメッセージ定義
    """

    # 各言語のエラーメッセージ
    MESSAGES = {
        # 日本語のエラーメッセージ
        "ja": {
            # カート操作関連
            CartErrorCode.CART_CREATE_ERROR: "カートの作成に失敗しました",
            CartErrorCode.CART_NOT_FOUND: "カートが見つかりません",
            CartErrorCode.CART_SAVE_ERROR: "カートの保存に失敗しました",
            # 商品登録関連
            CartErrorCode.ITEM_NOT_FOUND: "対象商品が見つかりません",
            CartErrorCode.BALANCE_ZERO: "残高はすでに０です",
            CartErrorCode.BALANCE_GREATER_THAN_ZERO: "残高が残っています",
            CartErrorCode.BALANCE_MINUS: "残高がマイナスです",
            CartErrorCode.DEPOSIT_OVER: "預かり金額が残高より多いです",
            CartErrorCode.ALREADY_VOIDED: "この取引は既に取消済みです",
            CartErrorCode.ALREADY_REFUNDED: "この取引は既に返品済みです",
            # ディスカウント関連
            CartErrorCode.AMOUNT_LESS_THAN_DISCOUNT: "値引金額が商品金額より多いです",
            CartErrorCode.BALANCE_LESS_THAN_DISCOUNT: "値引金額が残高より多いです",
            CartErrorCode.DISCOUNT_ALLOCATION_ERROR: "値引の按分処理に失敗しました",
            CartErrorCode.DISCOUNT_RESTRICTION: "値引禁止商品です",
            # その他
            CartErrorCode.TERMINAL_STATUS_ERROR: "端末の状態を確認してください",
            CartErrorCode.SIGN_IN_OUT_ERROR: "担当者の登録状況を確認してください",
            CartErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスエラーが発生しました",
            CartErrorCode.INTERNAL_ERROR: "内部処理エラーが発生しました",
            CartErrorCode.UNEXPECTED_ERROR: "想定外のエラーが発生しました",
        },
        # 英語のエラーメッセージ
        "en": {
            # カート操作関連
            CartErrorCode.CART_CREATE_ERROR: "Cart creation failed",
            CartErrorCode.CART_NOT_FOUND: "Cart not found",
            CartErrorCode.CART_SAVE_ERROR: "Failed to save cart",
            # 商品登録関連
            CartErrorCode.ITEM_NOT_FOUND: "Item not found",
            CartErrorCode.BALANCE_ZERO: "Balance is already zero",
            CartErrorCode.BALANCE_GREATER_THAN_ZERO: "Balance is greater than zero",
            CartErrorCode.BALANCE_MINUS: "Balance is minus",
            CartErrorCode.DEPOSIT_OVER: "Deposit amount is more than balance",
            CartErrorCode.ALREADY_VOIDED: "This transaction has already been voided",
            CartErrorCode.ALREADY_REFUNDED: "This transaction has already been refunded",
            # ディスカウント関連
            CartErrorCode.AMOUNT_LESS_THAN_DISCOUNT: "Amount is less than discount",
            CartErrorCode.BALANCE_LESS_THAN_DISCOUNT: "Balance is less than discount",
            CartErrorCode.DISCOUNT_ALLOCATION_ERROR: "Discount allocation error",
            CartErrorCode.DISCOUNT_RESTRICTION: "Discount restriction",
            # その他
            CartErrorCode.TERMINAL_STATUS_ERROR: "Check terminal status",
            CartErrorCode.SIGN_IN_OUT_ERROR: "Check sign-in/out status",
            CartErrorCode.EXTERNAL_SERVICE_ERROR: "External service error occurred",
            CartErrorCode.INTERNAL_ERROR: "Internal processing error occurred",
            CartErrorCode.UNEXPECTED_ERROR: "Unexpected error occurred",
        },
    }

    # 共通エラーメッセージクラスを拡張
    @classmethod
    def extend_messages(cls):
        """
        共通エラーメッセージに、カートサービス固有のエラーメッセージを追加する
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


# アプリケーション起動時にカートサービス固有のエラーメッセージを共通エラーメッセージに追加
CartErrorMessage.extend_messages()
