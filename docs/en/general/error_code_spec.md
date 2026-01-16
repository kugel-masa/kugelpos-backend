# Kugelpos Error Code Specification

## Overview

The Kugelpos system achieves consistent error handling across services through a unified error code system. Error codes are in 6-digit numeric format (XXYYZZ) and include multi-language support.

## Error Code Structure (XXYYZZ)

### XX: Error Category

| Category | Code Range | Description |
|----------|------------|-------------|
| General | 10XXXX | General errors |
| Authentication | 20XXXX | Authentication/authorization errors |
| Input Validation | 30XXXX | Input data validation errors |
| Business Rule | 40XXXX | Business logic errors (service-specific subcategories) |
| Database | 50XXXX | Database/repository errors |
| External Service | 60XXXX | External service integration errors |
| System | 90XXXX | System errors |

### YY: Subcategory (Service-specific ranges within Business Rule Errors)

| Service | Code Range | Description |
|---------|------------|-------------|
| Cart | 401xx-404xx | Cart/transaction processing |
| Master-data | 405xx | Master data management |
| Terminal | 406xx-407xx | Terminal/store management |
| Account | 408xx-409xx | Authentication/user management |
| Journal | 410xx-411xx | Electronic journal |
| Report | 412xx-413xx | Report generation |
| Stock | 414xx-415xx | Inventory management |

### ZZ: Specific Error Number

## Implemented Error Codes

### General Errors (10XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 100000 | General error occurred | 一般エラーが発生しました | System general |
| 100001 | Resource not found | 対象データが見つかりませんでした | Resource search |

### Authentication/Authorization Errors (20XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 200001 | Authentication failed | 認証に失敗しました | Login failure |
| 200002 | Permission denied | 権限がありません | Authorization check |

### Input Validation Errors (30XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 300001 | Invalid input data | 入力データが無効です | General validation |
| 300002 | Required field is missing | 必須フィールドがありません | Required check |
| 300003 | Invalid field format | フィールドの形式が正しくありません | Format validation |
| 300004 | Invalid operation | 操作が無効です | Operation validation |

### Business Rule Errors (40XXXX)

Business rule errors are a category for defining service-specific errors. Subcategories are assigned by service.

**Note:** Specific business rule error codes are defined in each service.

### Database/Repository Errors (50XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 500001 | Database error occurred | データベースエラーが発生しました | DB general |
| 500002 | Cannot create data | データを作成できませんでした | Create failure |
| 500003 | Cannot update data | データを更新できませんでした | Update failure |
| 500004 | Cannot delete data | データを削除できませんでした | Delete failure |
| 500005 | Duplicate key | キーが重複しています | Duplicate error |
| 500006 | Update operation failed | 更新が機能しませんでした | Update malfunction |
| 500007 | Replace operation failed | 置換が機能しませんでした | Replace malfunction |
| 500008 | Cannot delete because child elements exist | 子要素が存在するため削除できません | Referential integrity |

### External Service Integration Errors (60XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 600001 | External service error occurred | 外部サービスエラーが発生しました | External integration |

### System Errors (90XXXX)

| Code | English Message | Japanese Message | Usage |
|------|-----------------|------------------|-------|
| 900001 | System error occurred | システムエラーが発生しました | System failure |
| 900999 | Unexpected error occurred | 予期しないエラーが発生しました | Unexpected error |

## Multi-language Support Implementation

### ErrorMessage Class

**Implementation Location:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

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
            # ... other error messages
        },
        "en": {
            ErrorCode.GENERAL_ERROR: "General error occurred",
            ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
            ErrorCode.VALIDATION_ERROR: "Invalid input data",
            ErrorCode.DATABASE_ERROR: "Database error occurred",
            # ... other error messages
        }
    }

    DEFAULT_ERROR_MESSAGES = {
        "ja": "不明なエラーが発生しました",
        "en": "An unknown error occurred"
    }

    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None) -> str:
        """Get message corresponding to error code"""
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

### Unified Response Format

```json
{
  "success": false,
  "code": 400,
  "message": "Operation failed",
  "userError": {
    "code": "500001",
    "message": "Database error occurred"
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
