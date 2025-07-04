# Stock Service WebSocket Specification

## Overview

The WebSocket functionality of Stock Service is a real-time communication system for notifying inventory level changes in real-time. It immediately delivers alerts to connected clients when items fall below reorder points or minimum inventory levels.

## WebSocket Endpoint

### Basic Information
- **Endpoint**: `/api/v1/ws/{tenant_id}/{store_code}`
- **Protocol**: WebSocket (ws://, wss://)
- **Authentication**: JWT token sent as query parameter

### Complete URL Example
```
ws://localhost:8006/api/v1/ws/tenant001/store001?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Authentication System

### JWT Token Authentication
Due to WebSocket protocol constraints, authentication uses query parameters:

```javascript
const token = 'your_jwt_token_here';
const wsUrl = `ws://localhost:8006/api/v1/ws/${tenantId}/${storeCode}?token=${token}`;
const websocket = new WebSocket(wsUrl);
```

### Authentication Errors
When authentication fails, the WebSocket connection is closed with the following codes:
- **Code**: 1008 (Policy Violation)
- **Reason**: "No token provided" or "Authentication failed"

## Message Formats

### 1. Connection Confirmation Message
Sent when WebSocket connection is established:

```json
{
  "type": "connection",
  "status": "connected",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### 2. Reorder Point Alert
Sent when inventory falls below reorder point:

```json
{
  "type": "stock_alert",
  "alert_type": "reorder_point",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM001",
  "current_quantity": 40.0,
  "reorder_point": 50.0,
  "reorder_quantity": 100.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### 3. Minimum Stock Alert
Sent when inventory falls below minimum stock level:

```json
{
  "type": "stock_alert",
  "alert_type": "minimum_stock",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM002",
  "current_quantity": 5.0,
  "minimum_quantity": 10.0,
  "reorder_quantity": 50.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

## Alert Control System

### Alert Cooldown
Cooldown functionality implemented to prevent duplicate alerts for the same item:

- **Configuration**: Environment variable `ALERT_COOLDOWN_SECONDS`
- **Default Value**: 60 seconds
- **Test Environment**: Can be set to 0 seconds
- **Scope**: Same item (tenant_id + store_code + item_code) for same alert type

### Alert Delivery Conditions
Alerts are delivered only when the following conditions are met:

1. **On Inventory Update**: Evaluated when inventory quantity changes
2. **Threshold Check**: 
   - Reorder Point Alert: `current_quantity <= reorder_point` and `reorder_point > 0`
   - Minimum Stock Alert: `current_quantity < minimum_quantity` and `minimum_quantity > 0`
3. **Cooldown Condition**: Configured time has passed since last alert

## Connection Management

### ConnectionManager
WebSocket connections are managed by the ConnectionManager class:

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, tenant_id: str, store_code: str)
    async def disconnect(self, websocket: WebSocket, tenant_id: str, store_code: str)
    async def send_to_store(self, tenant_id: str, store_code: str, message: str)
```

### Connection Lifecycle
1. **Connection Establishment**: Added to connection pool after JWT authentication
2. **Message Delivery**: Alert evaluation and delivery on inventory updates
3. **Connection Termination**: Automatically removed from connection pool

### Multiple Client Support
- Multiple WebSocket connections possible for the same tenant/store
- Alerts are delivered simultaneously to all connected clients
- Each connection is managed independently; disconnection of one doesn't affect others

## Implementation Examples

### JavaScript/TypeScript Client

#### Basic Connection
```javascript
class StockAlertClient {
    constructor(tenantId, storeCode, token) {
        this.tenantId = tenantId;
        this.storeCode = storeCode;
        this.token = token;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    connect() {
        const wsUrl = `ws://localhost:8006/api/v1/ws/${this.tenantId}/${this.storeCode}?token=${this.token}`;
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = (event) => {
            console.log('WebSocket connection established');
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.websocket.onclose = (event) => {
            if (event.code === 1008) {
                console.error('Authentication error:', event.reason);
                // Don't reconnect on authentication error
                return;
            }
            
            console.log('WebSocket connection closed');
            this.attemptReconnect();
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'connection':
                console.log('Connection confirmed:', data.status);
                break;
            case 'stock_alert':
                this.handleStockAlert(data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    handleStockAlert(alert) {
        const message = this.formatAlertMessage(alert);
        
        // Browser notification
        if (Notification.permission === 'granted') {
            new Notification('Stock Alert', {
                body: message,
                icon: '/icons/alert.png'
            });
        }
        
        // UI update
        this.updateUI(alert);
        
        // Log output
        console.log('Stock alert received:', alert);
    }

    formatAlertMessage(alert) {
        if (alert.alert_type === 'reorder_point') {
            return `${alert.item_code}: Below reorder point (current: ${alert.current_quantity})`;
        } else if (alert.alert_type === 'minimum_stock') {
            return `${alert.item_code}: Below minimum stock (current: ${alert.current_quantity})`;
        }
        return `${alert.item_code}: Stock alert`;
    }

    updateUI(alert) {
        // DOM manipulation to display alert
        const alertElement = document.createElement('div');
        alertElement.className = 'alert alert-warning';
        alertElement.textContent = this.formatAlertMessage(alert);
        
        const container = document.getElementById('alerts-container');
        if (container) {
            container.prepend(alertElement);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            
            console.log(`Attempting reconnect in ${delay}ms (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('Maximum reconnection attempts reached');
        }
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }
}

// Usage example
const client = new StockAlertClient('tenant001', 'store001', 'your_jwt_token');
client.connect();
```

#### React Hook
```javascript
import { useEffect, useState, useRef } from 'react';

export function useStockAlerts(tenantId, storeCode, token) {
    const [alerts, setAlerts] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const websocketRef = useRef(null);

    useEffect(() => {
        if (!tenantId || !storeCode || !token) return;

        const wsUrl = `ws://localhost:8006/api/v1/ws/${tenantId}/${storeCode}?token=${token}`;
        const websocket = new WebSocket(wsUrl);
        websocketRef.current = websocket;

        websocket.onopen = () => {
            setConnectionStatus('connected');
        };

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'stock_alert') {
                setAlerts(prev => [data, ...prev.slice(0, 99)]); // Keep latest 100 alerts
            }
        };

        websocket.onclose = (event) => {
            setConnectionStatus('disconnected');
            
            if (event.code === 1008) {
                console.error('Authentication error:', event.reason);
            }
        };

        websocket.onerror = () => {
            setConnectionStatus('error');
        };

        return () => {
            websocket.close();
        };
    }, [tenantId, storeCode, token]);

    const clearAlerts = () => {
        setAlerts([]);
    };

    return {
        alerts,
        connectionStatus,
        clearAlerts
    };
}

// Usage example
function StockDashboard() {
    const { alerts, connectionStatus } = useStockAlerts('tenant001', 'store001', userToken);

    return (
        <div>
            <div className={`connection-status ${connectionStatus}`}>
                Connection Status: {connectionStatus}
            </div>
            
            <div className="alerts-container">
                {alerts.map((alert, index) => (
                    <div key={index} className={`alert alert-${alert.alert_type}`}>
                        <strong>{alert.item_code}</strong>: Below {alert.alert_type === 'reorder_point' ? 'reorder point' : 'minimum stock'}
                        <br />
                        Current quantity: {alert.current_quantity}
                        <br />
                        <small>{new Date(alert.timestamp).toLocaleString()}</small>
                    </div>
                ))}
            </div>
        </div>
    );
}
```

### Python Client
```python
import asyncio
import json
import websockets
from typing import Callable, Optional

class StockAlertClient:
    def __init__(self, tenant_id: str, store_code: str, token: str, 
                 base_url: str = "ws://localhost:8006"):
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.token = token
        self.ws_url = f"{base_url}/api/v1/ws/{tenant_id}/{store_code}?token={token}"
        self.websocket = None
        self.alert_handlers = []

    def add_alert_handler(self, handler: Callable[[dict], None]):
        """Add alert handler"""
        self.alert_handlers.append(handler)

    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            print(f"WebSocket connection established: {self.tenant_id}/{self.store_code}")
            
            # Start message listening loop
            await self._listen_for_messages()
            
        except websockets.exceptions.ConnectionClosedError as e:
            if e.code == 1008:
                print(f"Authentication error: {e.reason}")
            else:
                print(f"Connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    async def _listen_for_messages(self):
        """Message receiving loop"""
        async for message in self.websocket:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except json.JSONDecodeError:
                print(f"Invalid JSON message: {message}")
            except Exception as e:
                print(f"Message processing error: {e}")

    async def _handle_message(self, data: dict):
        """Handle received messages"""
        if data.get("type") == "connection":
            print(f"Connection confirmed: {data.get('status')}")
        elif data.get("type") == "stock_alert":
            for handler in self.alert_handlers:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Alert handler error: {e}")

    async def disconnect(self):
        """Disconnect WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            print("WebSocket connection disconnected")

# Usage example
async def handle_stock_alert(alert_data):
    """Handle stock alerts"""
    alert_type = "reorder point" if alert_data["alert_type"] == "reorder_point" else "minimum stock"
    print(f"🚨 {alert_data['item_code']}: {alert_type} alert")
    print(f"   Current quantity: {alert_data['current_quantity']}")
    
    # Database recording, email sending, etc.
    # await save_alert_to_database(alert_data)
    # await send_email_notification(alert_data)

async def main():
    client = StockAlertClient(
        tenant_id="tenant001",
        store_code="store001", 
        token="your_jwt_token"
    )
    
    client.add_alert_handler(handle_stock_alert)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        print("Manually stopped")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling

### Connection Errors
| Error Code | Reason | Solution |
|------------|--------|----------|
| 1008 | Authentication failure | Check JWT token and reacquire |
| 1006 | Abnormal disconnection | Implement automatic reconnection |
| 1000 | Normal disconnection | Reconnect if needed |

### Reconnection Strategy
```javascript
class ReconnectManager {
    constructor(maxAttempts = 5, baseDelay = 1000) {
        this.maxAttempts = maxAttempts;
        this.baseDelay = baseDelay;
        this.attempts = 0;
    }

    async attempt(connectFunction) {
        while (this.attempts < this.maxAttempts) {
            try {
                await connectFunction();
                this.attempts = 0; // Reset on success
                return;
            } catch (error) {
                this.attempts++;
                
                if (this.attempts >= this.maxAttempts) {
                    throw new Error('Maximum reconnection attempts reached');
                }
                
                const delay = Math.min(
                    this.baseDelay * Math.pow(2, this.attempts), 
                    30000
                );
                
                console.log(`Attempting reconnect in ${delay}ms`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
}
```

## Performance Characteristics

### System Limits
- **Maximum Concurrent Connections**: Limited by system resources (no implementation limit)
- **Message Rate**: Sent only when alerts occur (low frequency)
- **Memory Usage**: Connections × ~1KB (connection management overhead)
- **CPU Usage**: Increases only during alert evaluation and message delivery

### Network Requirements
- **Bandwidth**: ~10-50 bytes/alert per connection (when JSON compressed)
- **Latency**: Usually < 100ms (from inventory update to alert delivery)
- **Heartbeat**: Uses WebSocket protocol ping

## Security Considerations

### Authentication & Authorization
- JWT token authentication (including expiration check)
- Tenant and store level access control
- Detection and logging of unauthorized access attempts

### Data Protection
- Encrypted transmission of sensitive inventory data
- Minimize alert content (send only necessary information)
- Avoid logging personal information

### DoS Attack Prevention
- Connection rate limiting (planned for future implementation)
- Alert spam prevention through cooldown functionality
- Resource monitoring and alerting

## Monitoring & Operations

### Metrics
- Number of active WebSocket connections
- Number of alerts delivered (by type and time)
- Connection error rate
- Average response time

### Logging
```json
{
  "timestamp": "2024-01-01T12:34:56.789Z",
  "level": "INFO",
  "event": "websocket_alert_sent",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM001",
  "alert_type": "reorder_point",
  "connection_count": 3
}
```

### Alerts
- Sudden increase in WebSocket connections
- Rising alert delivery failure rate
- Detection of abnormal disconnection patterns

## Integration with Alert Service

### AlertService Class
The AlertService manages alert logic and delivery:

```python
class AlertService:
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.alert_cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.recent_alerts: Dict[str, datetime] = {}

    async def check_and_send_alerts(self, stock: StockDocument):
        """Check stock levels and send alerts if necessary"""
        # Reorder point check
        if stock.reorder_point > 0 and stock.current_quantity <= stock.reorder_point:
            alert_key = f"reorder_{stock.tenant_id}_{stock.store_code}_{stock.item_code}"
            if self._should_send_alert(alert_key):
                await self.send_reorder_alert(stock)
        
        # Minimum stock check
        if stock.minimum_quantity > 0 and stock.current_quantity < stock.minimum_quantity:
            alert_key = f"minimum_{stock.tenant_id}_{stock.store_code}_{stock.item_code}"
            if self._should_send_alert(alert_key):
                await self.send_minimum_stock_alert(stock)
```

### Configuration
Alert behavior can be configured via environment variables:

```bash
# Alert cooldown in seconds (default: 60)
ALERT_COOLDOWN_SECONDS=60

# For testing (no cooldown)
ALERT_COOLDOWN_SECONDS=0
```

This specification enables effective understanding and implementation of the Stock Service WebSocket functionality.