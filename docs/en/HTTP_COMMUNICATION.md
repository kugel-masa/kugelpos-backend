# HTTP Communication Patterns

This document describes the unified HTTP communication patterns used throughout the Kugelpos microservices architecture.

## Overview

All HTTP communication in Kugelpos follows a consistent pattern using specialized helper classes:
- **HttpClientHelper**: Provides retry logic and connection pooling for REST APIs
- **DaprClientHelper**: Provides circuit breaker pattern for Dapr sidecar communication

## Communication Types

### 1. Inter-Service REST Communication

All direct service-to-service REST API calls use `HttpClientHelper`:

```python
from kugel_common.utils.http_client_helper import get_service_client

async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})
```

**Features:**
- Automatic retry (default: 3 attempts)
- Connection pooling
- Service discovery
- Unified error handling

**Used by:**
- `ItemMasterWebRepository` (Cart → Master Data)
- `PaymentMasterWebRepository` (Cart → Master Data) 
- `SettingsMasterWebRepository` (Cart → Master Data)
- `TranlogWebRepository` (Terminal → Cart)
- `TerminalInfoWebRepository` (Report → Terminal)
- `StoreInfoWebRepository` (Commons → Terminal)
- `StaffMasterWebRepository` (Commons → Master Data)

### 2. Dapr Communication

All Dapr sidecar communication uses `DaprClientHelper`:

```python
from kugel_common.utils.dapr_client_helper import get_dapr_client

async with get_dapr_client() as client:
    # Pub/Sub
    await client.publish_event("pubsub", "topic", {"message": "data"})
    
    # State Store
    await client.save_state("statestore", "key", {"value": "data"})
    data = await client.get_state("statestore", "key")
```

**Features:**
- Circuit breaker pattern
- Automatic retry via HttpClientHelper
- Proper response parsing for Dapr APIs
- Non-blocking error handling

**Used by:**
- `PubsubManager` (Cart, Terminal)
- `StateStoreManager` (Report, Journal)

## Circuit Breaker Pattern

The circuit breaker pattern is implemented in DaprClientHelper to prevent cascade failures:

### States
1. **Closed** (Normal Operation)
   - All requests pass through
   - Failures are counted

2. **Open** (Failure State)
   - All requests fail immediately
   - No load on failing service
   - Activated after threshold failures

3. **Half-Open** (Recovery Test)
   - Limited requests allowed
   - Success → return to Closed
   - Failure → return to Open

### Configuration
- **Failure Threshold**: 3 consecutive failures
- **Reset Timeout**: 60 seconds
- **Configurable per instance**

## Authentication Patterns

### API Key Authentication
```python
headers = {"X-API-KEY": api_key}
```

### JWT Bearer Token
```python
headers = {"Authorization": f"Bearer {token}"}
```

### Mixed Authentication (with fallback)
```python
try:
    token = create_service_token(...)
    headers = {"Authorization": f"Bearer {token}"}
except Exception:
    headers = {"X-API-KEY": api_key}  # Fallback
```

## Error Handling

### HttpClientHelper Exceptions
- `HttpClientError`: Base exception with status code and response
- Automatic retry on transient errors (no circuit breaker)

### DaprClientHelper Returns
- Pub/Sub: `bool` (success/failure)
- State Get: `Optional[Any]` (data or None)
- State Save: `bool` (success/failure)

## Best Practices

1. **Always use context managers**
   ```python
   async with get_service_client("service") as client:
       # Use client
   ```

2. **Handle None responses for state operations**
   ```python
   data = await client.get_state("store", "key")
   if data is None:
       # Key doesn't exist
   ```

3. **Log appropriately**
   - Success: DEBUG level
   - Warnings: Circuit breaker state changes
   - Errors: Failed operations with context

4. **Configure timeouts appropriately**
   - Default: 30 seconds
   - Adjust based on operation type

## Migration Guide

### From direct httpx to HttpClientHelper
```python
# Before
async with httpx.AsyncClient() as client:
    response = await client.get(url, headers=headers)
    
# After
async with get_service_client("service-name") as client:
    response = await client.get(endpoint, headers=headers)
```

### From aiohttp to DaprClientHelper
```python
# Before (Pub/Sub)
async with aiohttp.ClientSession() as session:
    await session.post(dapr_url, json=message)
    
# After
async with get_dapr_client() as client:
    await client.publish_event(pubsub_name, topic, message)
```

## Performance Considerations

1. **Connection Pooling**: Reuse connections where possible
2. **Circuit Breaker**: Prevents cascade failures (DaprClientHelper only)
3. **Retry Logic**: Handles transient failures automatically
4. **Async Operations**: All operations are non-blocking

## Monitoring

Monitor these metrics:
- Circuit breaker state changes
- Retry counts
- Response times
- Error rates by service

## Future Enhancements

1. Implement request tracing
2. Add metrics collection
3. Support for bulk operations
4. WebSocket support for real-time communication