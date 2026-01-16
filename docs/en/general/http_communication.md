# Kugelpos HTTP Communication Specification

## Overview

The Kugelpos system adopts unified HTTP communication patterns to achieve high reliability and performance. It provides robust inter-service communication through circuit breaker patterns and automatic retry mechanisms.

## Unified HTTP Communication Architecture

### HttpClientHelper

**Implementation Location:** `/services/commons/src/kugel_common/utils/http_client_helper.py`

**Main Features:**
- Automatic retry mechanism (3 attempts, exponential backoff)
- Connection pooling (max 100 connections, Keep-Alive 20 connections)
- Service discovery support
- Unified error handling

**Note:** Circuit breaker pattern is implemented in `DaprClientHelper`. `HttpClientHelper` provides auto-retry only.

**Configuration:**
```python
httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
)
```

### Usage Examples

```python
# Inter-service communication
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})

# Manual configuration
client = HttpClientHelper("master-data")
response = await client.get("/api/v1/products/123")
await client.close()
```

## Inter-Service Communication Patterns

### Authentication Mechanisms

#### 1. JWT Bearer Token Authentication
```python
headers = {"Authorization": f"Bearer {jwt_token}"}
```

#### 2. API Key Authentication
```python
headers = {"X-API-Key": terminal_api_key}
```

### Service Discovery

**Environment Variable Based:**
```python
MASTER_DATA_SERVICE_URL=http://master-data:8002
CART_SERVICE_URL=http://cart:8003
```

**Docker Compose Environment:**
- Automatic resolution by service name
- Communication over internal network

## Error Handling

### Unified Exception System

**HttpClientError:**
```python
class HttpClientError(Exception):
    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
```

### Retry Target Errors

- **5xx Server Errors**: All are retry targets
- **Timeouts**: Connection and read timeouts
- **Connection Errors**: Network failures

### Non-Retry Target Errors

- **4xx Client Errors**: Immediate failure
- **Authentication Errors**: 401, 403
- **Resource Not Found**: 404

## Circuit Breaker Implementation (DaprClientHelper)

**Note:** Circuit breaker is implemented only in `DaprClientHelper`. `HttpClientHelper` provides retry only.

### State Management

```python
class CircuitState(Enum):
    CLOSED = "closed"      # Normal state
    OPEN = "open"          # Blocked state
    HALF_OPEN = "half_open" # Recovery attempt state
```

### Operation Flow

1. **CLOSED → OPEN**: Block after 3 consecutive failures
2. **OPEN → HALF_OPEN**: Recovery attempt after 60 seconds
3. **HALF_OPEN → CLOSED**: Normal recovery on success
4. **HALF_OPEN → OPEN**: Block again on failure

## Performance Optimization

### Connection Pooling

- **Maximum Connections**: 100
- **Keep-Alive Connections**: 20
- **Connection Reuse**: Automatic management

### Timeout Settings

- **Connection Timeout**: 30 seconds
- **Read Timeout**: 30 seconds
- **Write Timeout**: 30 seconds

### Asynchronous Processing

- **asyncio Foundation**: All communication is asynchronous
- **Parallel Requests**: Simultaneous calls to multiple services
- **Non-blocking I/O**: High throughput

## Monitoring & Logging

### Metrics

- **Request Count**: By service and endpoint
- **Response Time**: Average and 95th percentile
- **Error Rate**: By 4xx/5xx
- **Circuit Breaker Status**: OPEN/CLOSED

### Log Output

```python
logger.info(f"HTTP {method} {url} - {status_code} ({duration}ms)")
logger.warning(f"Circuit breaker opened for {service_name}")
logger.error(f"HTTP request failed: {error}")
```

## Configuration Management

### Environment Variables

```bash
# Service URLs
MASTER_DATA_SERVICE_URL=http://master-data:8002
CART_SERVICE_URL=http://cart:8003

# Timeout settings
HTTP_TIMEOUT=30
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT=60
```

### Default Settings

```python
class HttpClientSettings:
    timeout: int = 30
    max_connections: int = 100
    max_keepalive: int = 20
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout: int = 60
    retry_attempts: int = 3
```

## Security Considerations

### HTTPS Communication

- **Production Environment**: Required
- **Development Environment**: HTTP allowed
- **Certificate Verification**: Enabled in production

### Header Security

```python
default_headers = {
    "User-Agent": "kugelpos-client/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
```

### Sensitive Information Protection

- **API Keys**: Transmitted in headers
- **JWT Tokens**: Bearer format
- **Log Masking**: Automatic masking of sensitive information

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Connection refused | Service down | Check service startup |
| Circuit breaker open | Consecutive failures | Wait for service normalization |
| Timeout | Response delay | Adjust timeout values |
| 401 Unauthorized | Authentication failure | Check token/API key |

### Debugging Methods

```python
# Log level setting
logging.getLogger("httpx").setLevel(logging.DEBUG)

# Request detail display
client = HttpClientHelper("service", debug=True)
```

## Future Enhancement Plans

### Load Balancing

- **Round Robin**: Support for multiple instances
- **Health Checks**: Exclude unhealthy instances

### Caching

- **Response Cache**: GET requests
- **ETags**: Conditional requests

### Compression

- **gzip**: Response compression
- **brotli**: High-efficiency compression

Through this unified HTTP communication architecture, Kugelpos achieves highly reliable and performant inter-service communication.