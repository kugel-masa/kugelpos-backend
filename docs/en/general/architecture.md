# Kugelpos System Architecture

## Overview

Kugelpos is a POS backend system built on microservices architecture, utilizing FastAPI, MongoDB, Dapr, and Redis as core technologies to achieve high availability and scalability.

## System Configuration

### Core Services

| Service | Port | Responsibilities | Implementation Location |
|---------|------|------------------|------------------------|
| Account | 8000 | JWT authentication, user management | `/services/account/` |
| Terminal | 8001 | Terminal/store management, open/close operations | `/services/terminal/` |
| Master-data | 8002 | Product/master data management | `/services/master-data/` |
| Cart | 8003 | Cart/transaction processing (state machine) | `/services/cart/` |
| Report | 8004 | Report generation (plugin-based) | `/services/report/` |
| Journal | 8005 | Electronic journal, audit logs | `/services/journal/` |
| Stock | 8006 | Inventory management, WebSocket alerts | `/services/stock/` |

### Technology Stack

**Frameworks & Libraries:**
- Python 3.12+ with FastAPI
- MongoDB (Motor async driver)
- Redis (caching & pub/sub)
- Dapr (service mesh & state management)
- Docker & Docker Compose

**Common Libraries:**
- `kugel_common`: Common functionality module
  - Implementation: `/services/commons/src/kugel_common/`
  - BaseSchemaModel, AbstractRepository, error handling

## Inter-Service Communication

### 1. HTTP Communication (Synchronous)

**HttpClientHelper Unified Implementation:**
- Implementation: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- Features:
  - Auto-retry (3 attempts, exponential backoff)
  - Connection pooling
  - Circuit breaker pattern
  - Service discovery support

```python
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})
```

### 2. Event Communication (Asynchronous)

**DaprClientHelper Unified Implementation:**
- Implementation: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`
- Features:
  - Built-in circuit breaker (3 failures for 60-second block)
  - Auto-retry mechanism
  - Non-blocking error handling

**Pub/Sub Topics:**
- `tranlog_report`: Cart → Report/Journal/Stock
- `tranlog_status`: Cart internal status updates
- `cashlog_report`: Terminal → Report/Journal
- `opencloselog_report`: Terminal → Report/Journal

```python
async with get_dapr_client() as client:
    await client.publish_event("pubsub", "tranlog_report", transaction_data)
```

## Data Architecture

### Multi-Tenant Design

**Database Separation:**
- Pattern: `{tenant_id}_{service_name}`
- Example: `tenant001_cart`, `tenant001_stock`
- Complete tenant data isolation

**Collection Naming Convention:**
- snake_case format
- Example: `item_master`, `transaction_log`, `cart_documents`

### Base Document Model

Implementation: `/services/commons/src/kugel_common/models/document/base_document_model.py`

```python
class BaseDocumentModel:
    id: ObjectId
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]
```

## Architecture Patterns

### 1. State Machine Pattern (Cart Service)

**Implementation:** `/services/cart/app/services/cart_state_manager.py`

**State Transitions:**
```
initial → idle → entering_item → paying → completed
               ↘               ↗        ↘ cancelled
```

**State Implementation:**
- InitialState, IdleState, EnteringItemState, PayingState
- CompletedState, CancelledState
- Each state defines allowed operations

### 2. Plugin Architecture

**Cart Service Implementation:**
- Payment strategies: `/services/cart/app/services/strategies/payments/`
- Sales promotions: `/services/cart/app/services/strategies/promotions/`
- Configuration file: `plugins.json`

**Report Service Implementation:**
- Report generators: `/services/report/app/services/plugins/`
- Dynamic plugin loading functionality

### 3. Repository Pattern

**Implementation:** `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`

```python
class AbstractRepository(ABC, Generic[Tdocument]):
    async def create_async(self, document: Tdocument) -> bool
    async def get_one_async(self, filter: dict) -> Tdocument
    async def update_one_async(self, filter: dict, new_values: dict) -> bool
```

**Features:**
- Generic type support
- Optimistic locking with retry
- Pagination support

### 4. Circuit Breaker Pattern

**Implementation:**
- HttpClientHelper: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- DaprClientHelper: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**Configuration:**
- Failure threshold: 3 consecutive failures
- Recovery timeout: 60 seconds
- States: CLOSED → OPEN → HALF_OPEN

**Target Operations:**
- External HTTP service calls
- Dapr pub/sub operations
- Dapr state store operations

## Security Architecture

### Authentication & Authorization

**JWT Authentication:**
- Issuer: Account Service
- Verification: Independent implementation in each service
- Bearer Token format

**API Key Authentication:**
- Terminal-specific API keys (Terminal Service)
- SHA-256 hashed storage

**Multi-Tenant Separation:**
- Database-level separation
- Strict access control by tenant ID

### Data Protection

- bcrypt password hashing
- Secret management via environment variables
- MongoDB replica set configuration

## Performance Design

### Asynchronous Processing

**Async I/O:**
- Motor (MongoDB async driver)
- httpx (HTTP async client)
- FastAPI async endpoints

**Concurrent Processing:**
- asyncio-based parallel processing
- Non-blocking I/O operations

### Caching Strategy

**Redis Cache:**
- Terminal info caching (Cart Service)
- Daily counter management
- Session management

**Dapr State Store:**
- Cart state management
- Idempotency key storage
- Transaction status tracking

### Index Optimization

**MongoDB Optimization:**
- Compound indexes (tenant_id + business key)
- TTL indexes (automatic data deletion)
- Partial indexes (conditional)

## Error Handling

### Unified Error Code System

**Format:** XXYYZZ
- XX: Service identifier
- YY: Feature/module identifier
- ZZ: Specific error number

**Service Ranges:**
- 10XXX: Account Service
- 20XXX: Terminal Service
- 30XXX: Master-data Service
- 40XXX: Cart Service
- 41XXX: Report Service
- 42XXX: Journal Service
- 43XXX: Stock Service

### Multi-Language Error Messages

**Implementation:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

```python
class ErrorMessage:
    MESSAGES = {
        "ja": {"10001": "認証に失敗しました"},
        "en": {"10001": "Authentication failed"}
    }
```

## Operations & Monitoring

### Health Checks

**Common Endpoint:** `GET /health`
- Database connection verification
- Redis connection verification
- Dependent service verification

### Log Management

**Unified Logging:**
- Python logging module
- JSON structured logs
- Request/response tracking

### Metrics

**Performance Indicators:**
- Response time
- Error rate
- Connection count (WebSocket)
- Circuit breaker status

## Deployment

### Development Environment

**Docker Compose Configuration:**
```yaml
services:
  mongodb:
    image: mongo:7.0
    command: ["--replSet", "rs0"]
  redis:
    image: redis:7-alpine
  # Service definitions
```

### Production Considerations

**Scalability:**
- Stateless design (except Cart)
- Horizontal scaling support
- Load balancer support

**High Availability:**
- MongoDB replica set
- Redis Cluster (recommended)
- Dapr High Availability mode