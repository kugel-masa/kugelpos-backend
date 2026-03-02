# プロモーションAPI契約

## 概要

master-dataサービスに追加するプロモーション管理APIの定義。

## ベースURL

```
/api/v1/tenants/{tenant_id}/promotions
```

---

## エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|---------------|------|
| POST | `/promotions` | プロモーション作成 |
| GET | `/promotions` | プロモーション一覧取得 |
| GET | `/promotions/active` | 有効プロモーション取得 |
| GET | `/promotions/{promotion_code}` | プロモーション詳細取得 |
| PUT | `/promotions/{promotion_code}` | プロモーション更新 |
| DELETE | `/promotions/{promotion_code}` | プロモーション削除 |

---

## API詳細

### 1. プロモーション作成

**POST** `/api/v1/tenants/{tenant_id}/promotions`

#### リクエスト

```json
{
  "promotionCode": "SUMMER2026_BEVERAGE",
  "promotionType": "category_discount",
  "name": "夏季飲料キャンペーン",
  "description": "飲料カテゴリ全品10%オフ",
  "startDatetime": "2026-07-01T00:00:00",
  "endDatetime": "2026-08-31T23:59:59",
  "isActive": true,
  "detail": {
    "targetStoreCodes": ["STORE001", "STORE002"],
    "targetCategoryCodes": ["BEV001", "BEV002"],
    "discountRate": 10.0
  }
}
```

**注意**: `targetStoreCodes` が空配列 `[]` または省略された場合、全店舗に適用される。

#### レスポンス（成功: 201）

```json
{
  "success": true,
  "code": 201,
  "message": "Promotion SUMMER2026_BEVERAGE created successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "夏季飲料キャンペーン",
    "description": "飲料カテゴリ全品10%オフ",
    "startDatetime": "2026-07-01T00:00:00",
    "endDatetime": "2026-08-31T23:59:59",
    "isActive": true,
    "detail": {
      "targetStoreCodes": ["STORE001", "STORE002"],
      "targetCategoryCodes": ["BEV001", "BEV002"],
      "discountRate": 10.0
    },
    "entryDatetime": "2026-02-05T10:30:00",
    "lastUpdateDatetime": "2026-02-05T10:30:00"
  }
}
```

#### エラーレスポンス

| コード | 状況 | メッセージ |
|--------|------|-----------|
| 400 | バリデーションエラー | Invalid request data |
| 400101 | 重複 | Promotion code already exists |
| 400103 | 日付範囲不正 | End datetime must be after start datetime |
| 400104 | 割引率不正 | Discount rate must be between 0 and 100 |

---

### 2. プロモーション一覧取得

**GET** `/api/v1/tenants/{tenant_id}/promotions`

#### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| limit | int | No | 取得件数（デフォルト: 20） |
| page | int | No | ページ番号（デフォルト: 1） |
| sort | string | No | ソート条件（デフォルト: promotion_code:asc） |
| promotionType | string | No | タイプでフィルタ |
| isActive | bool | No | 有効フラグでフィルタ |

#### レスポンス（成功: 200）

```json
{
  "success": true,
  "code": 200,
  "message": "Promotions retrieved successfully",
  "data": [
    {
      "promotionCode": "SUMMER2026_BEVERAGE",
      "promotionType": "category_discount",
      "name": "夏季飲料キャンペーン",
      "startDatetime": "2026-07-01T00:00:00",
      "endDatetime": "2026-08-31T23:59:59",
      "isActive": true,
      "detail": {
        "targetCategoryCodes": ["BEV001", "BEV002"],
        "discountRate": 10.0
      }
    }
  ],
  "metadata": {
    "total": 15,
    "page": 1,
    "limit": 20,
    "sort": "promotion_code:asc",
    "filter": {}
  }
}
```

---

### 3. 有効プロモーション取得

**GET** `/api/v1/tenants/{tenant_id}/promotions/active`

現在有効なプロモーションを取得する。

#### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| storeCode | string | No | 店舗コードでフィルタ（該当店舗または全店舗対象を返す） |
| categoryCode | string | No | カテゴリコードでフィルタ |
| promotionType | string | No | タイプでフィルタ |

#### レスポンス（成功: 200）

```json
{
  "success": true,
  "code": 200,
  "message": "Active promotions retrieved successfully",
  "data": [
    {
      "promotionCode": "SUMMER2026_BEVERAGE",
      "promotionType": "category_discount",
      "name": "夏季飲料キャンペーン",
      "detail": {
        "targetStoreCodes": ["STORE001", "STORE002"],
        "targetCategoryCodes": ["BEV001", "BEV002"],
        "discountRate": 10.0
      }
    }
  ]
}
```

---

### 4. プロモーション詳細取得

**GET** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

#### レスポンス（成功: 200）

```json
{
  "success": true,
  "code": 200,
  "message": "Promotion SUMMER2026_BEVERAGE found successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "夏季飲料キャンペーン",
    "description": "飲料カテゴリ全品10%オフ",
    "startDatetime": "2026-07-01T00:00:00",
    "endDatetime": "2026-08-31T23:59:59",
    "isActive": true,
    "detail": {
      "targetCategoryCodes": ["BEV001", "BEV002"],
      "discountRate": 10.0
    },
    "entryDatetime": "2026-02-05T10:30:00",
    "lastUpdateDatetime": "2026-02-05T10:30:00"
  }
}
```

#### エラーレスポンス

| コード | 状況 | メッセージ |
|--------|------|-----------|
| 400102 | 存在しない | Promotion not found |

---

### 5. プロモーション更新

**PUT** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

#### リクエスト

```json
{
  "name": "夏季飲料キャンペーン（延長）",
  "endDatetime": "2026-09-30T23:59:59",
  "detail": {
    "targetCategoryCodes": ["BEV001", "BEV002", "BEV003"],
    "discountRate": 15.0
  }
}
```

**注意**: `promotionCode` と `promotionType` は変更不可。

#### レスポンス（成功: 200）

```json
{
  "success": true,
  "code": 200,
  "message": "Promotion SUMMER2026_BEVERAGE updated successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "夏季飲料キャンペーン（延長）",
    "endDatetime": "2026-09-30T23:59:59",
    "detail": {
      "targetCategoryCodes": ["BEV001", "BEV002", "BEV003"],
      "discountRate": 15.0
    },
    "lastUpdateDatetime": "2026-02-10T14:00:00"
  }
}
```

---

### 6. プロモーション削除

**DELETE** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

論理削除を行う（`is_deleted = true`）。

#### レスポンス（成功: 200）

```json
{
  "success": true,
  "code": 200,
  "message": "Promotion SUMMER2026_BEVERAGE deleted successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE"
  }
}
```

---

## 共通エラーコード

| コード | 説明 |
|--------|------|
| 400101 | プロモーションコード重複 |
| 400102 | プロモーションが見つからない |
| 400103 | 日付範囲が不正 |
| 400104 | 割引タイプが不正 |
| 400105 | 割引値が不正 |

---

## スキーマ定義

### PromotionCreateRequest

```python
class PromotionCreateRequest(BaseModel):
    promotion_code: str = Field(..., alias="promotionCode")
    promotion_type: str = Field(..., alias="promotionType")
    name: str
    description: Optional[str] = None
    start_datetime: datetime = Field(..., alias="startDatetime")
    end_datetime: datetime = Field(..., alias="endDatetime")
    is_active: bool = Field(True, alias="isActive")
    detail: Optional[BaseCategoryPromoDetail] = Field(None, alias="detail")
```

### CategoryPromoDetail

```python
class CategoryPromoDetail(BaseModel):
    target_store_codes: Optional[List[str]] = Field([], alias="targetStoreCodes")  # 空=全店舗
    target_category_codes: List[str] = Field(..., alias="targetCategoryCodes")
    discount_rate: float = Field(..., alias="discountRate", gt=0, le=100)
```

### PromotionResponse

```python
class PromotionResponse(BaseModel):
    promotion_code: str = Field(..., alias="promotionCode")
    promotion_type: str = Field(..., alias="promotionType")
    name: str
    description: Optional[str] = None
    start_datetime: datetime = Field(..., alias="startDatetime")
    end_datetime: datetime = Field(..., alias="endDatetime")
    is_active: bool = Field(..., alias="isActive")
    detail: Optional[BaseCategoryPromoDetail] = Field(None, alias="detail")
    entry_datetime: Optional[str] = Field(None, alias="entryDatetime")
    last_update_datetime: Optional[str] = Field(None, alias="lastUpdateDatetime")
```
