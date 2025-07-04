# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
stockサービス固有のエラーコードとエラーメッセージの定義
"""
from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage


class StockErrorCode:
    """
    stockサービス固有のエラーコード定義

    コード体系: XXYYZZ
    XX: エラーカテゴリ
    YY: サブカテゴリ
    ZZ: 詳細コード

    stockサービス用に予約された範囲:
    - 414xx: 在庫基本操作関連
    - 415xx: その他の在庫関連エラー
    """

    # 在庫基本操作関連 (4140xx)
    STOCK_NOT_FOUND = "414001"  # 在庫が見つからない
    INSUFFICIENT_STOCK = "414002"  # 在庫不足
    STOCK_VALIDATION_ERROR = "414003"  # 在庫のバリデーションエラー
    STOCK_ACCESS_DENIED = "414004"  # 在庫へのアクセス拒否
    STOCK_DATABASE_ERROR = "414005"  # 在庫データベースエラー

    # 在庫更新操作関連 (4141xx)
    STOCK_UPDATE_FAILED = "414101"  # 在庫更新失敗
    STOCK_UPDATE_VALIDATION_ERROR = "414102"  # 在庫更新のバリデーションエラー
    STOCK_UPDATE_CONFLICT = "414103"  # 在庫更新の競合
    STOCK_UPDATE_NOT_FOUND = "414104"  # 更新対象の在庫が見つからない

    # スナップショット操作関連 (4142xx)
    SNAPSHOT_CREATION_FAILED = "414201"  # スナップショット作成失敗
    SNAPSHOT_NOT_FOUND = "414202"  # スナップショットが見つからない
    SNAPSHOT_VALIDATION_ERROR = "414203"  # スナップショットのバリデーションエラー
    SNAPSHOT_DELETION_FAILED = "414204"  # スナップショット削除失敗

    # 外部サービス操作関連 (4143xx)
    EXTERNAL_SERVICE_ERROR = "414301"  # 外部サービスエラー
    PUBSUB_ERROR = "414302"  # Pub/Subエラー
    STATE_STORE_ERROR = "414303"  # ステートストアエラー

    # トランザクション処理関連 (4144xx)
    TRANSACTION_PROCESSING_ERROR = "414401"  # トランザクション処理エラー
    TRANSACTION_VALIDATION_ERROR = "414402"  # トランザクションバリデーションエラー
    TRANSACTION_DUPLICATE = "414403"  # 重複トランザクション


class StockErrorMessage:
    """
    stockサービス固有のエラーメッセージ定義
    """

    # 各言語のエラーメッセージ
    MESSAGES = {
        # 日本語のエラーメッセージ
        "ja": {
            # 在庫基本操作関連
            StockErrorCode.STOCK_NOT_FOUND: "在庫情報が見つかりません",
            StockErrorCode.INSUFFICIENT_STOCK: "在庫が不足しています",
            StockErrorCode.STOCK_VALIDATION_ERROR: "在庫情報のバリデーションエラーが発生しました",
            StockErrorCode.STOCK_ACCESS_DENIED: "在庫情報へのアクセスが拒否されました",
            StockErrorCode.STOCK_DATABASE_ERROR: "在庫データベースエラーが発生しました",
            # 在庫更新操作関連
            StockErrorCode.STOCK_UPDATE_FAILED: "在庫の更新に失敗しました",
            StockErrorCode.STOCK_UPDATE_VALIDATION_ERROR: "在庫更新のバリデーションエラーが発生しました",
            StockErrorCode.STOCK_UPDATE_CONFLICT: "在庫更新で競合が発生しました",
            StockErrorCode.STOCK_UPDATE_NOT_FOUND: "更新対象の在庫が見つかりません",
            # スナップショット操作関連
            StockErrorCode.SNAPSHOT_CREATION_FAILED: "スナップショットの作成に失敗しました",
            StockErrorCode.SNAPSHOT_NOT_FOUND: "スナップショットが見つかりません",
            StockErrorCode.SNAPSHOT_VALIDATION_ERROR: "スナップショットのバリデーションエラーが発生しました",
            StockErrorCode.SNAPSHOT_DELETION_FAILED: "スナップショットの削除に失敗しました",
            # 外部サービス操作関連
            StockErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスエラーが発生しました",
            StockErrorCode.PUBSUB_ERROR: "Pub/Subエラーが発生しました",
            StockErrorCode.STATE_STORE_ERROR: "ステートストアエラーが発生しました",
            # トランザクション処理関連
            StockErrorCode.TRANSACTION_PROCESSING_ERROR: "トランザクション処理エラーが発生しました",
            StockErrorCode.TRANSACTION_VALIDATION_ERROR: "トランザクションのバリデーションエラーが発生しました",
            StockErrorCode.TRANSACTION_DUPLICATE: "重複したトランザクションです",
        },
        # 英語のエラーメッセージ
        "en": {
            # 在庫基本操作関連
            StockErrorCode.STOCK_NOT_FOUND: "Stock not found",
            StockErrorCode.INSUFFICIENT_STOCK: "Insufficient stock",
            StockErrorCode.STOCK_VALIDATION_ERROR: "Stock validation error occurred",
            StockErrorCode.STOCK_ACCESS_DENIED: "Access to stock denied",
            StockErrorCode.STOCK_DATABASE_ERROR: "Stock database error occurred",
            # 在庫更新操作関連
            StockErrorCode.STOCK_UPDATE_FAILED: "Failed to update stock",
            StockErrorCode.STOCK_UPDATE_VALIDATION_ERROR: "Stock update validation error occurred",
            StockErrorCode.STOCK_UPDATE_CONFLICT: "Stock update conflict occurred",
            StockErrorCode.STOCK_UPDATE_NOT_FOUND: "Stock to update not found",
            # スナップショット操作関連
            StockErrorCode.SNAPSHOT_CREATION_FAILED: "Failed to create snapshot",
            StockErrorCode.SNAPSHOT_NOT_FOUND: "Snapshot not found",
            StockErrorCode.SNAPSHOT_VALIDATION_ERROR: "Snapshot validation error occurred",
            StockErrorCode.SNAPSHOT_DELETION_FAILED: "Failed to delete snapshot",
            # 外部サービス操作関連
            StockErrorCode.EXTERNAL_SERVICE_ERROR: "External service error occurred",
            StockErrorCode.PUBSUB_ERROR: "Pub/Sub error occurred",
            StockErrorCode.STATE_STORE_ERROR: "State store error occurred",
            # トランザクション処理関連
            StockErrorCode.TRANSACTION_PROCESSING_ERROR: "Transaction processing error occurred",
            StockErrorCode.TRANSACTION_VALIDATION_ERROR: "Transaction validation error occurred",
            StockErrorCode.TRANSACTION_DUPLICATE: "Duplicate transaction",
        },
    }


def extend_messages():
    """
    共通エラーメッセージとマージ
    """
    import copy

    merged_messages = copy.deepcopy(CommonErrorMessage.MESSAGES)

    # 各言語のメッセージをマージ
    for lang, messages in StockErrorMessage.MESSAGES.items():
        if lang not in merged_messages:
            merged_messages[lang] = {}
        merged_messages[lang].update(messages)

    return merged_messages


# エラーメッセージ取得ヘルパー関数
def get_message(error_code: str, lang: str = "ja") -> str:
    """
    エラーコードに対応するメッセージを取得

    Args:
        error_code: エラーコード
        lang: 言語コード (ja/en)

    Returns:
        エラーメッセージ
    """
    messages = extend_messages()
    if lang in messages and error_code in messages[lang]:
        return messages[lang][error_code]

    # デフォルトメッセージ
    return messages.get("ja", {}).get(error_code, f"エラーが発生しました (Code: {error_code})")
