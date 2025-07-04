# Stock Service Model Specification

## Overview

Stock Service is a sophisticated inventory management system that provides real-time stock tracking, automated alerts, point-in-time snapshots, and comprehensive audit trails. The service implements event-driven stock updates via Dapr pub/sub, real-time WebSocket notifications for stock alerts, automated snapshot scheduling, and enterprise-grade multi-tenancy support. All operations are designed with atomic consistency, comprehensive audit trails, and race condition prevention to ensure data integrity in high-throughput POS environments.

## Database Document Models

All document models extend `AbstractDocument` which provides common fields for auditing, caching, and sharding.

### AbstractDocument (Base Class)

Base class providing common functionality for all documents.

**Base Fields:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| shard_key | string | - | Database sharding key for horizontal scaling |
| created_at | datetime | - | Document creation timestamp |
| updated_at | datetime | - | Last modification timestamp |
| cached_on | datetime | - | Cache timestamp for invalidation |
| etag | string | - | Entity tag for optimistic concurrency control |

### 1. StockDocument (Primary Inventory Storage)

Main document for tracking current inventory levels with reorder management capabilities.

**Collection Name:** `stocks`

**Purpose:** Real-time inventory tracking with alert threshold management

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| item_code | string | ✓ | Item/product code |
| current_quantity | float | ✓ | Current stock level (allows negative for backorders) |
| minimum_quantity | float | ✓ | Minimum stock threshold for alerts (default: 0.0) |
| reorder_point | float | ✓ | Reorder point threshold for automatic alerts (default: 0.0) |
| reorder_quantity | float | ✓ | Suggested quantity to order when reordering (default: 0.0) |
| last_transaction_id | string | - | Reference to last transaction that modified this stock |

**Indexes:**
- Unique compound index: (tenant_id, store_code, item_code)
- Index: tenant_id
- Index: store_code

**Business Rules:**
- Supports fractional quantities for weight-based items
- Allows negative stock for backorder scenarios
- Automatic alert evaluation after every update

### 2. StockUpdateDocument (Comprehensive Audit Trail)

Tracks complete history of all inventory changes with full context.

**Collection Name:** `stock_updates`

**Purpose:** Immutable audit trail for all stock modifications

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| item_code | string | ✓ | Item/product code |
| update_type | UpdateType | ✓ | Type of stock update (see enumeration below) |
| quantity_change | float | ✓ | Signed quantity change (+/-) |
| before_quantity | float | ✓ | Stock level before update |
| after_quantity | float | ✓ | Stock level after update |
| reference_id | string | - | Transaction/operation reference ID |
| timestamp | datetime | ✓ | UTC timestamp of update |
| operator_id | string | - | User/system that performed update |
| note | string | - | Optional explanatory note |

**Indexes:**
- Compound index: (tenant_id, store_code, item_code, timestamp DESC)
- Index: update_type
- Index: timestamp DESC
- Index: reference_id
- Compound index: (tenant_id, reference_id) for transaction correlation

**Audit Features:**
- Immutable records for regulatory compliance
- Complete before/after state tracking
- Operator accountability with user tracking
- Reference ID linking to source transactions

### 3. StockSnapshotDocument (Point-in-Time Inventory)

Periodic snapshots of complete store inventory for historical analysis.

**Collection Name:** `stock_snapshots`

**Purpose:** Point-in-time inventory records with automated retention management

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| total_items | integer | ✓ | Total number of distinct items in inventory |
| total_quantity | float | ✓ | Sum of all stock quantities |
| stocks | array[StockSnapshotItem] | ✓ | Complete inventory details |
| created_by | string | ✓ | User or system that created snapshot |
| generate_date_time | string | ✓ | ISO format timestamp for query filtering |

**Indexes:**
- Compound index: (tenant_id, store_code, created_at DESC)
- Compound index: (tenant_id, store_code, generate_date_time DESC)
- TTL index: created_at (configurable retention period)

**Automated Features:**
- TTL-based automatic cleanup
- Configurable retention policies per tenant
- Scheduled creation via background jobs

### 4. StockSnapshotItem (Embedded Inventory Record)

Embedded document within StockSnapshotDocument containing item-specific inventory state.

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| item_code | string | ✓ | Item/product code |
| quantity | float | ✓ | Stock quantity at snapshot time |
| minimum_quantity | float | ✓ | Minimum threshold at snapshot time |
| reorder_point | float | ✓ | Reorder point at snapshot time |
| reorder_quantity | float | ✓ | Reorder quantity at snapshot time |

### 5. SnapshotScheduleDocument (Automated Snapshot Configuration)

Per-tenant configuration for automated snapshot creation.

**Collection Name:** `snapshot_schedules`

**Purpose:** Tenant-specific automated snapshot scheduling

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier (unique constraint) |
| enabled | boolean | ✓ | Whether automated snapshots are enabled |
| schedule_interval | string | ✓ | Frequency: "daily", "weekly", "monthly" |
| schedule_hour | integer | ✓ | Hour of day to execute (0-23) |
| schedule_minute | integer | ✓ | Minute of hour to execute (0-59) |
| schedule_day_of_week | integer | - | Day of week for weekly (0=Monday) |
| schedule_day_of_month | integer | - | Day of month for monthly (1-31) |
| retention_days | integer | ✓ | Days to retain snapshots before cleanup |
| target_stores | array[string] | ✓ | Store codes or ["all"] for all stores |

**Indexes:**
- Unique index: tenant_id
- Index: enabled

### 6. StockAlertDocument (Alert State Tracking)

Tracks alert cooldown state to prevent notification spam.

**Collection Name:** `stock_alerts`

**Purpose:** Alert cooldown management and state tracking

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| item_code | string | ✓ | Item/product code |
| alert_type | string | ✓ | Alert type: "minimum_stock" or "reorder_point" |
| last_alert_time | datetime | ✓ | Last time alert was sent |
| cooldown_until | datetime | ✓ | Timestamp when cooldown expires |

**Indexes:**
- Unique compound index: (tenant_id, store_code, item_code, alert_type)
- TTL index: cooldown_until

## Enumerations

### UpdateType (Stock Update Categories)

Comprehensive enumeration for categorizing all types of stock modifications.

| Value | Description | Quantity Impact | Source |
|-------|-------------|----------------|---------|
| SALE | Regular sales transaction | Decrease (-) | Cart Service |
| RETURN | Customer return transaction | Increase (+) | Cart Service |
| VOID | Voided/canceled sale | Increase (+) | Cart Service |
| VOID_RETURN | Voided return transaction | Decrease (-) | Cart Service |
| PURCHASE | Inventory receipt/procurement | Increase (+) | Manual/Import |
| ADJUSTMENT | Manual stock adjustment | +/- | Manual |
| INITIAL | Initial stock setup | Set | Manual/Import |
| DAMAGE | Damaged/spoiled goods writeoff | Decrease (-) | Manual |
| TRANSFER_IN | Stock received from other location | Increase (+) | Transfer |
| TRANSFER_OUT | Stock sent to other location | Decrease (-) | Transfer |

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` which provides automatic snake_case to camelCase conversion for JSON serialization.

### Request Schemas

#### StockUpdateRequest

Manual stock adjustment request with full audit trail support.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| quantityChange | float | ✓ | Signed quantity change (positive for increase, negative for decrease) |
| updateType | UpdateType | ✓ | Type of update from enumeration |
| referenceId | string | - | Transaction or operation reference ID |
| operatorId | string | - | User performing the update |
| note | string | - | Optional explanatory note (max 500 chars) |

#### SetMinimumQuantityRequest

Set minimum stock threshold for alerts.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| minimumQuantity | float | ✓ | Minimum quantity threshold (≥ 0) |

#### SetReorderParametersRequest

Configure reorder point and quantity for automated ordering alerts.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| reorderPoint | float | ✓ | Quantity that triggers reorder alert (≥ 0) |
| reorderQuantity | float | ✓ | Suggested order quantity (≥ 0) |

#### CreateSnapshotRequest

Manual snapshot creation request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| createdBy | string | ✓ | User or system creating snapshot |

#### SnapshotScheduleCreateRequest

Configure automated snapshot scheduling for tenant.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| enabled | boolean | ✓ | Enable/disable automated snapshots |
| scheduleInterval | string | ✓ | "daily", "weekly", or "monthly" |
| scheduleHour | integer | ✓ | Hour of day (0-23) |
| scheduleMinute | integer | ✓ | Minute of hour (0-59) |
| scheduleDayOfWeek | integer | - | Day of week for weekly (0=Monday) |
| scheduleDayOfMonth | integer | - | Day of month for monthly (1-31) |
| retentionDays | integer | ✓ | Snapshot retention period |
| targetStores | array[string] | ✓ | Store codes or ["all"] |

### Response Schemas

#### StockResponse

Current stock information with all alert parameters.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| itemCode | string | Item/product code |
| currentQuantity | float | Current stock level |
| minimumQuantity | float | Minimum stock threshold |
| reorderPoint | float | Reorder point threshold |
| reorderQuantity | float | Suggested order quantity |
| lastUpdated | string | Last update timestamp (ISO format) |
| lastTransactionId | string | Last transaction reference |

#### StockUpdateResponse

Stock update history entry with complete audit information.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| itemCode | string | Item/product code |
| updateType | string | Update type |
| quantityChange | float | Quantity change amount |
| beforeQuantity | float | Stock before update |
| afterQuantity | float | Stock after update |
| referenceId | string | Reference ID if available |
| timestamp | string | Update timestamp (ISO format) |
| operatorId | string | Operator ID if available |
| note | string | Note if available |

#### StockSnapshotResponse

Complete inventory snapshot with summary statistics.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| totalItems | integer | Total number of items |
| totalQuantity | float | Total stock quantity |
| stocks | array[StockSnapshotItemResponse] | Detailed item inventory |
| createdBy | string | Snapshot creator |
| createdAt | string | Creation timestamp (ISO format) |
| generateDateTime | string | Generation timestamp for filtering |

#### SnapshotScheduleResponse

Automated snapshot schedule configuration.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| enabled | boolean | Whether automated snapshots are enabled |
| scheduleInterval | string | Schedule frequency |
| scheduleHour | integer | Execution hour |
| scheduleMinute | integer | Execution minute |
| scheduleDayOfWeek | integer | Day of week for weekly |
| scheduleDayOfMonth | integer | Day of month for monthly |
| retentionDays | integer | Snapshot retention period |
| targetStores | array[string] | Target store codes |

#### WebSocketAlertMessage

Real-time alert message sent via WebSocket connections.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| type | string | Alert type: "minimum_stock" or "reorder_point" |
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| itemCode | string | Item/product code |
| currentQuantity | float | Current stock level |
| threshold | float | Alert threshold (minimum_quantity or reorder_point) |
| timestamp | string | Alert timestamp (ISO format) |

## Event-Driven Architecture

### Dapr Pub/Sub Integration

The service processes stock updates via event-driven architecture with comprehensive idempotency and error handling.

#### Transaction Log Events (`topic-tranlog`)
- **Source**: Cart Service
- **Route**: `/api/v1/tranlog`
- **Content**: Complete transaction data with line items
- **Processing**: Updates stock levels for each transaction item

#### Event Processing Pipeline

**1. Message Reception and Validation:**
- Receive transaction events via Dapr pub/sub
- Validate message structure and extract event_id
- Check for required fields and data integrity

**2. Idempotency Management:**
- Check Dapr state store for duplicate event_id
- Skip processing if already handled
- Ensure exactly-once processing semantics

**3. Stock Update Processing:**
- Process each transaction item atomically
- Handle different transaction types (sales, returns, voids)
- Support cancelled transactions and individual cancelled items
- Update stock using MongoDB findAndModify for race condition prevention

**4. Alert Evaluation:**
- Check minimum stock and reorder point thresholds
- Send real-time WebSocket alerts if thresholds crossed
- Implement alert cooldown to prevent spam

**5. Acknowledgment and Status:**
- Send processing status back to Cart Service
- Store event processing state in Dapr state store
- Handle and report any processing errors

### Transaction Type Processing

**Sales Transactions (type 101):**
- Decrease stock by item quantities
- Handle cancelled items within transactions
- Support partial cancellations

**Return Transactions (type 102):**
- Increase stock by returned quantities
- Handle cancelled returns

**Void Transactions (types 201, 202):**
- Reverse original transaction impact
- Void sales: increase stock
- Void returns: decrease stock

## Real-Time WebSocket Alert System

### Connection Management

**WebSocket Endpoint:** `/ws/alerts/{tenant_id}/{store_code}`

**Authentication:**
- JWT token validation required for connection
- Tenant/store access verification
- Automatic connection termination on invalid tokens

**Connection Grouping:**
- Connections organized by tenant and store
- Broadcast capabilities to all store connections
- Automatic cleanup on disconnect

### Alert Types and Triggers

**Minimum Stock Alerts:**
- Triggered when: `current_quantity < minimum_quantity` AND `minimum_quantity > 0`
- Message type: "minimum_stock"
- Threshold: minimum_quantity value

**Reorder Point Alerts:**
- Triggered when: `current_quantity <= reorder_point` AND `reorder_point > 0`
- Message type: "reorder_point"
- Threshold: reorder_point value

### Alert Cooldown System

**Cooldown Management:**
- Prevents duplicate alerts for same item/type combination
- Default cooldown: 60 seconds (configurable via `ALERT_COOLDOWN_SECONDS`)
- Separate cooldowns for minimum_stock and reorder_point alerts
- Automatic cleanup of expired cooldown records via TTL indexes

**Initial Alert Delivery:**
- New WebSocket connections receive current alerts immediately
- Helps catch up on missed alerts during disconnection
- Only sends alerts for items currently below thresholds

## Automated Snapshot Scheduling

### Background Scheduler Service

**MultiTenantSnapshotScheduler:**
- APScheduler-based background service
- Per-tenant job management
- Distributed lock prevention for concurrent executions
- Dynamic schedule updates during runtime

### Schedule Management

**Supported Intervals:**
- **Daily**: Execute once per day at specified time
- **Weekly**: Execute on specific day of week
- **Monthly**: Execute on specific day of month

**Job Configuration:**
- Individual schedules per tenant
- Configurable execution time (hour/minute)
- Target store selection (all stores or specific stores)
- Automatic retry on failure

**Dynamic Updates:**
- Runtime addition/removal of schedules
- Automatic job rescheduling on configuration changes
- Graceful shutdown with job cleanup

### Snapshot Retention Management

**TTL-Based Cleanup:**
- Automatic deletion based on retention_days configuration
- MongoDB TTL indexes handle cleanup automatically
- Configurable per tenant for compliance requirements

**Retention Policies:**
- Default retention: 90 days
- Configurable per tenant
- Immediate cleanup when retention period changes

## Data Consistency and Atomicity

### Race Condition Prevention

**Atomic Stock Updates:**
- MongoDB findAndModify operations for atomic updates
- Upsert capability for new items
- Before/after quantity tracking in single operation
- Prevents lost updates in high-concurrency scenarios

**Optimistic Locking:**
- ETag-based optimistic locking via AbstractDocument
- Prevents overwriting concurrent modifications
- Automatic retry with exponential backoff

### Transaction Consistency

**MongoDB Transactions:**
- Stock updates and audit trail creation in single transaction
- Rollback capability on failures
- Ensures data consistency across collections

**Idempotent Processing:**
- Event ID tracking prevents duplicate processing
- Dapr state store for distributed idempotency
- Graceful handling of message redelivery

## Multi-Tenancy and Security

### Database Isolation

**Tenant Separation:**
- Separate MongoDB databases per tenant: `db_stock_{tenant_id}`
- Complete data isolation between tenants
- Tenant validation on all operations
- Shard key prefixing with tenant identifier

**Collection Structure Per Tenant:**
Each tenant database contains:
- `stocks`: Current inventory levels
- `stock_updates`: Audit trail
- `stock_snapshots`: Historical snapshots
- `snapshot_schedules`: Automation configuration
- `stock_alerts`: Alert cooldown tracking

### Authentication and Authorization

**Multi-Modal Authentication:**
- **JWT Tokens**: Primary authentication with tenant claims
- **API Keys**: Legacy support for external integrations
- **WebSocket Authentication**: Token-based WebSocket security

**Service-to-Service Communication:**
- Service tokens for Cart Service communication
- Dapr pub/sub security integration
- Circuit breaker patterns for external service calls

### Security Features

**Data Protection:**
- No cross-tenant data access possible
- Input validation and sanitization
- Audit trail for all modifications
- Secure WebSocket connections

**Access Control:**
- Tenant-based data filtering
- Store-level access restrictions
- Operation-level authorization checks

## Performance Optimization

### Indexing Strategy

**Query Optimization:**
- Compound indexes for multi-field queries
- Tenant-based sharding for horizontal scaling
- Timestamp indexes for temporal queries
- Reference ID indexes for transaction correlation

**Index Maintenance:**
- Regular index analysis and optimization
- TTL indexes for automatic data cleanup
- Partial indexes for conditional queries

### Caching and Performance

**WebSocket Connection Pooling:**
- Efficient connection management
- Group-based message broadcasting
- Automatic connection cleanup

**Database Optimization:**
- Connection pooling with Motor driver
- Aggregation pipeline optimization
- Projection limiting for large result sets

### Scalability Features

**Horizontal Scaling:**
- Tenant-based database sharding
- Stateless service design
- Load balancing capability
- Independent service scaling

**Background Processing:**
- Asynchronous event processing
- Background job scheduling
- Queue-based task management

## Validation Rules

### Stock Quantity Validation

**Business Rules:**
- `current_quantity`: Allows negative values for backorder support
- `minimum_quantity`: Must be ≥ 0
- `reorder_point`: Must be ≥ 0
- `reorder_quantity`: Must be ≥ 0
- `quantity_change`: Allows positive and negative values

**Data Integrity:**
- Atomic updates ensure consistency
- Before/after quantity validation
- Reference ID validation for transaction correlation

### API Request Validation

**Input Validation:**
- String length limits enforced
- Numeric range validation
- Enum value validation for update types
- Required field validation

**Security Validation:**
- Tenant access authorization
- Store access restrictions
- Input sanitization for security

## Error Handling and Monitoring

### Exception Management

**Structured Error Handling:**
- Custom exception hierarchy for stock operations
- Detailed error context in responses
- Transaction rollback on failures

**Error Recovery:**
- Automatic retry for transient failures
- Dead letter queue for persistent failures
- Circuit breaker patterns for external services

### Health Monitoring

**Service Health Checks:**
- Database connectivity monitoring
- Dapr sidecar health verification
- WebSocket connection health
- Background job status monitoring

**Performance Metrics:**
- Stock update latency tracking
- Alert delivery performance
- Snapshot creation timing
- Database query performance

This comprehensive model specification demonstrates the Stock Service's role as a sophisticated inventory management system with real-time capabilities, automated operations, comprehensive audit trails, and enterprise-grade reliability. The combination of event-driven processing, WebSocket alerts, automated scheduling, and robust multi-tenancy provides a scalable foundation for modern POS inventory management.