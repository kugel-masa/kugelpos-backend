# Promotion API Contract

## Overview

Definition of the promotion management API to be added to the master-data service.

## Base URL

```
/api/v1/tenants/{tenant_id}/promotions
```

---

## Endpoint List

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/promotions` | Create promotion |
| GET | `/promotions` | List promotions |
| GET | `/promotions/active` | Get active promotions |
| GET | `/promotions/{promotion_code}` | Get promotion details |
| PUT | `/promotions/{promotion_code}` | Update promotion |
| DELETE | `/promotions/{promotion_code}` | Delete promotion |

---

## API Details

### 1. Create Promotion

**POST** `/api/v1/tenants/{tenant_id}/promotions`

#### Request

```json
{
  "promotionCode": "SUMMER2026_BEVERAGE",
  "promotionType": "category_discount",
  "name": "Summer Beverage Campaign",
  "description": "10% off all items in the beverage category",
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

**Note**: If `targetStoreCodes` is an empty array `[]` or omitted, the promotion applies to all stores.

#### Response (Success: 201)

```json
{
  "success": true,
  "code": 201,
  "message": "Promotion SUMMER2026_BEVERAGE created successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "Summer Beverage Campaign",
    "description": "10% off all items in the beverage category",
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

#### Error Responses

| Code | Situation | Message |
|------|-----------|---------|
| 400 | Validation error | Invalid request data |
| 400101 | Duplicate | Promotion code already exists |
| 400103 | Invalid date range | End datetime must be after start datetime |
| 400104 | Invalid discount rate | Discount rate must be between 0 and 100 |

---

### 2. List Promotions

**GET** `/api/v1/tenants/{tenant_id}/promotions`

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | int | No | Number of items to retrieve (default: 20) |
| page | int | No | Page number (default: 1) |
| sort | string | No | Sort condition (default: promotion_code:asc) |
| promotionType | string | No | Filter by type |
| isActive | bool | No | Filter by active flag |

#### Response (Success: 200)

```json
{
  "success": true,
  "code": 200,
  "message": "Promotions retrieved successfully",
  "data": [
    {
      "promotionCode": "SUMMER2026_BEVERAGE",
      "promotionType": "category_discount",
      "name": "Summer Beverage Campaign",
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

### 3. Get Active Promotions

**GET** `/api/v1/tenants/{tenant_id}/promotions/active`

Retrieves currently active promotions.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| storeCode | string | No | Filter by store code (returns matching store or all-store promotions) |
| categoryCode | string | No | Filter by category code |
| promotionType | string | No | Filter by type |

#### Response (Success: 200)

```json
{
  "success": true,
  "code": 200,
  "message": "Active promotions retrieved successfully",
  "data": [
    {
      "promotionCode": "SUMMER2026_BEVERAGE",
      "promotionType": "category_discount",
      "name": "Summer Beverage Campaign",
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

### 4. Get Promotion Details

**GET** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

#### Response (Success: 200)

```json
{
  "success": true,
  "code": 200,
  "message": "Promotion SUMMER2026_BEVERAGE found successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "Summer Beverage Campaign",
    "description": "10% off all items in the beverage category",
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

#### Error Responses

| Code | Situation | Message |
|------|-----------|---------|
| 400102 | Not found | Promotion not found |

---

### 5. Update Promotion

**PUT** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

#### Request

```json
{
  "name": "Summer Beverage Campaign (Extended)",
  "endDatetime": "2026-09-30T23:59:59",
  "detail": {
    "targetCategoryCodes": ["BEV001", "BEV002", "BEV003"],
    "discountRate": 15.0
  }
}
```

**Note**: `promotionCode` and `promotionType` cannot be changed.

#### Response (Success: 200)

```json
{
  "success": true,
  "code": 200,
  "message": "Promotion SUMMER2026_BEVERAGE updated successfully",
  "data": {
    "promotionCode": "SUMMER2026_BEVERAGE",
    "promotionType": "category_discount",
    "name": "Summer Beverage Campaign (Extended)",
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

### 6. Delete Promotion

**DELETE** `/api/v1/tenants/{tenant_id}/promotions/{promotion_code}`

Performs a soft delete (`is_deleted = true`).

#### Response (Success: 200)

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

## Common Error Codes

| Code | Description |
|------|-------------|
| 400101 | Duplicate promotion code |
| 400102 | Promotion not found |
| 400103 | Invalid date range |
| 400104 | Invalid discount type |
| 400105 | Invalid discount value |

---

## Schema Definitions

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
    target_store_codes: Optional[List[str]] = Field([], alias="targetStoreCodes")  # empty = all stores
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
