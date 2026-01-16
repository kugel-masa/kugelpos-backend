# Stock Service WebSocket Specification

## Overview

The Stock service's WebSocket functionality is a system that provides real-time notifications of stock level changes. It instantly delivers alerts to connected clients when products fall below reorder points or minimum stock levels.

## WebSocket Endpoint

### Connection Information

**Endpoint:** `WebSocket /ws/{tenant_id}/{store_code}`

**Implementation Location:** `/services/stock/app/api/v1/stock.py:996`

**Authentication:** JWT authentication (via query parameter)

**URL Example:**
```
ws://localhost:8006/ws/tenant001/STORE001?token={jwt_token}
```

## Authentication Mechanism

### JWT Authentication
**Implementation Location:** `/services/stock/app/api/v1/stock.py:1028`

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
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "message": "Connected to stock alert service"
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

**Implementation Location:** `/services/stock/app/websocket/connection_manager.py`

```python
class ConnectionManager:
    """Manager for WebSocket connections"""

    def __init__(self):
        # Structure: {tenant_id: {store_code: set(websocket_connections)}}
        self._connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
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

**Implementation Location:** `/services/stock/app/services/alert_service.py`

**Main Features:**

1. **Alert Evaluation Logic**
   ```python
   async def check_and_send_alerts(self, stock: StockDocument) -> None:
       """Check stock levels and send alerts if necessary"""
   ```

2. **Alert Types**
   - `reorder_point`: Stock quantity ≤ reorder point (only when reorder_point > 0)
   - `minimum_stock`: Stock quantity < minimum stock (only when minimum_quantity > 0)

3. **Cooldown Feature**
   - Default: 60 seconds
   - Environment variable: `ALERT_COOLDOWN_SECONDS`
   - Key format: `{alert_type}_{tenant_id}_{store_code}_{item_code}`

### Cooldown Implementation

Managed using an in-memory dictionary (`recent_alerts`) within AlertService.

```python
class AlertService:
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.alert_cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.recent_alerts: Dict[str, datetime] = {}  # Track recent alerts
        self._cleanup_task = None

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if we should send an alert based on cooldown"""
```

**Cleanup:**
- Background task (`_cleanup_old_alerts`) deletes old records every 10 minutes
- Implementation: `/services/stock/app/services/alert_service.py:38`

## Integration Points

### 1. Trigger on Stock Updates

**Implementation Location:** `/services/stock/app/services/stock_service.py:96`

```python
# Check for alerts if alert service is available
if self._alert_service:
    await self._alert_service.check_and_send_alerts(updated_stock)
```

### 2. On WebSocket Connection Establishment

**Implementation Location:** `/services/stock/app/api/v1/stock.py:1079`

When a WebSocket connection is established, current alert states are sent:
- Reorder point alerts for items below reorder point
- Minimum stock alerts for items below minimum quantity

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