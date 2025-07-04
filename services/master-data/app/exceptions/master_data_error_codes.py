# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
master-dataサービス固有のエラーコードとエラーメッセージの定義
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class MasterDataErrorCode:
    """
    master-dataサービス固有のエラーコード定義

    コード体系: XXYYZZ
    XX: エラーカテゴリ
    YY: サブカテゴリ
    ZZ: 詳細コード

    master-dataサービス用に予約された範囲:
    - 405xx: マスターデータ関連
    """

    # マスターデータ基本エラー (405xx)
    MASTER_DATA_VALIDATION_ERROR = "405001"  # マスターデータ検証エラー
    MASTER_DATA_NOT_FOUND = "405002"  # マスターデータが見つからない
    MASTER_DATA_ALREADY_EXISTS = "405003"  # マスターデータがすでに存在する
    MASTER_DATA_CANNOT_CREATE = "405004"  # マスターデータを作成できない
    MASTER_DATA_CANNOT_UPDATE = "405005"  # マスターデータを更新できない
    MASTER_DATA_CANNOT_DELETE = "405006"  # マスターデータを削除できない

    # 商品マスター関連エラー (4051x)
    PRODUCT_NOT_FOUND = "405101"  # 商品が見つからない
    PRODUCT_CODE_DUPLICATE = "405102"  # 商品コードが重複している
    PRODUCT_INVALID_PRICE = "405103"  # 商品の価格が無効
    PRODUCT_INVALID_TAX_RATE = "405104"  # 商品の税率が無効

    # 価格マスター関連エラー (4052x)
    PRICE_NOT_FOUND = "405201"  # 価格が見つからない
    PRICE_INVALID_AMOUNT = "405202"  # 価格の金額が無効
    PRICE_INVALID_DATE_RANGE = "405203"  # 価格の適用期間が無効

    # 顧客マスター関連エラー (4053x)
    CUSTOMER_NOT_FOUND = "405301"  # 顧客が見つからない
    CUSTOMER_ID_DUPLICATE = "405302"  # 顧客IDが重複している

    # 店舗マスター関連エラー (4054x)
    STORE_NOT_FOUND = "405401"  # 店舗が見つからない
    STORE_CODE_DUPLICATE = "405402"  # 店舗コードが重複している

    # 部門マスター関連エラー (4055x)
    DEPARTMENT_NOT_FOUND = "405501"  # 部門が見つからない
    DEPARTMENT_CODE_DUPLICATE = "405502"  # 部門コードが重複している


class MasterDataErrorMessage:
    """
    master-dataサービス固有のエラーメッセージ定義
    """

    # 各言語のエラーメッセージ
    MESSAGES = {
        # 日本語のエラーメッセージ
        "ja": {
            # マスターデータ基本エラー
            MasterDataErrorCode.MASTER_DATA_VALIDATION_ERROR: "マスターデータ検証エラーが発生しました",
            MasterDataErrorCode.MASTER_DATA_NOT_FOUND: "マスターデータが見つかりません",
            MasterDataErrorCode.MASTER_DATA_ALREADY_EXISTS: "マスターデータがすでに存在します",
            MasterDataErrorCode.MASTER_DATA_CANNOT_CREATE: "マスターデータを作成できません",
            MasterDataErrorCode.MASTER_DATA_CANNOT_UPDATE: "マスターデータを更新できません",
            MasterDataErrorCode.MASTER_DATA_CANNOT_DELETE: "マスターデータを削除できません",
            # 商品マスター関連エラー
            MasterDataErrorCode.PRODUCT_NOT_FOUND: "商品が見つかりません",
            MasterDataErrorCode.PRODUCT_CODE_DUPLICATE: "商品コードが重複しています",
            MasterDataErrorCode.PRODUCT_INVALID_PRICE: "商品の価格が無効です",
            MasterDataErrorCode.PRODUCT_INVALID_TAX_RATE: "商品の税率が無効です",
            # 価格マスター関連エラー
            MasterDataErrorCode.PRICE_NOT_FOUND: "価格が見つかりません",
            MasterDataErrorCode.PRICE_INVALID_AMOUNT: "価格の金額が無効です",
            MasterDataErrorCode.PRICE_INVALID_DATE_RANGE: "価格の適用期間が無効です",
            # 顧客マスター関連エラー
            MasterDataErrorCode.CUSTOMER_NOT_FOUND: "顧客が見つかりません",
            MasterDataErrorCode.CUSTOMER_ID_DUPLICATE: "顧客IDが重複しています",
            # 店舗マスター関連エラー
            MasterDataErrorCode.STORE_NOT_FOUND: "店舗が見つかりません",
            MasterDataErrorCode.STORE_CODE_DUPLICATE: "店舗コードが重複しています",
            # 部門マスター関連エラー
            MasterDataErrorCode.DEPARTMENT_NOT_FOUND: "部門が見つかりません",
            MasterDataErrorCode.DEPARTMENT_CODE_DUPLICATE: "部門コードが重複しています",
        },
        # 英語のエラーメッセージ
        "en": {
            # マスターデータ基本エラー
            MasterDataErrorCode.MASTER_DATA_VALIDATION_ERROR: "Master data validation error occurred",
            MasterDataErrorCode.MASTER_DATA_NOT_FOUND: "Master data not found",
            MasterDataErrorCode.MASTER_DATA_ALREADY_EXISTS: "Master data already exists",
            MasterDataErrorCode.MASTER_DATA_CANNOT_CREATE: "Cannot create master data",
            MasterDataErrorCode.MASTER_DATA_CANNOT_UPDATE: "Cannot update master data",
            MasterDataErrorCode.MASTER_DATA_CANNOT_DELETE: "Cannot delete master data",
            # 商品マスター関連エラー
            MasterDataErrorCode.PRODUCT_NOT_FOUND: "Product not found",
            MasterDataErrorCode.PRODUCT_CODE_DUPLICATE: "Product code is duplicate",
            MasterDataErrorCode.PRODUCT_INVALID_PRICE: "Product price is invalid",
            MasterDataErrorCode.PRODUCT_INVALID_TAX_RATE: "Product tax rate is invalid",
            # 価格マスター関連エラー
            MasterDataErrorCode.PRICE_NOT_FOUND: "Price not found",
            MasterDataErrorCode.PRICE_INVALID_AMOUNT: "Price amount is invalid",
            MasterDataErrorCode.PRICE_INVALID_DATE_RANGE: "Price date range is invalid",
            # 顧客マスター関連エラー
            MasterDataErrorCode.CUSTOMER_NOT_FOUND: "Customer not found",
            MasterDataErrorCode.CUSTOMER_ID_DUPLICATE: "Customer ID is duplicate",
            # 店舗マスター関連エラー
            MasterDataErrorCode.STORE_NOT_FOUND: "Store not found",
            MasterDataErrorCode.STORE_CODE_DUPLICATE: "Store code is duplicate",
            # 部門マスター関連エラー
            MasterDataErrorCode.DEPARTMENT_NOT_FOUND: "Department not found",
            MasterDataErrorCode.DEPARTMENT_CODE_DUPLICATE: "Department code is duplicate",
        },
    }

    # 共通エラーメッセージクラスを拡張
    @classmethod
    def extend_messages(cls):
        """
        共通エラーメッセージに、master-dataサービス固有のエラーメッセージを追加する
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


# アプリケーション起動時にmaster-dataサービス固有のエラーメッセージを共通エラーメッセージに追加
MasterDataErrorMessage.extend_messages()
