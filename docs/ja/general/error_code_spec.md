# Kugelpos エラーコード仕様

## 概要

Kugelposシステムでは、統一されたエラーコード体系により、サービス横断での一貫したエラーハンドリングを実現しています。エラーコードは6桁の数値（XXYYZZ）形式で、多言語対応も含めて実装されています。

## エラーコード構造（XXYYZZ）

### XX: エラーカテゴリ

| カテゴリ | コード範囲 | 説明 |
|---------|------------|------|
| 一般エラー | 10XXXX | 一般的なエラー |
| 認証・認可 | 20XXXX | 認証・認可エラー |
| 入力バリデーション | 30XXXX | 入力データ検証エラー |
| ビジネスルール | 40XXXX | ビジネスロジックエラー（サービス別サブカテゴリ） |
| データベース | 50XXXX | データベース・リポジトリエラー |
| 外部サービス | 60XXXX | 外部サービス連携エラー |
| システム | 90XXXX | システムエラー |

### YY: サブカテゴリ（ビジネスルールエラー内のサービス別範囲）

| サービス | コード範囲 | 説明 |
|---------|------------|------|
| Cart | 401xx-404xx | カート・取引処理 |
| Master-data | 405xx | マスターデータ管理 |
| Terminal | 406xx-407xx | 端末・店舗管理 |
| Account | 408xx-409xx | 認証・ユーザー管理 |
| Journal | 410xx-411xx | 電子ジャーナル |
| Report | 412xx-413xx | レポート生成 |
| Stock | 414xx-415xx | 在庫管理 |

### ZZ: 特定エラー番号

## 実装されたエラーコード

### 一般エラー（10XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 100000 | General error occurred | 一般エラーが発生しました | システム全般 |
| 100001 | Resource not found | 対象データが見つかりませんでした | リソース検索 |

### 認証・認可エラー（20XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 200001 | Authentication failed | 認証に失敗しました | ログイン失敗 |
| 200002 | Permission denied | 権限がありません | 認可チェック |

### 入力バリデーションエラー（30XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 300001 | Invalid input data | 入力データが無効です | 一般バリデーション |
| 300002 | Required field is missing | 必須フィールドがありません | 必須チェック |
| 300003 | Invalid field format | フィールドの形式が正しくありません | 形式検証 |
| 300004 | Invalid operation | 操作が無効です | 操作検証 |

### ビジネスルールエラー（40XXXX）

ビジネスルールエラーは、各サービス固有のエラーを定義するためのカテゴリです。サービス別にサブカテゴリが割り当てられています。

**注:** 具体的なビジネスルールエラーコードは各サービスで定義されます。

### データベース・リポジトリエラー（50XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 500001 | Database error occurred | データベースエラーが発生しました | DB一般 |
| 500002 | Cannot create data | データを作成できませんでした | 作成失敗 |
| 500003 | Cannot update data | データを更新できませんでした | 更新失敗 |
| 500004 | Cannot delete data | データを削除できませんでした | 削除失敗 |
| 500005 | Duplicate key | キーが重複しています | 重複エラー |
| 500006 | Update operation failed | 更新が機能しませんでした | 更新不具合 |
| 500007 | Replace operation failed | 置換が機能しませんでした | 置換不具合 |
| 500008 | Cannot delete because child elements exist | 子要素が存在するため削除できません | 参照整合性 |

### 外部サービス連携エラー（60XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 600001 | External service error occurred | 外部サービスエラーが発生しました | 外部連携 |

### システムエラー（90XXXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 900001 | System error occurred | システムエラーが発生しました | システム障害 |
| 900999 | Unexpected error occurred | 予期しないエラーが発生しました | 予期しないエラー |

## 多言語対応実装

### ErrorMessage クラス

**実装場所:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

```python
class ErrorMessage:
    DEFAULT_LANGUAGE = "ja"
    SUPPORTED_LANGUAGES = ["ja", "en"]

    MESSAGES = {
        "ja": {
            ErrorCode.GENERAL_ERROR: "一般エラーが発生しました",
            ErrorCode.AUTHENTICATION_ERROR: "認証に失敗しました",
            ErrorCode.VALIDATION_ERROR: "入力データが無効です",
            ErrorCode.DATABASE_ERROR: "データベースエラーが発生しました",
            # ... 他のエラーメッセージ
        },
        "en": {
            ErrorCode.GENERAL_ERROR: "General error occurred",
            ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
            ErrorCode.VALIDATION_ERROR: "Invalid input data",
            ErrorCode.DATABASE_ERROR: "Database error occurred",
            # ... 他のエラーメッセージ
        }
    }

    DEFAULT_ERROR_MESSAGES = {
        "ja": "不明なエラーが発生しました",
        "en": "An unknown error occurred"
    }

    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None) -> str:
        """エラーコードに対応するメッセージを取得"""
        if lang is None:
            lang = cls.DEFAULT_LANGUAGE
        if lang not in cls.SUPPORTED_LANGUAGES:
            lang = cls.DEFAULT_LANGUAGE

        message = cls.MESSAGES.get(lang, {}).get(error_code)
        if message is None:
            if default_message:
                return default_message
            return cls.DEFAULT_ERROR_MESSAGES.get(lang, cls.DEFAULT_ERROR_MESSAGES.get(cls.DEFAULT_LANGUAGE))
        return message
```

### 統一レスポンス形式

```json
{
  "success": false,
  "code": 400,
  "message": "Operation failed",
  "userError": {
    "code": "500001",
    "message": "データベースエラーが発生しました"
  },
  "data": null,
  "metadata": null,
  "operation": "create_cart"
}
```

## カスタム例外クラス

### 基底例外クラス

```python
class KugelBaseException(Exception):
    def __init__(self, error_code: str, message: str = None, details: dict = None):
        self.error_code = error_code
        self.message = message or ErrorMessage.get_message(error_code)
        self.details = details or {}
        super().__init__(self.message)
```

### サービス固有例外

```python
# Cart Service例外
class CartNotFoundException(KugelBaseException):
    def __init__(self, cart_id: str):
        super().__init__(
            error_code="50001",
            details={"cart_id": cart_id}
        )

class InvalidCartStateException(KugelBaseException):
    def __init__(self, current_state: str, required_state: str):
        super().__init__(
            error_code="50002",
            details={
                "current_state": current_state,
                "required_state": required_state
            }
        )
```

## エラーハンドリングパターン

### FastAPIエラーハンドラー

```python
@app.exception_handler(KugelBaseException)
async def kugelbase_exception_handler(request: Request, exc: KugelBaseException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "code": 400,
            "message": "Operation failed",
            "userError": {
                "code": exc.error_code,
                "message": exc.message
            },
            "data": None,
            "metadata": exc.details,
            "operation": request.url.path.split('/')[-1]
        }
    )
```

### ログ出力

```python
logger.error(
    f"Error {exc.error_code}: {exc.message}",
    extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "operation": operation_name
    }
)
```

## 運用指針

### エラーコード追加ルール

1. **連番管理**: 同一モジュール内でZZ部分を連番で管理
2. **文書化**: 新規エラーコードは本仕様書に追記
3. **多言語対応**: 日本語・英語のメッセージを必ず追加
4. **後方互換性**: 既存コードの変更は避ける

### 監視・分析

```python
# エラー統計の収集
error_stats = {
    "error_code": exc.error_code,
    "service": "cart",
    "timestamp": datetime.utcnow(),
    "user_agent": request.headers.get("user-agent"),
    "ip_address": request.client.host
}
```

### エラーレート監視

- **警告レベル**: エラー率 > 5%
- **緊急レベル**: エラー率 > 10%
- **特定エラー**: 50001（カート不見つからない）の急増

このエラーコード体系により、Kugelposは一貫性のあるエラーハンドリングと効果的な問題診断を実現しています。