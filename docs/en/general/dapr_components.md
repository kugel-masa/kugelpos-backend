# Kugelpos Dapr Components Specification

## Overview

The Kugelpos system uses Dapr (Distributed Application Runtime) for the following purposes:

- **State Store**: Redis-based caching and idempotency management
- **Pub/Sub Messaging**: Event-driven communication between services
- **Circuit Breaker**: Appropriate failover during failures

## Dapr Component Configuration

### State Store Components

#### 1. statestore (General State Store)

**Configuration File:** `/services/dapr/components/statestore.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "3600"
  - name: databaseIndex
    value: "1"
```

**Use Cases:**
- Idempotency management (duplicate event prevention)
- Tracking processed event IDs
- Circuit breaker backup functionality

**Used by Services:** Report, Journal, Stock

#### 2. cartstore (Cart-specific State Store)

**Configuration File:** `/services/dapr/components/cartstore.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: cartstore
spec:
  type: state.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "36000"
  - name: databaseIndex
    value: "2"
```

**Use Cases:**
- Cart document caching
- State retention during transactions
- MongoDB complement for high-speed access

**Used by Services:** Cart

### Pub/Sub Components

#### 1. pubsub-tranlog-report (Transaction Log Distribution)

**Configuration File:** `/services/dapr/components/pubsub_tranlog_report.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: pubsub-tranlog-report
spec:
  type: pubsub.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: consumerID
    value: kugelpos-tranlog-consumer
  - name: processingTimeout
    value: "180s"
```

**Event Flow:**
- **Publisher:** Cart Service
- **Subscribers:** Report Service, Journal Service, Stock Service
- **Topics:** Transaction completion, cancellation, refund

#### 2. pubsub-cashlog-report (Cash In/Out Log Distribution)

**Configuration File:** `/services/dapr/components/pubsub_cashlog_report.yaml`

**Event Flow:**
- **Publisher:** Terminal Service
- **Subscribers:** Report Service, Journal Service
- **Topics:** Cash in, cash out

#### 3. pubsub-opencloselog-report (Open/Close Log Distribution)

**Configuration File:** `/services/dapr/components/pubsub_opencloselog_report.yaml`

**Event Flow:**
- **Publisher:** Terminal Service
- **Subscribers:** Report Service, Journal Service
- **Topics:** Store open, store close

## Service-specific Dapr Usage Patterns

### Account Service
- **Dapr Usage:** None
- **Communication:** Direct HTTP (JWT issuance/verification)

### Terminal Service
- **Dapr Usage:** Pub/Sub (Publisher)
- **Published Events:**
  - `cashlog_report`: Cash in/out
  - `opencloselog_report`: Store open/close
- **Implementation:** PubsubManager → DaprClientHelper

### Master-data Service
- **Dapr Usage:** None
- **Communication:** Direct HTTP (master data provision)

### Cart Service
- **Dapr Usage:** State Store + Pub/Sub
- **State Store:** `cartstore` (cart caching)
- **Published Events:** `tranlog_report` (transaction logs)
- **Pattern:** State Machine + Plugin

### Report Service
- **Dapr Usage:** State Store + Pub/Sub (Subscriber)
- **State Store:** `statestore` (idempotency management)
- **Received Events:** All types of logs
- **Plugin:** Report generators

### Journal Service
- **Dapr Usage:** State Store + Pub/Sub (Subscriber)
- **State Store:** `statestore` (idempotency management)
- **Received Events:** All types of logs
- **Function:** Electronic journal storage

### Stock Service
- **Dapr Usage:** State Store + Pub/Sub (Subscriber)
- **State Store:** `statestore` (idempotency management)
- **Received Events:** `tranlog_report` (inventory updates)
- **Additional Function:** WebSocket alerts (non-Dapr dependent)

## Unified Dapr Client Implementation

### DaprClientHelper

**Implementation Location:** `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**Main Features:**
- Built-in circuit breaker (3 failures for 60-second block)
- Automatic retry mechanism
- Unified API for pub/sub and state store
- Non-blocking error handling

**Usage Example:**
```python
async with get_dapr_client() as client:
    # Publish event
    await client.publish_event("pubsub-tranlog-report", "tranlog_topic", data)
    
    # Save state
    await client.save_state("statestore", "event_123", {"processed": True})
    
    # Get state
    state = await client.get_state("statestore", "event_123")
```

### Migration from Legacy Implementation

**Migrated:**
- `PubsubManager` → `DaprClientHelper`
- `StateStoreManager` → `DaprClientHelper`

**Benefits of Unification:**
- Consistent error handling
- Integrated circuit breaker
- Centralized configuration

## Event-Driven Architecture Patterns

### Fan-out Pattern

```
Cart Service → tranlog_report → ┌─ Report Service
                               ├─ Journal Service
                               └─ Stock Service

Terminal Service → cashlog_report → ┌─ Report Service
                                   └─ Journal Service

Terminal Service → opencloselog_report → ┌─ Report Service
                                        └─ Journal Service
```

### Idempotency Guarantee Pattern

**Implementation:**
1. Check event_id when receiving event
2. Execute business logic only if unprocessed
3. Record event_id after processing completion

**Code Example:**
```python
async def handle_tranlog_event(event_data):
    event_id = event_data.get("event_id")
    
    # Idempotency check
    if await state_manager.is_processed(event_id):
        logger.info(f"Event {event_id} already processed")
        return
    
    # Execute business logic
    await process_transaction_log(event_data)
    
    # Mark as processed
    await state_manager.mark_processed(event_id)
```

## Redis Configuration and Database Separation

### Database Index Assignment

| DB Index | Purpose | TTL | Used by Services |
|----------|---------|-----|------------------|
| 0 | Redis default | - | Unused |
| 1 | statestore (idempotency) | 1 hour | Report, Journal, Stock |
| 2 | cartstore (caching) | 10 hours | Cart |
| 3 | terminalstore | - | Unused |

### TTL Configuration Rationale

- **statestore (1 hour)**: Short-term storage needed for event duplication prevention
- **cartstore (10 hours)**: Medium-term storage to support long-duration transactions

## Performance Considerations

### Connection Pool Configuration

```python
# httpx.AsyncClient configuration
timeout=httpx.Timeout(30.0)
limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
```

### Batch Processing

- No batch size limit for message reception
- Sequential processing prioritizes reliability
- Circuit breaker protection during failures

### Monitoring Metrics

- **Connection Count**: Active Dapr connections
- **Circuit Breaker Status**: CLOSED/OPEN/HALF_OPEN
- **Event Processing Rate**: Success/failure/skip
- **Latency**: pub/sub delivery time

## Operational Considerations

### Circuit Breaker Behavior

1. **CLOSED (Normal)**: All requests pass through
2. **OPEN (Blocked)**: All requests immediately fail
3. **HALF_OPEN (Recovery Attempt)**: Test request determines state

### Failure Behavior

- **Redis Failure**: State store fallback, tolerate duplicate processing
- **Pub/Sub Failure**: Skip event delivery, log records
- **Network Failure**: Automatic retry, exponential backoff

### Impact of Configuration Changes

- **TTL Changes**: No impact on existing data, applies to new data
- **DB Index Changes**: Existing data inaccessible, requires careful migration
- **Timeout Changes**: Immediate effect, ongoing requests continue