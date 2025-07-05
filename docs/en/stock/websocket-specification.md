# Stock Service WebSocket Specification

## Overview

The Stock service's WebSocket functionality is a system that provides real-time notifications of stock level changes. It instantly delivers alerts to connected clients when products fall below reorder points or minimum stock levels.

## WebSocket Endpoint

### Connection Information

**Endpoint:** `WebSocket /api/v1/ws/{tenant_id}/{store_code}`

**Implementation Location:** `/services/stock/app/routers/websocket_router.py:21`

**Authentication:** JWT authentication (via query parameter)

**URL Example:**
```
ws://localhost:8006/api/v1/ws/tenant001/STORE001?token={jwt_token}
```

## Authentication Mechanism

### JWT Authentication
**Implementation Location:** `/services/stock/app/routers/websocket_router.py:29`

Due to WebSocket protocol constraints, the authentication token is sent as a query parameter:

```python
async def verify_jwt_from_query(token: str) -> Optional[User]:
    """Verify JWT token from query parameter"""
```

**Authentication Errors:**
- Code: 1008 (Policy Violation)
- Reasons: "No token provided", "Authentication failed", "Tenant ID mismatch"

## Message Formats

### 1. Connection Confirmation Message

Sent when connection is established:

```json
{
  "type": "connection",
  "status": "connected",
  "message": "WebSocket connected successfully"
}
```

### 2. Stock Alerts

#### Reorder Point Alert
```json
{
  "type": "stock_alert",
  "alert_type": "reorder_point",
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "item_code": "ITEM001",
  "current_quantity": 15.0,
  "reorder_point": 20.0,
  "reorder_quantity": 50.0,
  "timestamp": "2025-01-05T12:00:00Z"
}
```

#### Minimum Stock Alert
```json
{
  "type": "stock_alert",
  "alert_type": "minimum_stock",
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "item_code": "ITEM002",
  "current_quantity": 8.0,
  "minimum_quantity": 10.0,
  "reorder_quantity": 30.0,
  "timestamp": "2025-01-05T12:00:00Z"
}
```

### 3. Ping/Pong Messages

Heartbeat for connection maintenance:
- Client sends: `"ping"`
- Server responds: `"pong"`

## Connection Management

### ConnectionManager

**Implementation Location:** `/services/stock/app/services/websocket/connection_manager.py`

```python
class ConnectionManager:
    """Manager for WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        self._lock = asyncio.Lock()
```

**Main Methods:**
- `connect()`: Register new connection
- `disconnect()`: Remove connection
- `send_to_store()`: Send to all connections in specific store
- `broadcast_to_tenant()`: Send to all stores in tenant
- `get_connection_count()`: Get connection count

**Hierarchical Structure:**
```
{tenant_id: {store_code: set(websockets)}}
```

## Alert Service

### AlertService

**Implementation Location:** `/services/stock/app/services/websocket/alert_service.py`

**Main Features:**

1. **Alert Evaluation Logic**
   ```python
   async def check_and_send_alerts(
       self,
       tenant_id: str,
       store_code: str,
       item: StockItemDocument
   )
   ```

2. **Alert Types**
   - `reorder_point`: Stock quantity ≤ reorder point
   - `minimum_stock`: Stock quantity < minimum stock

3. **Cooldown Feature**
   - Default: 60 seconds
   - Environment variable: `ALERT_COOLDOWN_SECONDS`
   - Key format: `{alert_type}_{tenant_id}_{store_code}_{item_code}`

### Cooldown Implementation

**Implementation Location:** `/services/stock/app/repositories/alert_cooldown_repository.py`

```python
class AlertCooldownRepository:
    """Repository for managing alert cooldowns"""
    
    async def is_in_cooldown(
        self,
        alert_type: str,
        tenant_id: str,
        store_code: str,
        item_code: str
    ) -> bool
```

**Cleanup:**
- Background task deletes old records every 10 minutes
- Implementation: `/services/stock/app/services/websocket/alert_service.py:60`

## Integration Points

### 1. Trigger on Stock Updates

**Implementation Location:** `/services/stock/app/services/stock_service.py:239`

```python
# Alert check after stock update
await self.alert_service.check_and_send_alerts(
    tenant_id=tenant_id,
    store_code=store_code,
    item=updated_item
)
```

### 2. During Transaction Processing

**Implementation Location:** `/services/stock/app/services/transaction_handler.py:100`

Alert check after transaction log processing when stock changes occur

## Performance Characteristics

1. **Connection Management**
   - Efficient connection management through hierarchical data structure
   - Concurrent execution control via asynchronous locks

2. **Message Delivery**
   - Bulk sending per store
   - Parallel delivery through asynchronous processing

3. **Cooldown**
   - Fast evaluation via in-memory cache
   - Prevents bloating through periodic cleanup

## Security

1. **Authentication**
   - JWT verification required
   - Tenant ID matching confirmation

2. **Data Isolation**
   - Strict isolation at tenant and store levels
   - No access to other tenants' data

3. **Connection Limits**
   - Immediate disconnection on authentication failure
   - Ignores invalid messages

## Error Handling

### WebSocket Connection Errors

| Code | Description | Action |
|------|-------------|--------|
| 1008 | Policy violation (authentication failure) | Re-acquire token |
| 1006 | Abnormal disconnection | Reconnection recommended |
| 1000 | Normal closure | Reconnect if needed |

### Message Send Errors

On send failure, individual connections are closed and removed from connection pool

## Limitations

1. **Scalability**
   - Connection management within single server instance
   - External message broker required for horizontal scaling

2. **Message Guarantees**
   - At-most-once delivery (no retries)
   - Possible message loss during disconnection

3. **Resource Limits**
   - Connection count depends on system resources
   - Memory usage consideration for high connection volumes