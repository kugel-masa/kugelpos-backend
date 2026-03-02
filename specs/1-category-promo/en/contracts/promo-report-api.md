# Promotion Results Aggregation API Contract

## Overview

Definition of the promotion results aggregation API to be added to the report service.

## Base URL

```
/api/v1/tenants/{tenant_id}/reports/promotions
```

---

## Endpoint List

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/promotions/summary` | Promotion results summary |
| GET | `/promotions/{promotion_code}` | Promotion-specific results detail |

---

## API Details

### 1. Promotion Results Summary

**GET** `/api/v1/tenants/{tenant_id}/reports/promotions/summary`

Returns aggregated promotion results within a specified period.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| startDate | string (YYYY-MM-DD) | Yes | Aggregation start date |
| endDate | string (YYYY-MM-DD) | Yes | Aggregation end date |
| storeCode | string | No | Filter by store code |
| promotionType | string | No | Filter by promotion type |

#### Response (Success: 200)

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
        "name": "Summer Beverage Campaign",
        "transactionCount": 800,
        "lineItemCount": 2500,
        "discountAmount": 200000.0,
        "targetSalesAmount": 2000000.0,
        "discountRate": 10.0
      },
      {
        "promotionCode": "SNACK_PROMO",
        "promotionType": "category_discount",
        "name": "Snack Sale",
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

### 2. Promotion-Specific Results Detail

**GET** `/api/v1/tenants/{tenant_id}/reports/promotions/{promotion_code}`

Retrieves detailed results for a specific promotion.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| startDate | string (YYYY-MM-DD) | Yes | Aggregation start date |
| endDate | string (YYYY-MM-DD) | Yes | Aggregation end date |
| storeCode | string | No | Filter by store code |
| groupBy | string | No | Aggregation unit (day, store, category) |

#### Response (Success: 200)

```json
{
  "status": "success",
  "code": 200,
  "message": "Promotion detail retrieved successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "Summer Beverage Campaign",
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
        "categoryName": "Soft Drinks",
        "lineItemCount": 1500,
        "discountAmount": 120000.0
      },
      {
        "categoryCode": "BEV002",
        "categoryName": "Alcoholic Beverages",
        "lineItemCount": 1000,
        "discountAmount": 80000.0
      }
    ]
  }
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 500101 | Invalid date range |
| 500102 | Promotion not found |
| 500103 | No aggregation data |

---

## Schema Definitions

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
