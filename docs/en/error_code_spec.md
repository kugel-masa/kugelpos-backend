# Error Code Specification

## Overview

This document defines the error code system for the Kugelpos system. Error codes consist of 6-digit numbers (XXYYZZ format) to ensure consistent error handling.

## Error Code Structure

### Format: XXYYZZ

- **XX**: Error category (first 2 digits)
- **YY**: Subcategory (middle 2 digits)
- **ZZ**: Detail code (last 2 digits)

## Common Error Codes (Shared Across All Services)

`/services/commons/src/kugel_common/exceptions/error_codes.py`

### General Errors (10YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 100000 | General error | 一般エラーが発生しました |
| 100001 | Resource not found | 対象データが見つかりませんでした |

### Authentication/Authorization Errors (20YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 200001 | Authentication failed | 認証に失敗しました |
| 200002 | Permission denied | 権限がありません |

### Input Validation Errors (30YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 300001 | General validation error | 入力データが無効です |
| 300002 | Required field missing | 必須フィールドがありません |
| 300003 | Invalid field format | フィールドの形式が正しくありません |
| 300004 | Invalid operation | 操作が無効です |

### Database/Repository Errors (50YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 500001 | General database error | データベースエラーが発生しました |
| 500002 | Cannot create | データを作成できませんでした |
| 500003 | Cannot update | データを更新できませんでした |
| 500004 | Cannot delete | データを削除できませんでした |
| 500005 | Duplicate key | キーが重複しています |
| 500006 | Update operation failed | 更新が機能しませんでした |
| 500007 | Replace operation failed | 置換が機能しませんでした |
| 500008 | Cannot delete because child elements exist | 子要素が存在するため削除できません |

### External Service Integration Errors (60YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 600001 | External service error | 外部サービスエラーが発生しました |

### System Errors (90YYZZ)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 900001 | System error | システムエラーが発生しました |
| 900999 | Unexpected error | 予期しないエラーが発生しました |

## Service-Specific Error Codes

### Cart Service (401xx-404xx)

`/services/cart/app/exceptions/cart_error_codes.py`

#### Cart Operations (401xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 401001 | Cart creation failed | カートの作成に失敗しました |
| 401002 | Cart not found | カートが見つかりません |
| 401003 | Failed to save cart | カートの保存に失敗しました |

#### Item Registration (402xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 402001 | Item not found | 対象商品が見つかりません |
| 402002 | Amount is less than discount | 値引金額が商品金額より多いです |
| 402003 | Balance is less than discount | 値引金額が残高より多いです |
| 402004 | Discount allocation error | 値引の按分処理に失敗しました |
| 402005 | Discount restriction | 値引禁止商品です |

#### Payment Related (403xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 403001 | Balance is already zero | 残高はすでに０です |
| 403002 | Balance is greater than zero | 残高が残っています |
| 403003 | Balance is minus | 残高がマイナスです |
| 403004 | Deposit amount is more than balance | 預かり金額が残高より多いです |
| 403005 | This transaction has already been voided | この取引は既に取消済みです |
| 403006 | This transaction has already been refunded | この取引は既に返品済みです |

#### Other Cart Errors (404xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 404001 | Check terminal status | 端末の状態を確認してください |
| 404002 | Check sign-in/out status | 担当者の登録状況を確認してください |
| 404003 | External service error occurred | 外部サービスエラーが発生しました |
| 404004 | Internal processing error occurred | 内部処理エラーが発生しました |
| 404999 | Unexpected error occurred | 想定外のエラーが発生しました |

### Master-Data Service (405xx)

`/services/master-data/app/exceptions/master_data_error_codes.py`

#### Master Data Basic Errors (405xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405001 | Master data validation error | マスターデータ検証エラーが発生しました |
| 405002 | Master data not found | マスターデータが見つかりません |
| 405003 | Master data already exists | マスターデータがすでに存在します |
| 405004 | Cannot create master data | マスターデータを作成できません |
| 405005 | Cannot update master data | マスターデータを更新できません |
| 405006 | Cannot delete master data | マスターデータを削除できません |

#### Product Master (4051x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405101 | Product not found | 商品が見つかりません |
| 405102 | Product code is duplicate | 商品コードが重複しています |
| 405103 | Product price is invalid | 商品の価格が無効です |
| 405104 | Product tax rate is invalid | 商品の税率が無効です |

#### Price Master (4052x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405201 | Price not found | 価格が見つかりません |
| 405202 | Price amount is invalid | 価格の金額が無効です |
| 405203 | Price date range is invalid | 価格の適用期間が無効です |

#### Customer Master (4053x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405301 | Customer not found | 顧客が見つかりません |
| 405302 | Customer ID is duplicate | 顧客IDが重複しています |

#### Store Master (4054x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405401 | Store not found | 店舗が見つかりません |
| 405402 | Store code is duplicate | 店舗コードが重複しています |

#### Department Master (4055x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 405501 | Department not found | 部門が見つかりません |
| 405502 | Department code is duplicate | 部門コードが重複しています |

### Terminal Service (406xx-407xx)

`/services/terminal/app/exceptions/terminal_error_codes.py`

#### Terminal Basic Operations (4060xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 406001 | Terminal not found | 端末が見つかりません |
| 406002 | Terminal already exists | 端末はすでに存在します |
| 406003 | Terminal status error | 端末の状態を確認してください |
| 406004 | Sign in/out error | 担当者の登録状況を確認してください |
| 406005 | Sign in required | サインインが必要です |
| 406006 | Invalid credentials | 認証情報が無効です |
| 406007 | Failed to open the terminal | 端末オープン処理に失敗しました |
| 406008 | Failed to close the terminal | 端末クローズ処理に失敗しました |
| 406009 | Terminal is already opened | 端末はすでにオープン状態です |
| 406010 | Terminal is already closed | 端末はすでにクローズ状態です |
| 406011 | Terminal is busy | 端末が他の処理を実行中です |
| 406012 | Failed to change function mode | 機能モード変更に失敗しました |
| 406013 | Terminal is not signed in | 端末にサインインしていません |
| 406014 | Already signed in | すでにサインインしています |
| 406015 | Terminal is signed out | サインアウトされています |

#### Cash Management (4061xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 406101 | Cash in/out operation failed | 入出金処理に失敗しました |
| 406102 | Invalid amount entered | 入力金額が不正です |
| 406103 | Cash drawer is closed | キャッシュドロワーがクローズ状態です |
| 406104 | Amount exceeds maximum limit | 最大金額を超過しています |
| 406105 | Amount is below minimum limit | 最小金額を下回っています |
| 406106 | Physical amount does not match | 実在高と記録金額が一致しません |

#### Tenant Related (4070xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 407001 | Tenant not found | テナントが見つかりません |
| 407002 | Tenant already exists | テナントはすでに存在します |
| 407003 | Failed to update tenant info | テナント情報の更新に失敗しました |
| 407004 | Failed to delete tenant | テナントの削除に失敗しました |
| 407005 | Tenant configuration error | テナント設定に問題があります |
| 407006 | Failed to create tenant | テナントの作成に失敗しました |

#### Store Related (4071xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 407101 | Store not found | 店舗が見つかりません |
| 407102 | Store already exists | 店舗はすでに存在します |
| 407103 | Failed to update store info | 店舗情報の更新に失敗しました |
| 407104 | Failed to delete store | 店舗の削除に失敗しました |
| 407105 | Store configuration error | 店舗設定に問題があります |
| 407106 | Business date error | 営業日の設定に問題があります |

#### External Service Related (4072xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 407201 | External service integration error | 外部サービスとの連携に失敗しました |

#### Other Terminal Errors (4073xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 407301 | Internal processing error | 内部処理エラーが発生しました |
| 407399 | Unexpected error occurred | 想定外のエラーが発生しました |

### Account Service (408xx-409xx)

*Note: Account Service uses common error codes. No service-specific error codes are defined.*

### Journal Service (410xx-411xx)

`/services/journal/app/exceptions/journal_error_codes.py`

#### Journal Basic Operations (4100x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 410001 | Journal not found | ジャーナルが見つかりません |
| 410002 | Journal validation error | ジャーナルのバリデーションエラーが発生しました |
| 410003 | Failed to create journal | ジャーナルの作成に失敗しました |
| 410004 | Failed to query journals | ジャーナルの検索に失敗しました |
| 410005 | Invalid journal format | ジャーナルの形式が不正です |
| 410006 | Issue with journal date | ジャーナルの日付に問題があります |
| 410007 | Issue with journal data | ジャーナルデータに問題があります |

#### Journal Validation (4101x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 410101 | Terminal not found | 端末が見つかりません |
| 410102 | Store not found | 店舗が見つかりません |
| 410103 | Required logs are missing | 必要なログが欠落しています |
| 410104 | Issue with log sequence | ログシーケンスに問題があります |
| 410105 | Transaction validation failed | トランザクションの検証に失敗しました |

#### Other Journal Errors (411xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 411001 | Failed to generate receipt | レシートの生成に失敗しました |
| 411002 | Failed to generate journal text | ジャーナルテキストの生成に失敗しました |
| 411003 | Failed to export data | データのエクスポートに失敗しました |
| 411004 | Failed to import data | データのインポートに失敗しました |
| 411005 | Issue with transaction receipt | トランザクションレシートに問題があります |
| 411006 | External service error | 外部サービスエラーが発生しました |

### Report Service (412xx-413xx)

`/services/report/app/exceptions/report_error_codes.py`

#### Report Basic Operations (4120x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 412001 | Report not found | レポートが見つかりません |
| 412002 | Report validation error | レポートのバリデーションエラーが発生しました |
| 412003 | Failed to generate report | レポートの生成に失敗しました |
| 412004 | Invalid report type | 不正なレポートタイプです |
| 412005 | Invalid report scope | 不正なレポートスコープです |
| 412006 | Issue with report date | レポート日付に問題があります |
| 412007 | Issue with report data | レポートデータに問題があります |

#### Report Validation (4121x)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 412101 | Terminal not closed | 端末がクローズされていないため、レポートを生成できません |
| 412102 | Required logs are missing | 必要なログが欠落しています |
| 412103 | Log count mismatch | ログの数が一致しません |
| 412104 | Transaction logs are missing | トランザクションログが欠落しています |
| 412105 | Cash in/out logs are missing | 入出金ログが欠落しています |
| 412106 | Open/close logs are missing | 開閉店ログが欠落しています |
| 412107 | Data verification failed | データ検証に失敗しました |

#### Other Report Errors (413xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 413001 | Failed to generate receipt | レシートの生成に失敗しました |
| 413002 | Failed to generate journal | ジャーナルの生成に失敗しました |
| 413003 | Failed to export data | データのエクスポートに失敗しました |
| 413004 | Failed to import data | データのインポートに失敗しました |
| 413005 | Failed to process daily info | 日次情報の処理に失敗しました |
| 413006 | External service error | 外部サービスエラーが発生しました |

## Error Code Implementation Guidelines

### 1. Error Code Definition

Each service has a dedicated error code file:
```python
# services/{service_name}/app/exceptions/{service_name}_error_codes.py
from kugel_common.exceptions.error_codes import ErrorCodeDefinition

# Error code definition
CART_CREATION_FAILED = ErrorCodeDefinition(
    error_code=401001,
    error_message_en="Cart creation failed",
    error_message_jp="カートの作成に失敗しました"
)
```

### 2. Exception Class Implementation

```python
# services/{service_name}/app/exceptions/{service_name}_exceptions.py
from kugel_common.exceptions import ServiceException
from .cart_error_codes import CART_CREATION_FAILED

class CartCreationFailedException(ServiceException):
    def __init__(self, detail: str = None):
        super().__init__(
            error_code_def=CART_CREATION_FAILED,
            detail=detail
        )
```

### 3. Unified Error Response Format

```json
{
    "error_code": 401001,
    "error_message": "Cart creation failed",
    "detail": "Specific error details",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### 4. Multi-language Support

- Error messages are defined in both English and Japanese
- Appropriate language is returned based on client's Accept-Language header
- Default language is Japanese

### 5. Error Code Range Reservation

| Service | Error Code Range | Description |
|---------|-----------------|-------------|
| Commons | 10YYZZ-90YYZZ | Common across all services |
| Cart | 401xx-404xx | Cart service |
| Master-Data | 405xx | Master data service |
| Terminal | 406xx-407xx | Terminal service |
| Account | 408xx-409xx | Account service (not implemented) |
| Journal | 410xx-411xx | Journal service |
| Report | 412xx-413xx | Report service |
| Stock | 414xx-415xx | Stock management service |

### Stock Service (414xx-415xx)

`/services/stock/app/exceptions/stock_error_codes.py`

#### Stock Basic Operations (4140xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 414001 | Stock not found | 在庫情報が見つかりません |
| 414002 | Insufficient stock | 在庫が不足しています |
| 414003 | Stock validation error occurred | 在庫情報のバリデーションエラーが発生しました |
| 414004 | Access to stock denied | 在庫情報へのアクセスが拒否されました |
| 414005 | Stock database error occurred | 在庫データベースエラーが発生しました |

#### Stock Update Operations (4141xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 414101 | Failed to update stock | 在庫の更新に失敗しました |
| 414102 | Stock update validation error occurred | 在庫更新のバリデーションエラーが発生しました |
| 414103 | Stock update conflict occurred | 在庫更新で競合が発生しました |
| 414104 | Stock to update not found | 更新対象の在庫が見つかりません |

#### Snapshot Operations (4142xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 414201 | Failed to create snapshot | スナップショットの作成に失敗しました |
| 414202 | Snapshot not found | スナップショットが見つかりません |
| 414203 | Snapshot validation error occurred | スナップショットのバリデーションエラーが発生しました |
| 414204 | Failed to delete snapshot | スナップショットの削除に失敗しました |

#### External Service Operations (4143xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 414301 | External service error occurred | 外部サービスエラーが発生しました |
| 414302 | Pub/Sub error occurred | Pub/Subエラーが発生しました |
| 414303 | State store error occurred | ステートストアエラーが発生しました |

#### Transaction Processing (4144xx)
| Code | English Message | Japanese Message |
|------|----------------|------------------|
| 414401 | Transaction processing error occurred | トランザクション処理エラーが発生しました |
| 414402 | Transaction validation error occurred | トランザクションのバリデーションエラーが発生しました |
| 414403 | Duplicate transaction | 重複したトランザクションです |

## Revision History

- 2025-01-06: Initial version - Extracted and documented all error codes from actual codebase