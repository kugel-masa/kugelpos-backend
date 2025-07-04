# Kugel POS Backend Services Architecture

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Service Architecture](#service-architecture)
4. [Technology Stack](#technology-stack)
5. [Data Architecture](#data-architecture)
6. [Communication Patterns](#communication-patterns)
7. [Security Architecture](#security-architecture)
8. [Design Patterns](#design-patterns)
9. [Deployment Architecture](#deployment-architecture)
10. [Error Handling](#error-handling)
11. [Performance Considerations](#performance-considerations)

## Overview

Kugel POS is a microservices-based Point of Sale (POS) backend system designed for retail businesses. The system provides comprehensive functionality for managing retail operations including user authentication, terminal management, product catalogs, shopping carts, sales reporting, and transaction journaling.

### Key Characteristics
- **Microservices Architecture**: 7 independent services with clear boundaries
- **Multi-tenant Support**: Database-level isolation for each tenant
- **Event-driven Communication**: Asynchronous messaging via Dapr pub/sub
- **RESTful APIs**: FastAPI-based services with OpenAPI documentation
- **Cloud-ready**: Designed for deployment on Azure Container Apps

## System Architecture

### High-Level Architecture

```
┌─────────────────┐
│  Frontend Apps  │
│   (POS, Web)    │
└────────┬────────┘
         │
┌────────▼────────┐
│  Load Balancer  │
│  (Azure ALB)    │
└────────┬────────┘
         │
┌────────▼────────────────────────────────────────────────┐
│              Container Environment (Azure)               │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Account  │  │ Terminal │  │  Master  │              │
│  │ Service  │  │ Service  │  │   Data   │              │
│  │  :8000   │  │  :8001   │  │  :8002   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │   Cart   │  │  Report  │  │ Journal  │              │
│  │ Service  │  │ Service  │  │ Service  │              │
│  │  :8003   │  │  :8004   │  │  :8005   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │          Dapr Service Mesh             │             │
│  │    (Pub/Sub, State Store, Sidecars)    │             │
│  └────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────┘
         │                              │
┌────────▼────────┐            ┌────────▼────────┐
│     MongoDB     │            │      Redis      │
│  (Cosmos DB)    │            │     Cache       │
└─────────────────┘            └─────────────────┘
```

### Service Map

| Service | Port | Description | Key Responsibilities |
|---------|------|-------------|---------------------|
| Account | 8000 | Authentication Service | User management, JWT token generation, role-based access control |
| Terminal | 8001 | Terminal Management | Store/terminal registration, API key management, open/close operations |
| Master Data | 8002 | Master Data Service | Product catalog, payment methods, tax rules, staff management |
| Cart | 8003 | Transaction Service | Shopping cart management, payment processing, state machine |
| Report | 8004 | Reporting Service | Sales reports, daily summaries, extensible report generation |
| Journal | 8005 | Journal Service | Electronic journal, transaction log storage and retrieval |
| Stock | 8006 | Stock Management | Inventory tracking, stock updates, transaction processing |

## Service Architecture

### 1. Account Service
- **Purpose**: Centralized authentication and authorization
- **Key Features**:
  - JWT token generation and validation
  - User account management (CRUD operations)
  - Role-based access control
  - Password hashing with bcrypt
- **API Endpoints**:
  - `POST /api/v1/accounts/token` - Generate JWT token
  - `GET /api/v1/accounts/token/valid` - Validate token
  - `POST /api/v1/accounts/users` - Create user
  - `GET /api/v1/accounts/users` - List users

### 2. Terminal Service
- **Purpose**: Terminal and store management
- **Key Features**:
  - Terminal registration and configuration
  - API key generation and validation
  - Store open/close operations
  - Cash in/out management
- **API Endpoints**:
  - `POST /api/v1/terminals/register` - Register terminal
  - `POST /api/v1/terminals/open` - Open store
  - `POST /api/v1/terminals/close` - Close store
  - `POST /api/v1/terminals/cash-in-out` - Cash operations
- **Events Published**:
  - `opencloselog_report` - Store open/close events
  - `cashlog_report` - Cash in/out events

### 3. Master Data Service
- **Purpose**: Centralized master data management
- **Key Features**:
  - Item/Product catalog management
  - Category management
  - Payment method configuration
  - Tax rule management
  - Staff master data
  - Store-specific pricing
- **Data Models**:
  - `ItemCommonMaster` - Global product information
  - `ItemStoreMaster` - Store-specific product data
  - `PaymentMaster` - Payment method configuration
  - `TaxMaster` - Tax calculation rules
  - `StaffMaster` - Employee information

### 4. Cart Service
- **Purpose**: Shopping cart and transaction processing with advanced state management
- **Key Features**:
  - State machine-based cart lifecycle with transition validation
  - Line item management with tax calculation
  - Payment processing with plugin architecture
  - Receipt generation with customizable strategies
  - Void/return operations with dual storage
  - Circuit breaker pattern for external service calls
- **State Machine**:
  ```
  initial → idle → entering_item → paying → completed
                ↘               ↗        ↘ cancelled
  ```
- **Plugin System** (configured via `plugins.json`):
  - **Payment Plugins**:
    - `PaymentByCash` (code "01"): Cash payments with change calculation
    - `PaymentByCashless` (code "11"): Electronic payments without change
    - `PaymentByOthers` (code "12"): Alternative payment methods
  - **Additional Strategies**:
    - Sales promotion strategies
    - Receipt data customization strategies
- **Dual Storage Pattern**:
  - Primary: MongoDB for persistent cart data
  - Secondary: Dapr state store for transaction state
  - Circuit breaker prevents cascade failures between storage layers
- **Events Published**:
  - `tranlog_report` - Transaction logs for reporting and stock updates
  - `tranlog_status` - Transaction status updates for delivery confirmation

### 5. Report Service
- **Purpose**: Sales reporting and analytics with extensible plugin architecture
- **Key Features**:
  - Daily sales reports with comprehensive aggregation
  - Terminal-based reports across multiple data sources
  - Time-based aggregations using MongoDB pipelines
  - Plugin-based report generation for extensibility
- **Plugin System** (configured via `plugins.json`):
  - **Report Plugins**:
    - `SalesReportMaker`: Processes transaction, cash, and open/close logs
    - Implements `IReportPlugin` interface for consistency
    - Uses MongoDB aggregation pipelines for efficient data processing
- **Report Types**:
  - Daily sales summary with tax breakdown
  - Terminal-specific reports
  - Time-based aggregations
  - Custom reports via plugin extensions
- **Data Processing**:
  - Multi-collection aggregation (transaction_logs, cash_logs, open_close_logs)
  - Configurable report scopes and filtering

### 6. Journal Service
- **Purpose**: Electronic journal and audit trail with dual storage architecture
- **Key Features**:
  - Dual storage pattern for specialized and unified logging
  - Idempotent event processing with state tracking
  - Atomic transaction handling across multiple collections
  - Search and retrieval APIs
  - Pagination support for large datasets
  - Time-based queries
- **Dual Storage Architecture**:
  - **Specialized Collections**: `transaction_logs`, `cash_logs`, `open_close_logs`
  - **Unified Collection**: `journals` for comprehensive audit trail
  - **Atomic Operations**: MongoDB transactions ensure consistency across both layers
- **Idempotency Handling**:
  - Event ID tracking via Dapr state store
  - Prevents duplicate processing of pub/sub events
  - State management for event processing status
- **Event Processing Pattern**:
  ```python
  async with session.start_transaction():
      # Create specialized log entry
      log_result = await specialized_collection.insert_one(log_data, session=session)
      # Create unified journal entry  
      journal_result = await journal_collection.insert_one(journal_data, session=session)
      # Mark event as processed
      await state_store.save_state(event_id, processed_data, session=session)
  ```
- **Data Types**:
  - Transaction logs with line item details
  - Cash in/out logs with audit trail
  - Terminal open/close logs with session tracking

### 7. Stock Service
- **Purpose**: Inventory management, stock tracking, and real-time alerts
- **Key Features**:
  - Real-time stock tracking with atomic updates
  - WebSocket-based stock alert system
  - Automated stock snapshot scheduling
  - Multi-store inventory support with tenant isolation
  - Reorder point and minimum stock monitoring
- **WebSocket Implementation**:
  - **Endpoint**: `/ws/{tenant_id}/{store_code}`
  - **Authentication**: JWT token validation for connections
  - **Alert Types**: `reorder_point`, `minimum_stock`
  - **Alert Structure**:
    ```json
    {
      "type": "stock_alert",
      "alert_type": "reorder_point|minimum_stock",
      "tenant_id": "tenant_001",
      "store_code": "store_001",
      "item_code": "ITEM_001",
      "current_quantity": 45.0,
      "reorder_point": 50.0,
      "minimum_quantity": 10.0,
      "reorder_quantity": 200.0,
      "timestamp": "2024-01-01T12:00:00Z"
    }
    ```
- **Background Processing**:
  - Automated snapshot creation with TTL-based cleanup
  - Alert cooldown mechanism (60-second default)
  - Automatic cleanup of old alert records (10-minute intervals)
- **API Endpoints**:
  - `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock` - Get all stock items
  - `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}` - Get specific item stock
  - `PUT /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update` - Update stock quantity
  - `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot` - Create stock snapshot
  - `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot` - Get stock snapshots
- **Events Subscribed**:
  - `tranlog_report` - Update stock based on transactions with idempotency handling

## Technology Stack

### Core Technologies
- **Language**: Python 3.12+
- **Web Framework**: FastAPI with automatic OpenAPI generation
- **ASGI Server**: Uvicorn for async request handling
- **Database**: MongoDB 7.0+ with replica set configuration
- **Cache**: Redis for caching and stream-based pub/sub
- **Service Mesh**: Dapr for service communication and state management
- **Real-time Communication**: WebSockets for live stock alerts
- **Container**: Docker with multi-stage builds
- **Orchestration**: Docker Compose / Azure Container Apps

### Key Libraries
- **Motor**: Async MongoDB driver
- **Pydantic**: Data validation and serialization
- **Beanie**: MongoDB ODM
- **PyJWT**: JWT token handling
- **Bcrypt**: Password hashing
- **Httpx**: Async HTTP client
- **Pytest**: Testing framework

### Development Tools
- **Pipenv**: Dependency management
- **Ruff**: Linting and formatting
- **Pytest-asyncio**: Async test support
- **Coverage.py**: Code coverage

## Data Architecture

### Database Design
- **Multi-tenant Architecture**: Each tenant has a separate MongoDB database
- **Database Naming Convention**: `{service_name}_{tenant_code}`
- **Collection Naming**: Snake_case (e.g., `item_master`, `transaction_log`)

### Document Models
All documents inherit from `BaseDocumentModel` which provides:
- `id`: Unique identifier
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `created_by`: User who created the record
- `updated_by`: User who last updated

### Data Flow
```
Frontend → API Gateway → Service → Repository → MongoDB
                              ↓
                          State Store (Redis)
                              ↓
                          Pub/Sub (Redis)
```

## Communication Patterns

### Synchronous Communication
- **REST APIs**: Service-to-service calls using unified HTTP clients
- **HttpClientHelper**: All inter-service REST calls use this unified client
  - Automatic retry mechanism (default: 3 attempts)
  - Circuit breaker pattern implementation
  - Connection pooling for performance
  - Service discovery support
- **Authentication**: JWT tokens with API key fallback
- **API Versioning**: All APIs versioned as `/api/v1/`

### Asynchronous Communication
- **Event-driven**: Dapr pub/sub with Redis streams
- **DaprClientHelper**: Unified client for all Dapr operations
  - Built-in circuit breaker (3 failures trigger, 60s recovery)
  - Automatic retry via HttpClientHelper
  - Non-blocking error handling
- **Topics**:
  - `tranlog_report`: Transaction data for reports
  - `tranlog_status`: Transaction status updates
  - `cashlog_report`: Cash in/out events
  - `opencloselog_report`: Terminal open/close events

### State Management
- **Dapr State Store**: Redis-based state management
- **Unified Access**: Via DaprClientHelper for consistency
- **Use Cases**:
  - Terminal cache in cart service
  - Daily counter management
  - Transaction status tracking
  - Idempotency key storage

## Security Architecture

### Dual Authentication System

#### JWT Token Authentication (Account Service)
**Implementation**: `services/account/app/dependencies/auth.py`

**Token Structure**:
```json
{
  "sub": "username",
  "tenant_id": "tenant_001", 
  "is_superuser": false,
  "is_service_account": false,
  "service": "optional_service_name",
  "exp": 1640995200
}
```

**Key Functions**:
- `create_access_token()`: JWT creation with configurable expiration
- `authenticate_user()`: Username/password/tenant validation
- `get_current_user()`: FastAPI dependency for protected routes
- `verify_token()`: Token validation with tenant extraction

#### API Key Authentication (Terminal Service)
**Implementation**: `services/commons/src/kugel_common/security.py`

**Features**:
- API keys stored in `TerminalInfoDocument.api_key` field
- Terminal ID format: `{tenant_id}-{store_code}-{terminal_no}`
- Special `PUBSUB_NOTIFY_API_KEY` for service-to-service communication
- API key header: `X-API-KEY`

**Authentication Functions**:
- `get_terminal_info()`: API key validation with terminal info retrieval
- `get_terminal_info_for_terminal_service()`: Direct database access
- `get_terminal_info_from_terminal_service()`: HTTP-based terminal lookup

### Authorization and Security
- **Role-based Access Control**: User roles defined in JWT claims with superuser privileges
- **Multi-tenancy**: Tenant isolation at database level with separate databases
- **WebSocket Security**: JWT token validation for WebSocket connections
- **Service-to-service Authentication**: Dedicated API keys for inter-service communication

### Security Best Practices
- Password hashing with bcrypt (JWT authentication)
- API keys stored as plain text for terminal authentication
- Environment variable-based configuration for sensitive data
- No secrets in code or application logs
- Multi-layer security validation for all endpoints

## Design Patterns

### 1. State Machine Pattern (Cart Service)
```python
class CartStateManager:
    states = {
        'initial': InitialState(),
        'idle': IdleState(),
        'entering_item': EnteringItemState(),
        'paying': PayingState(),
        'completed': CompletedState(),
        'cancelled': CancelledState()
    }
```

### 2. Plugin Architecture
- **Payment Methods**: Extensible payment processing
- **Sales Promotions**: Pluggable promotion rules
- **Report Generators**: Custom report formats

### 3. Repository Pattern
```python
class AbstractRepository:
    async def create(self, document: T) -> T
    async def find_by_id(self, id: str) -> Optional[T]
    async def update(self, id: str, document: T) -> Optional[T]
    async def delete(self, id: str) -> bool
```

### 4. Circuit Breaker Pattern
- **Implementation**: Built into HttpClientHelper and DaprClientHelper
- **States**: Closed → Open → Half-Open
- **Configuration**:
  - Failure threshold: 3 consecutive failures
  - Recovery timeout: 60 seconds
  - Applied to all HTTP and Dapr operations
- **Benefits**:
  - Prevents cascade failures
  - Fast fail for unavailable services
  - Automatic recovery attempts

### 5. Strategy Pattern
- Payment processing strategies
- Tax calculation strategies
- Receipt generation strategies

## Deployment Architecture

### Local Development
```yaml
# Docker Compose setup
services:
  mongodb:
    image: mongo:7.0
    command: ["--replSet", "rs0"]
  
  redis:
    image: redis:7-alpine
  
  account:
    build: ./account
    ports: ["8000:8000"]
```

### Production (Azure)
- **Azure Container Apps**: Serverless container hosting
- **Azure Cosmos DB**: MongoDB-compatible database
- **Azure Redis Cache**: Managed Redis service
- **Azure Load Balancer**: Traffic distribution
- **Azure Container Registry**: Container image storage

### Environment Configuration
1. Docker Compose environment variables
2. Service-specific .env files
3. Default values in settings classes
4. Priority: ENV vars > .env > defaults

## Error Handling

### Error Code Structure
Format: `XXYYZZ`
- `XX`: Service identifier
- `YY`: Feature/module identifier
- `ZZ`: Specific error number

### Service Error Ranges
- `10xx`: General errors
- `20xx`: Authentication errors
- `30xx`: Validation errors
- `401xx-404xx`: Cart service
- `405xx`: Master data service
- `406xx-407xx`: Terminal service
- `408xx-409xx`: Account service
- `410xx-411xx`: Journal service
- `412xx-413xx`: Report service

### Error Response Format
```json
{
  "success": false,
  "code": "401001",
  "message": "Cart not found",
  "data": null
}
```

## Performance Considerations

### Caching Strategy
- **Redis Cache**: Terminal information, master data
- **In-memory Cache**: Frequently accessed configuration
- **Cache Invalidation**: Event-driven cache updates

### Database Optimization
- **Indexes**: Created on frequently queried fields
- **Aggregation Pipeline**: Used for complex queries
- **Connection Pooling**: Motor async connection management

### Async Operations
- All database operations are async
- Non-blocking I/O throughout
- Concurrent request handling

### Scalability
- Stateless services (except cart state)
- Horizontal scaling via container orchestration
- Database sharding by tenant
- Event-driven architecture for decoupling

## Monitoring and Observability

### Logging
- Structured logging with correlation IDs
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging middleware
- Centralized log aggregation

### Health Checks
- `/health` endpoint on each service
- Database connectivity checks
- Redis connectivity checks
- Dependency health monitoring

### Metrics
- Request latency
- Error rates
- Transaction volumes
- Resource utilization

## Development Workflow

### Code Organization
```
service/
├── app/
│   ├── api/          # API endpoints
│   ├── config/       # Configuration
│   ├── models/       # Data models
│   ├── services/     # Business logic
│   └── main.py       # Application entry
├── tests/            # Test files
├── Pipfile           # Dependencies
└── Dockerfile        # Container definition
```

### Testing Strategy
- Unit tests for business logic
- Integration tests for APIs
- Repository tests with test database
- Async test support with pytest-asyncio

### CI/CD Pipeline
1. Code commit triggers build
2. Run tests and linting
3. Build Docker images
4. Push to container registry
5. Deploy to staging
6. Run integration tests
7. Deploy to production
