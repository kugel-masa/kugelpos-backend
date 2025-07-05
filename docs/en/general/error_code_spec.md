# Kugelpos Error Code Specification

## Overview

The Kugelpos system implements consistent error handling across services through a unified error code system. Error codes are in 6-digit numeric format (XXYYZZ) and include multi-language support.

## Error Code Structure (XXYYZZ)

### XX: Service Identifier

| Service | Code Range | Description |
|---------|------------|-------------|
| Commons | 10XXX | Common errors |
| Account | 20XXX | Authentication & user management |
| Terminal | 30XXX | Terminal & store management |
| Master-data | 40XXX | Master data management |
| Cart | 50XXX | Cart & transaction processing |
| Report | 60XXX | Report generation |
| Journal | 70XXX | Electronic journal |
| Stock | 80XXX | Inventory management |

### YY: Feature/Module Identifier

### ZZ: Specific Error Number

## Implemented Error Codes

### Common Errors (10XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 10001 | General error occurred | 一般エラーが発生しました | System general |
| 10002 | Authentication required | 認証が必要です | Authentication check |
| 10003 | Access denied | アクセスが拒否されました | Authorization check |
| 10004 | Invalid request format | 無効なリクエスト形式です | Validation |
| 10005 | Database connection failed | データベース接続に失敗しました | DB connection |

### Account Service (20XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 20001 | Invalid credentials | 認証情報が無効です | Login failure |
| 20002 | User not found | ユーザーが見つかりません | User search |
| 20003 | Token expired | トークンが期限切れです | JWT validation |
| 20004 | User already exists | ユーザーが既に存在します | User creation |

### Terminal Service (30XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 30001 | Terminal not found | 端末が見つかりません | Terminal search |
| 30002 | Terminal already exists | 端末が既に存在します | Terminal creation |
| 30003 | Invalid terminal status | 無効な端末状態です | Status check |
| 30004 | Store not found | 店舗が見つかりません | Store search |
| 30005 | Invalid API key | 無効なAPIキーです | API authentication |

### Master-data Service (40XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 40001 | Item not found | 商品が見つかりません | Product search |
| 40002 | Category not found | カテゴリが見つかりません | Category search |
| 40003 | Price not configured | 価格が設定されていません | Price retrieval |
| 40004 | Tax rule not found | 税率ルールが見つかりません | Tax calculation |

### Cart Service (50XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 50001 | Cart not found | カートが見つかりません | Cart search |
| 50002 | Invalid cart state | 無効なカート状態です | State check |
| 50003 | Item already in cart | 商品が既にカートにあります | Item addition |
| 50004 | Payment method not supported | サポートされていない支払い方法です | Payment processing |
| 50005 | Insufficient payment | 支払い金額が不足しています | Payment validation |

### Report Service (60XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 60001 | Report generation failed | レポート生成に失敗しました | Report creation |
| 60002 | Invalid date range | 無効な日付範囲です | Date validation |
| 60003 | No data available | データがありません | Data retrieval |

### Journal Service (70XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 70001 | Journal entry not found | ジャーナルエントリが見つかりません | Search |
| 70002 | Invalid journal format | 無効なジャーナル形式です | Format validation |

### Stock Service (80XXX)

| Code | English Message | Japanese Message | Usage |
|------|----------------|------------------|-------|
| 80001 | Stock item not found | 在庫商品が見つかりません | Stock search |
| 80002 | Insufficient stock | 在庫が不足しています | Stock check |
| 80003 | Invalid quantity | 無効な数量です | Quantity validation |

## Multi-language Support Implementation

### ErrorMessage Class

**Implementation Location:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

```python
class ErrorMessage:
    MESSAGES = {
        "ja": {
            ErrorCode.GENERAL_ERROR: "一般エラーが発生しました",
            ErrorCode.AUTHENTICATION_ERROR: "認証に失敗しました",
            ErrorCode.CART_NOT_FOUND: "カートが見つかりません",
            # ... other error messages
        },
        "en": {
            ErrorCode.GENERAL_ERROR: "General error occurred",
            ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
            ErrorCode.CART_NOT_FOUND: "Cart not found",
            # ... other error messages
        }
    }
    
    @classmethod
    def get_message(cls, error_code: str, language: str = "ja") -> str:
        return cls.MESSAGES.get(language, {}).get(error_code, "Unknown error")
```

### Unified Response Format

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

## Custom Exception Classes

### Base Exception Class

```python
class KugelBaseException(Exception):
    def __init__(self, error_code: str, message: str = None, details: dict = None):
        self.error_code = error_code
        self.message = message or ErrorMessage.get_message(error_code)
        self.details = details or {}
        super().__init__(self.message)
```

### Service-specific Exceptions

```python
# Cart Service exceptions
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

## Error Handling Patterns

### FastAPI Error Handler

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

### Log Output

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

## Operational Guidelines

### Error Code Addition Rules

1. **Sequential Management**: Manage ZZ part sequentially within the same module
2. **Documentation**: Add new error codes to this specification
3. **Multi-language Support**: Always add Japanese and English messages
4. **Backward Compatibility**: Avoid changing existing codes

### Monitoring & Analysis

```python
# Error statistics collection
error_stats = {
    "error_code": exc.error_code,
    "service": "cart",
    "timestamp": datetime.utcnow(),
    "user_agent": request.headers.get("user-agent"),
    "ip_address": request.client.host
}
```

### Error Rate Monitoring

- **Warning Level**: Error rate > 5%
- **Critical Level**: Error rate > 10%
- **Specific Error**: Spike in 50001 (Cart not found)

Through this error code system, Kugelpos achieves consistent error handling and effective problem diagnosis.