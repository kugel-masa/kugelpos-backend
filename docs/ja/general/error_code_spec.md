# Kugelpos エラーコード仕様

## 概要

Kugelposシステムでは、統一されたエラーコード体系により、サービス横断での一貫したエラーハンドリングを実現しています。エラーコードは6桁の数値（XXYYZZ）形式で、多言語対応も含めて実装されています。

## エラーコード構造（XXYYZZ）

### XX: サービス識別子

| サービス | コード範囲 | 説明 |
|---------|------------|------|
| Commons | 10XXX | 共通エラー |
| Account | 20XXX | 認証・ユーザー管理 |
| Terminal | 30XXX | 端末・店舗管理 |
| Master-data | 40XXX | マスターデータ管理 |
| Cart | 50XXX | カート・取引処理 |
| Report | 60XXX | レポート生成 |
| Journal | 70XXX | 電子ジャーナル |
| Stock | 80XXX | 在庫管理 |

### YY: 機能・モジュール識別子

### ZZ: 特定エラー番号

## 実装されたエラーコード

### 共通エラー（10XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 10001 | General error occurred | 一般エラーが発生しました | システム全般 |
| 10002 | Authentication required | 認証が必要です | 認証チェック |
| 10003 | Access denied | アクセスが拒否されました | 認可チェック |
| 10004 | Invalid request format | 無効なリクエスト形式です | バリデーション |
| 10005 | Database connection failed | データベース接続に失敗しました | DB接続 |

### Account Service（20XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 20001 | Invalid credentials | 認証情報が無効です | ログイン失敗 |
| 20002 | User not found | ユーザーが見つかりません | ユーザー検索 |
| 20003 | Token expired | トークンが期限切れです | JWT検証 |
| 20004 | User already exists | ユーザーが既に存在します | ユーザー作成 |

### Terminal Service（30XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 30001 | Terminal not found | 端末が見つかりません | 端末検索 |
| 30002 | Terminal already exists | 端末が既に存在します | 端末作成 |
| 30003 | Invalid terminal status | 無効な端末状態です | 状態チェック |
| 30004 | Store not found | 店舗が見つかりません | 店舗検索 |
| 30005 | Invalid API key | 無効なAPIキーです | API認証 |

### Master-data Service（40XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 40001 | Item not found | 商品が見つかりません | 商品検索 |
| 40002 | Category not found | カテゴリが見つかりません | カテゴリ検索 |
| 40003 | Price not configured | 価格が設定されていません | 価格取得 |
| 40004 | Tax rule not found | 税率ルールが見つかりません | 税計算 |

### Cart Service（50XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 50001 | Cart not found | カートが見つかりません | カート検索 |
| 50002 | Invalid cart state | 無効なカート状態です | 状態チェック |
| 50003 | Item already in cart | 商品が既にカートにあります | 商品追加 |
| 50004 | Payment method not supported | サポートされていない支払い方法です | 支払い処理 |
| 50005 | Insufficient payment | 支払い金額が不足しています | 支払い検証 |

### Report Service（60XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 60001 | Report generation failed | レポート生成に失敗しました | レポート作成 |
| 60002 | Invalid date range | 無効な日付範囲です | 日付検証 |
| 60003 | No data available | データがありません | データ取得 |

### Journal Service（70XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 70001 | Journal entry not found | ジャーナルエントリが見つかりません | 検索 |
| 70002 | Invalid journal format | 無効なジャーナル形式です | 形式検証 |

### Stock Service（80XXX）

| コード | 英語メッセージ | 日本語メッセージ | 用途 |
|--------|---------------|-----------------|------|
| 80001 | Stock item not found | 在庫商品が見つかりません | 在庫検索 |
| 80002 | Insufficient stock | 在庫が不足しています | 在庫チェック |
| 80003 | Invalid quantity | 無効な数量です | 数量検証 |

## 多言語対応実装

### ErrorMessage クラス

**実装場所:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

```python
class ErrorMessage:
    MESSAGES = {
        "ja": {
            ErrorCode.GENERAL_ERROR: "一般エラーが発生しました",
            ErrorCode.AUTHENTICATION_ERROR: "認証に失敗しました",
            ErrorCode.CART_NOT_FOUND: "カートが見つかりません",
            # ... 他のエラーメッセージ
        },
        "en": {
            ErrorCode.GENERAL_ERROR: "General error occurred",
            ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
            ErrorCode.CART_NOT_FOUND: "Cart not found",
            # ... 他のエラーメッセージ
        }
    }
    
    @classmethod
    def get_message(cls, error_code: str, language: str = "ja") -> str:
        return cls.MESSAGES.get(language, {}).get(error_code, "Unknown error")
```

### 統一レスポンス形式

```json
{
  "success": false,
  "code": 400,
  "message": "Cart creation failed",
  "userError": {
    "code": "50001",
    "message": "カートが見つかりません"
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