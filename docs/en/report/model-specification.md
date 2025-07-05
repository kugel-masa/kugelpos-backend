# Report Service Model Specification

## Overview

This document provides the data model specifications for the Report service, including MongoDB collection structures, schema definitions, and data flows.

## Database Design

### Database Name
- `{tenant_id}_report` (e.g., `tenant001_report`)

### Collection List

| Collection Name | Purpose | Main Data |
|---------------|------|------------|
| report_transactions | Transaction log storage | Transaction data from Cart |
| report_cashinout | Cash in/out log storage | Cash operation data from Terminal |
| report_open_close | Open/close log storage | Open/close data from Terminal |
| report_daily_info | Daily information storage | Metadata for daily aggregation |
| report_aggregate_data | Aggregated data storage | Generated report data |

## Detailed Schema Definitions

### 1. report_transactions Collection

Collection storing transaction logs. Converts BaseTransaction to TransactionLogModel for storage.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "tran_id": "string",
  "tran_seq": "integer",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "transaction_type": "string (purchase/refund/exchange/void)",
  "transaction_time": "datetime",
  "void_flag": "boolean",
  "items": [
    {
      "item_id": "string",
      "item_name": "string",
      "quantity": "integer",
      "unit_price": "decimal",
      "amount": "decimal",
      "discount_amount": "decimal",
      "tax_info": {
        "tax_code": "string",
        "tax_type": "string",
        "tax_name": "string",
        "target_amount": "decimal",
        "tax_amount": "decimal"
      }
    }
  ],
  "transaction_discount": "decimal",
  "item_total": "decimal",
  "excluded_tax_total": "decimal",
  "included_tax_total": "decimal",
  "tax_total": "decimal",
  "discount_total": "decimal",
  "total_amount": "decimal",
  "payments": [
    {
      "payment_code": "string",
      "payment_name": "string",
      "amount": "decimal",
      "change_amount": "decimal"
    }
  ],
  "tax_aggregation": [
    {
      "tax_code": "string",
      "tax_type": "string",
      "tax_name": "string",
      "item_count": "integer",
      "target_amount": "decimal",
      "tax_amount": "decimal"
    }
  ],
  "staff_id": "string",
  "customer_id": "string",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 2. report_cashinout Collection

Collection storing cash in/out logs.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "cashinout_id": "string",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "operation_type": "string (cash_in/cash_out)",
  "operation_time": "datetime",
  "amount": "decimal",
  "reason": "string",
  "staff_id": "string",
  "comment": "string",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 3. report_open_close Collection

Collection storing open/close logs.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "operation_type": "string (open/close)",
  "operation_time": "datetime",
  "cash_amount": "decimal",
  "staff_id": "string",
  "open_time": "datetime (close operations only)",
  "close_time": "datetime (close operations only)",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. report_daily_info Collection

Collection storing daily information. Manages terminal-specific status.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "business_date": "string (YYYYMMDD)",
  "terminal_info": [
    {
      "terminal_no": "integer",
      "is_closed": "boolean",
      "close_time": "datetime",
      "transaction_count": "integer",
      "cashinout_count": "integer",
      "last_open_counter": "integer",
      "last_business_counter": "integer"
    }
  ],
  "all_terminals_closed": "boolean",
  "daily_report_generated": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 5. report_aggregate_data Collection

Generic collection storing aggregated data. Stores both flash and daily reports.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer (null for store total)",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer (flash only)",
  "report_scope": "string (flash/daily)",
  "report_type": "string (sales/category/item)",
  "report_data": {
    "sales_gross": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "sales_net": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "discount_for_lineitems": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "discount_for_subtotal": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "returns": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "taxes": [
      {
        "tax_code": "string",
        "tax_type": "string",
        "tax_name": "string",
        "item_count": "integer",
        "target_amount": "decimal",
        "tax_amount": "decimal"
      }
    ],
    "payments": [
      {
        "payment_code": "string",
        "payment_name": "string",
        "transaction_count": "integer",
        "total_amount": "decimal"
      }
    ],
    "cash": {
      "cash_in_count": "integer",
      "cash_in_amount": "decimal",
      "cash_out_count": "integer",
      "cash_out_amount": "decimal",
      "net_cash_movement": "decimal"
    },
    "receipt_text": "string",
    "journal_text": "string"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Index Definitions

### report_transactions
- Compound index: `tenant_id + store_code + terminal_no + business_date + tran_id` (unique)
- Compound index: `tenant_id + store_code + business_date + open_counter`
- Single index: `event_id` (unique)
- Single index: `created_at`

### report_cashinout
- Compound index: `tenant_id + store_code + terminal_no + business_date`
- Compound index: `tenant_id + store_code + business_date + open_counter`
- Single index: `event_id` (unique)
- Single index: `created_at`

### report_open_close
- Compound index: `tenant_id + store_code + terminal_no + business_date + operation_type`
- Compound index: `tenant_id + store_code + business_date + open_counter`
- Single index: `event_id` (unique)
- Single index: `created_at`

### report_daily_info
- Compound index: `tenant_id + store_code + business_date` (unique)
- Single index: `all_terminals_closed`

### report_aggregate_data
- Compound index: `tenant_id + store_code + terminal_no + business_date + report_scope + report_type`
- Compound index: `tenant_id + store_code + business_date + open_counter + report_scope + report_type`

## Data Flow

### Event-Driven Data Flow

1. **Transaction Log Processing**
   - Topic: `tranlog_report`
   - Source: Cart service
   - Processing flow:
     1. Receive BaseTransaction
     2. Duplicate check by event_id (using Dapr state store)
     3. Convert to TransactionLogModel
     4. Save to report_transactions
     5. Update aggregated data

2. **Cash In/Out Log Processing**
   - Topic: `cashlog_report`
   - Source: Terminal service
   - Processing flow:
     1. Receive BaseCashInOut
     2. Duplicate check by event_id
     3. Convert to CashInOutLogModel
     4. Save to report_cashinout
     5. Update cash movement aggregation

3. **Open/Close Log Processing**
   - Topic: `opencloselog_report`
   - Source: Terminal service
   - Processing flow:
     1. Receive BaseOpenClose
     2. Duplicate check by event_id
     3. Convert to OpenCloseLogModel
     4. Save to report_open_close
     5. Update report_daily_info

### Report Generation Flow

1. **Flash Report**
   - Real-time aggregation of event data
   - Generated per terminal or store-wide
   - Saved to report_aggregate_data (report_scope="flash")

2. **Daily Report**
   - Generated after confirming all terminals are closed
   - State management via report_daily_info
   - Data validation (log count consistency check)
   - Saved to report_aggregate_data (report_scope="daily")

## Plugin Architecture

### Report Plugin Interface
```python
class IReportPlugin(ABC):
    async def generate_report(
        self,
        store_code: str,
        terminal_no: int,
        business_counter: int,
        business_date: str,
        open_counter: int,
        report_scope: str,
        report_type: str,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
    ) -> dict[str, any]
```

### Implemented Plugins
- **SalesReportPlugin**: Sales report generation
- **CategoryReportPlugin**: Category-wise reports (not implemented)
- **ItemReportPlugin**: Item-wise reports (not implemented)

## Special Notes

1. **Idempotency**: Duplicate prevention by event_id and processed event management via Dapr state store
2. **Multi-tenancy**: Complete isolation with tenant ID included in database name
3. **Performance**: Appropriate indexes and caching of aggregated data
4. **Extensibility**: Addition of new report types via plugin architecture
5. **Circuit Breaker**: External communication failure handling via DaprClientHelper
6. **Data Integrity**: Strict data validation before daily report generation