# Kugelpos Design Patterns Specification

## Overview

The Kugelpos system implements the following key design patterns to improve maintainability, extensibility, and testability. Each pattern is designed based on actual business requirements and can be verified as concrete implementation code.

## Implemented Design Patterns

### 1. State Machine Pattern (Cart Service)

**Implementation Location:** `/services/cart/app/services/cart_state_manager.py`

**Purpose:** Cart lifecycle management and prevention of invalid operations

**State Transitions:**
```
initial → idle → entering_item → paying → completed
               ↘               ↗        ↘ cancelled
```

**Main Classes:**
- `CartStateManager`: Controls state transitions
- `AbstractState`: Base class for all states
- Concrete states: `InitialState`, `IdleState`, `EnteringItemState`, `PayingState`, `CompletedState`, `CancelledState`

**Features:**
- Clearly defines allowed operations for each state
- Applies business rules according to state
- Prevents invalid state transitions

### 2. Plugin Architecture

**Implementation Locations:**
- Cart Service: `/services/cart/app/services/strategies/`
- Report Service: `/services/report/app/services/plugins/`

**Plugin Configuration:** `plugins.json`
```json
{
    "payment_strategies": [
        {
            "module": "app.services.strategies.payments.cash",
            "class": "PaymentByCash",
            "args": ["01"]
        }
    ]
}
```

**Main Features:**
- Dynamic plugin loading (using importlib)
- Runtime switching of payment strategies
- Pluginized sales promotion rules
- Customizable report generators

**Plugin Manager:** `CartStrategyManager`
- Dynamically loads plugins from JSON configuration
- Runtime strategy selection and execution

### 3. Repository Pattern

**Implementation Location:** `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`

**Base Class:** `AbstractRepository[Tdocument]`
- Generic type support
- Standardized CRUD operations
- Optimistic locking with retry
- Pagination support
- Transaction management

**Main Methods:**
```python
async def create_async(self, document: Tdocument) -> bool
async def get_one_async(self, filter: dict) -> Tdocument
async def update_one_async(self, filter: dict, new_values: dict) -> bool
async def find_with_pagination_async(...) -> Tuple[List[Tdocument], int]
```

**Features:**
- Abstraction of data access layer
- Separation of business logic and DB operations
- Unified error handling

### 4. Circuit Breaker Pattern

**Implementation Locations:**
- `HttpClientHelper`: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- `DaprClientHelper`: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**Configuration:**
- Failure threshold: 3 consecutive failures
- Recovery timeout: 60 seconds
- States: CLOSED → OPEN → HALF_OPEN

**Target Operations:**
- External HTTP service calls
- Dapr pub/sub operations
- Dapr state store operations

**Unified Error Handling:**
- Automatic retry (3 attempts, exponential backoff)
- Prevention of cascade failures
- Fast fail functionality

### 5. Strategy Pattern

**Implementation Locations:**
- Payment strategies: `/services/cart/app/services/strategies/payments/`
- Tax calculation: `/services/cart/app/services/logics/calc_tax_logic.py`

**Abstract Strategy:** `AbstractPayment`
```python
async def pay(self, cart_doc, payment_code, amount, detail)
async def refund(self, cart_doc, payment_index)
async def cancel(self, cart_doc, payment_index)
```

**Concrete Strategies:**
- `PaymentByCash`: Cash payment (change calculation)
- `PaymentByCashless`: Cashless payment (overpayment check)

**Tax Calculation Strategies:**
- External tax calculation: Add tax amount to price
- Internal tax calculation: Tax amount included in price
- Tax-free: No tax amount

### 6. Factory Pattern

**Implementation Location:** `CartStrategyManager`

**Features:**
- Strategy instance creation based on payment codes
- Instance creation by promotion type
- Dynamic object creation driven by configuration files

### 7. Template Method Pattern

**Implementation Location:** `AbstractState`

**Processing Flow:**
1. Event permission check
2. Pre-processing
3. Main processing (subclass implementation)
4. Post-processing

## Unified Communication Architecture

### HttpClientHelper

**Features:**
- Automatic retry mechanism
- Connection pooling
- Built-in circuit breaker
- Service discovery support

**Usage Example:**
```python
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items")
```

### DaprClientHelper

**Features:**
- Unified interface for Dapr operations
- Integration of pub/sub and state store
- Circuit breaker protection
- Non-blocking error handling

**Usage Example:**
```python
async with get_dapr_client() as client:
    await client.publish_event("pubsub", "topic", data)
```

## Synergistic Effects of Pattern Combinations

### Synergistic Effects

1. **State Machine + Strategy**
   - Selection of payment strategies according to state
   - Clear separation of business rules

2. **Repository + Circuit Breaker**
   - High reliability of data access
   - Appropriate failover during failures

3. **Plugin + Factory**
   - Dynamic feature extension at runtime
   - Configuration-driven customization

### Maintainability Improvement

- **Single Responsibility Principle**: Each pattern has clear responsibilities
- **Open-Closed Principle**: Open for extension, closed for modification
- **Dependency Inversion**: Depend on abstractions, not concretions

### Testability

- **Mockability**: Mock implementations for each interface
- **Independence**: Isolated tests for each pattern
- **State Testing**: Comprehensive testing of state transitions

## Important Implementation Considerations

### Performance Optimization

- **Asynchronous Processing**: Utilize asyncio in all patterns
- **Resource Management**: Proper resource cleanup
- **Caching**: Reuse of strategy instances

### Error Handling

- **Unified Exception System**: Utilize custom exception classes
- **Graceful Degradation**: Continued operation during partial failures
- **Log Integration**: Traceability through structured logs

### Configuration Management

- **External Configuration**: JSON/YAML configuration files
- **Environment Variables**: Runtime parameter adjustment
- **Default Values**: Guaranteed operation without configuration

Through this combination of design patterns, Kugelpos provides a solution that combines maintainability and extensibility for complex POS business requirements.