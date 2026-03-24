# プロモーション実績集計API契約

## 概要

reportサービスに追加するプロモーション実績集計APIの定義。

## ベースURL

```
/api/v1/tenants/{tenant_id}/reports/promotions
```

---

## エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|---------------|------|
| GET | `/promotions/summary` | プロモーション実績サマリー |
| GET | `/promotions/{promotion_code}` | プロモーション別実績詳細 |

---

## API詳細

### 1. プロモーション実績サマリー

**GET** `/api/v1/tenants/{tenant_id}/reports/promotions/summary`

期間内のプロモーション実績を集計して返す。

#### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| startDate | string (YYYY-MM-DD) | Yes | 集計開始日 |
| endDate | string (YYYY-MM-DD) | Yes | 集計終了日 |
| storeCode | string | No | 店舗コードでフィルタ |
| promotionType | string | No | プロモーションタイプでフィルタ |

#### レスポンス（成功: 200）

```json
{
  "status": "success",
  "code": 200,
  "message": "Promotion summary retrieved successfully",
  "data": {
    "period": {
      "startDate": "2026-07-01",
      "endDate": "2026-07-31"
    },
    "summary": {
      "totalPromotionsApplied": 3,
      "totalTransactionCount": 1250,
      "totalLineItemCount": 3800,
      "totalDiscountAmount": 285000.0,
      "totalTargetSalesAmount": 2850000.0
    },
    "promotions": [
      {
        "promotionCode": "SUMMER2026_BEVERAGE",
        "promotionType": "category_discount",
        "name": "夏季飲料キャンペーン",
        "transactionCount": 800,
        "lineItemCount": 2500,
        "discountAmount": 200000.0,
        "targetSalesAmount": 2000000.0,
        "discountRate": 10.0
      },
      {
        "promotionCode": "SNACK_PROMO",
        "promotionType": "category_discount",
        "name": "スナック菓子セール",
        "transactionCount": 450,
        "lineItemCount": 1300,
        "discountAmount": 85000.0,
        "targetSalesAmount": 850000.0,
        "discountRate": 10.0
      }
    ]
  }
}
```

---

### 2. プロモーション別実績詳細

**GET** `/api/v1/tenants/{tenant_id}/reports/promotions/{promotion_code}`

特定のプロモーションの詳細実績を取得する。

#### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| startDate | string (YYYY-MM-DD) | Yes | 集計開始日 |
| endDate | string (YYYY-MM-DD) | Yes | 集計終了日 |
| storeCode | string | No | 店舗コードでフィルタ |
| groupBy | string | No | 集計単位（day, store, category） |

#### レスポンス（成功: 200）

```json
{
  "status": "success",
  "code": 200,
  "message": "Promotion detail retrieved successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "夏季飲料キャンペーン",
    "period": {
      "startDate": "2026-07-01",
      "endDate": "2026-07-31"
    },
    "summary": {
      "transactionCount": 800,
      "lineItemCount": 2500,
      "discountAmount": 200000.0,
      "targetSalesAmount": 2000000.0,
      "discountRate": 10.0
    },
    "breakdown": [
      {
        "date": "2026-07-01",
        "transactionCount": 25,
        "lineItemCount": 80,
        "discountAmount": 6500.0,
        "targetSalesAmount": 65000.0
      },
      {
        "date": "2026-07-02",
        "transactionCount": 28,
        "lineItemCount": 85,
        "discountAmount": 7200.0,
        "targetSalesAmount": 72000.0
      }
    ],
    "categoryBreakdown": [
      {
        "categoryCode": "BEV001",
        "categoryName": "ソフトドリンク",
        "lineItemCount": 1500,
        "discountAmount": 120000.0
      },
      {
        "categoryCode": "BEV002",
        "categoryName": "アルコール飲料",
        "lineItemCount": 1000,
        "discountAmount": 80000.0
      }
    ]
  }
}
```

---

## エラーコード

| コード | 説明 |
|--------|------|
| 500101 | 日付範囲が不正 |
| 500102 | プロモーションが見つからない |
| 500103 | 集計データなし |

---

## スキーマ定義

### PromotionSummaryResponse

```python
class PromotionSummaryItem(BaseModel):
    promotion_code: str = Field(..., alias="promotionCode")
    promotion_type: str = Field(..., alias="promotionType")
    name: str
    transaction_count: int = Field(..., alias="transactionCount")
    line_item_count: int = Field(..., alias="lineItemCount")
    discount_amount: float = Field(..., alias="discountAmount")
    target_sales_amount: float = Field(..., alias="targetSalesAmount")
    discount_rate: float = Field(..., alias="discountRate")

class PromotionSummaryTotal(BaseModel):
    total_promotions_applied: int = Field(..., alias="totalPromotionsApplied")
    total_transaction_count: int = Field(..., alias="totalTransactionCount")
    total_line_item_count: int = Field(..., alias="totalLineItemCount")
    total_discount_amount: float = Field(..., alias="totalDiscountAmount")
    total_target_sales_amount: float = Field(..., alias="totalTargetSalesAmount")

class PromotionSummaryResponse(BaseModel):
    period: dict
    summary: PromotionSummaryTotal
    promotions: List[PromotionSummaryItem]
```

### PromotionDetailResponse

```python
class DailyBreakdown(BaseModel):
    date: str
    transaction_count: int = Field(..., alias="transactionCount")
    line_item_count: int = Field(..., alias="lineItemCount")
    discount_amount: float = Field(..., alias="discountAmount")
    target_sales_amount: float = Field(..., alias="targetSalesAmount")

class CategoryBreakdown(BaseModel):
    category_code: str = Field(..., alias="categoryCode")
    category_name: str = Field(..., alias="categoryName")
    line_item_count: int = Field(..., alias="lineItemCount")
    discount_amount: float = Field(..., alias="discountAmount")

class PromotionDetailResponse(BaseModel):
    promotion_code: str = Field(..., alias="promotionCode")
    promotion_type: str = Field(..., alias="promotionType")
    name: str
    period: dict
    summary: dict
    breakdown: List[DailyBreakdown]
    category_breakdown: List[CategoryBreakdown] = Field(..., alias="categoryBreakdown")
```
