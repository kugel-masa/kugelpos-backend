# Frontend Developer Guide

This guide provides instructions and reference information for developing frontend applications using the Kugelpos POS backend API.

## Table of Contents
1. [System Overview](#system-overview)
2. [Environment Setup](#environment-setup)
3. [Authentication and Authorization](#authentication-and-authorization)
4. [API Endpoints](#api-endpoints)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Development Flow Example](#development-flow-example)
8. [Common Issues and Solutions](#common-issues-and-solutions)

## System Overview

The Kugelpos POS system is built on a microservices architecture. The main services and their roles are as follows:

- **Account Service (8000)**: User authentication and token management
- **Terminal Service (8001)**: Terminal, store, and tenant management
- **Master-data Service (8002)**: Master data management for products, payment methods, staff, etc.
- **Cart Service (8003)**: Shopping cart and transaction processing
- **Report Service (8004)**: Sales report generation and retrieval
- **Journal Service (8005)**: Electronic journal (transaction history) management
- **Stock Service (8006)**: Inventory management with real-time WebSocket alerts

Each service operates independently and communicates through REST APIs. Inter-service communication uses Dapr for pub/sub events and state management.

## Environment Setup

### Prerequisites
- Node.js 18 or higher
- npm or yarn
- Modern web browser (Chrome, Firefox, Edge, etc.)

### API Server Connection Settings

For frontend development, use the following base URLs to access the API:

**Local Development Environment:**
```
http://localhost:8000/ - Account Service
http://localhost:8001/ - Terminal Service
http://localhost:8002/ - Master-data Service
http://localhost:8003/ - Cart Service
http://localhost:8004/ - Report Service
http://localhost:8005/ - Journal Service
http://localhost:8006/ - Stock Service
ws://localhost:8006/ - Stock Service (WebSocket)
```

**Production/Test Environment:**
```
https://{environment-url}/api/v1/...
```

### CORS Notes

Backend services have CORS (Cross-Origin Resource Sharing) enabled and allow requests from all origins by default. Production environments may have appropriate origin restrictions configured.

## Authentication and Authorization

### Authentication Flow

1. **Login Process**:
```javascript
// Login example (using fetch API)
const response = await fetch('http://localhost:8000/api/v1/accounts/token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'your_password'
  })
});

const data = await response.json();
const token = data.access_token;
// Save token to local storage or secure cookie
localStorage.setItem('token', token);
```

2. **Authenticated Requests**:
```javascript
// Example request to API requiring authentication
const response = await fetch('http://localhost:8001/api/v1/terminals', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json'
  }
});
```

3. **Terminal Authentication (API Key)**:
```javascript
// Example request to API requiring terminal authentication
const response = await fetch('http://localhost:8003/api/v1/carts?terminal_id=TENANT-STORE-TERMINAL', {
  method: 'POST',
  headers: {
    'X-API-KEY': 'your_api_key',
    'Content-Type': 'application/json'
  }
});
```

4. **WebSocket Authentication (Stock Service)**:
```javascript
// WebSocket connection with JWT token authentication
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8006/ws/TENANT_ID/STORE_CODE?token=${token}`);

ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('Stock alert received:', alert);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

## API Endpoints

Below are the main endpoints for each service. Complete API specifications can be found at each service's `/docs` endpoint (Swagger UI).

### Account Service

- `POST /api/v1/accounts/token` - Login authentication and token retrieval
- `POST /api/v1/accounts/register` - Super user registration & new tenant creation
- `POST /api/v1/accounts/register/user` - General user registration by super user

### Terminal Service

- `POST /api/v1/tenants` - Tenant registration
- `POST /api/v1/tenants/{tenant_id}/stores` - Store registration
- `POST /api/v1/terminals` - Terminal registration
- `POST /api/v1/terminals/{terminal_id}/sign-in` - Terminal sign-in
- `POST /api/v1/terminals/{terminal_id}/open` - Terminal open
- `POST /api/v1/terminals/{terminal_id}/close` - Terminal close

### Master-data Service

- `POST /api/v1/tenants/{tenant_id}/staffs` - Staff registration
- `GET /api/v1/tenants/{tenant_id}/staffs` - Get staff list
- `POST /api/v1/tenants/{tenant_id}/items` - Product registration
- `GET /api/v1/tenants/{tenant_id}/items` - Get product list

### Cart Service

- `POST /api/v1/carts?terminal_id={terminal_id}` - Create cart
- `POST /api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}` - Add product
- `POST /api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}` - Calculate subtotal
- `POST /api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}` - Add payment
- `POST /api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}` - Complete billing

### Report Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/reports/daily?business_date={date}` - Get daily report

### Journal Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/journals` - Search journals

### Stock Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks` - Get stock list
- `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}` - Create/update stock
- `PUT /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}` - Adjust stock quantity
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}/snapshots` - Get stock snapshots
- `WS /ws/{tenant_id}/{store_code}` - WebSocket endpoint for real-time stock alerts

## Data Models

The main data models and their structures are as follows:

### Common Response Format

All API responses are returned in the following unified format:

```json
{
  "success": true|false,
  "code": 200|201|400|401|403|404|500,
  "message": "Processing description message",
  "userError": {
    "code": "Error code",
    "message": "User-facing error message"
  },
  "data": {
    // Actual data (varies by endpoint)
  },
  "metadata": {
    // Pagination information, etc.
  },
  "operation": "Name of the operation performed"
}
```

### Key Model Examples

**Tenant Information**:
```json
{
  "tenantId": "J5578",
  "tenantName": "Sample Company",
  "tags": ["Retail", "Apparel"],
  "stores": [
    {
      "storeCode": "0001",
      "storeName": "Ginza Store",
      "status": "Active",
      "businessDate": "20250506",
      "tags": ["Urban", "Flagship"],
      "entryDatetime": "2025-05-01 10:00:00",
      "lastUpdateDatetime": "2025-05-06 15:30:00"
    }
  ],
  "entryDatetime": "2025-05-01 10:00:00",
  "lastUpdateDatetime": "2025-05-06 15:30:00"
}
```

**Terminal Information**:
```json
{
  "terminalId": "J5578-0001-01",
  "tenantId": "J5578",
  "storeCode": "0001",
  "terminalNo": 1,
  "description": "Register 1",
  "functionMode": "MainMenu",
  "status": "Idle",
  "businessDate": "20250506",
  "openCounter": 2,
  "businessCounter": 15,
  "initialAmount": 50000.0,
  "physicalAmount": 123000.0,
  "staff": {
    "staffId": "S001",
    "staffName": "John Doe",
    "staffPin": "****"
  },
  "apiKey": "****",
  "entryDatetime": "2025-05-01 09:00:00",
  "lastUpdateDatetime": "2025-05-06 18:30:00"
}
```

**Cart Information**:
```json
{
  "cartId": "550e8400-e29b-41d4-a716-446655440000",
  "tenantId": "J5578",
  "storeCode": "0001",
  "terminalNo": 1,
  "status": "InProgress",
  "lineItems": [
    {
      "lineNo": 1,
      "itemCode": "ITEM001",
      "description": "T-Shirt White L",
      "unitPrice": 2000.0,
      "quantity": 2,
      "amount": 4000.0,
      "taxCode": "01",
      "discounts": []
    }
  ],
  "subtotal": {
    "totalAmount": 4000.0,
    "totalAmountWithTax": 4400.0,
    "taxAmount": 400.0,
    "totalQuantity": 2
  },
  "payments": [],
  "taxes": [
    {
      "taxNo": 1,
      "taxCode": "01",
      "taxName": "10% Tax",
      "taxAmount": 400.0,
      "targetAmount": 4000.0,
      "targetQuantity": 2
    }
  ]
}
```

## Error Handling

### Error Response Format

When an error occurs, error information is returned in the common response format. `success: false` is set and error details are included.

```json
{
  "success": false,
  "code": 400,
  "message": "Invalid input data: tenant_id -> field required",
  "userError": {
    "code": "400001",
    "message": "Invalid input data"
  },
  "data": null,
  "metadata": null,
  "operation": "validation_exception_handler"
}
```

### Main Error Codes

- `400xxx`: Input data error
- `401xxx`: Authentication error
- `403xxx`: Authorization error
- `404xxx`: Resource not found
- `405xxx`: Method not allowed
- `406xxx`: Processing not acceptable
- `500xxx`: Internal server error

### Frontend Error Handling Example

```javascript
async function fetchData(url) {
  try {
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    });
    
    const result = await response.json();
    
    if (!result.success) {
      // Display error message
      showError(result.userError?.message || result.message);
      return null;
    }
    
    return result.data;
  } catch (error) {
    console.error('API communication error:', error);
    showError('Failed to communicate with server.');
    return null;
  }
}
```

## Development Flow Example

Below is a typical POS application development flow:

1. **Initial Setup and Authentication**
   - Implement user login screen
   - Token acquisition and storage

2. **Master Data Configuration**
   - Register tenant, store, terminal (for administrators)
   - Register products, staff, payment methods (for administrators)

3. **Store Terminal Functions**
   - Terminal sign-in and open process
   - Cart creation and product registration
   - Payment processing and transaction completion
   - Journal search and return processing
   - Close process and report output

### Basic Flow Implementation Examples

**Step 1: Terminal Sign-in and Open**
```javascript
// 1. Terminal sign-in
async function signInTerminal(terminalId, staffId, staffPin) {
  const response = await fetch(`http://localhost:8001/api/v1/terminals/${terminalId}/sign-in`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ staff_id: staffId, pin: staffPin })
  });
  return await response.json();
}

// 2. Terminal open
async function openTerminal(terminalId, initialAmount) {
  const response = await fetch(`http://localhost:8001/api/v1/terminals/${terminalId}/open`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ initial_amount: initialAmount })
  });
  return await response.json();
}
```

**Step 2: Transaction Processing**
```javascript
// 1. Create cart
async function createCart(terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  const result = await response.json();
  return result.data.cartId;
}

// 2. Add item
async function addItemToCart(cartId, terminalId, itemCode, quantity) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/lineItems?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      item_code: itemCode,
      quantity: quantity
    })
  });
  return await response.json();
}

// 3. Calculate subtotal
async function calculateSubtotal(cartId, terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/subtotal?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
}

// 4. Add payment
async function addPayment(cartId, terminalId, paymentCode, amount) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/payments?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      payment_code: paymentCode,
      amount: amount
    })
  });
  return await response.json();
}

// 5. Complete billing
async function finalizeBill(cartId, terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/bill?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
}
```

## Real-time Features (WebSocket)

The Stock service provides real-time inventory alerts through WebSocket connections. This enables frontend applications to receive immediate notifications about stock levels and reorder points.

### WebSocket Connection Setup

```javascript
class StockAlertManager {
  constructor(tenantId, storeCode) {
    this.tenantId = tenantId;
    this.storeCode = storeCode;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second
  }

  connect() {
    const token = localStorage.getItem('token');
    const wsUrl = `ws://localhost:8006/ws/${this.tenantId}/${this.storeCode}?token=${token}`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('Connected to stock alerts');
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };
    
    this.ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      this.handleStockAlert(alert);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket connection closed');
      this.attemptReconnect();
    };
  }
  
  handleStockAlert(alert) {
    // Alert types: 'low_stock', 'reorder_point', 'out_of_stock'
    switch(alert.type) {
      case 'low_stock':
        console.warn(`Low stock alert: ${alert.itemCode} - ${alert.currentQuantity} remaining`);
        break;
      case 'reorder_point':
        console.warn(`Reorder point reached: ${alert.itemCode} - ${alert.currentQuantity} remaining`);
        break;
      case 'out_of_stock':
        console.error(`Out of stock: ${alert.itemCode}`);
        break;
    }
    
    // Update UI with alert information
    this.displayAlert(alert);
  }
  
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
      
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay);
      
      // Exponential backoff
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const stockAlerts = new StockAlertManager('J5578', '0001');
stockAlerts.connect();
```

### Stock Alert Message Format

```json
{
  "type": "low_stock",  // 'low_stock', 'reorder_point', 'out_of_stock'
  "itemCode": "ITEM001",
  "itemName": "T-Shirt White L",
  "currentQuantity": 5,
  "minimumQuantity": 10,
  "reorderPoint": 20,
  "timestamp": "2025-01-26T10:30:00Z",
  "message": "Stock level is below minimum quantity"
}
```

### Best Practices for WebSocket Handling

1. **Authentication**: Always include JWT token in the connection URL
2. **Reconnection Logic**: Implement exponential backoff for reconnection attempts
3. **Error Handling**: Gracefully handle connection failures and display offline status
4. **Message Validation**: Validate incoming messages before processing
5. **Resource Cleanup**: Close connections when components unmount or user navigates away

## Common Issues and Solutions

### 1. Authentication Errors
**Problem**: `401 Unauthorized` error occurs
**Solution**: 
- Check if token has expired
- Verify correct API key is being used
- Try logging in again

### 2. CORS Errors
**Problem**: CORS error displayed in browser console
**Solution**:
- Verify backend CORS settings are correct
- Consider using browser plugin to temporarily disable CORS restrictions during development

### 3. Data Consistency Errors
**Problem**: `406 Not Acceptable` error occurs during transaction processing
**Solution**:
- Check error message and fix data consistency issues (insufficient payment amount, etc.)
- Check debug logs to identify the problem

### 4. Performance Optimization
**Problem**: Slow response when retrieving large amounts of data
**Solution**:
- Set pagination parameters (limit, page) appropriately
- Optimize queries to retrieve only necessary data

### 5. Connection Errors
**Problem**: Cannot connect to API server
**Solution**:
- Verify backend services are running
- Check network settings and firewall
- Confirm correct URL and port are being used

### 6. WebSocket Connection Issues
**Problem**: WebSocket fails to connect or frequently disconnects
**Solution**:
- Verify JWT token is valid and not expired
- Check network stability and firewall settings
- Implement proper reconnection logic with exponential backoff
- Monitor WebSocket connection state and display connection status to users

## Health Check Endpoints

All services provide health check endpoints for monitoring service availability:

```javascript
// Check service health
async function checkServiceHealth(serviceUrl) {
  try {
    const response = await fetch(`${serviceUrl}/health`);
    const health = await response.json();
    return health.status === 'healthy';
  } catch (error) {
    return false;
  }
}

// Monitor all services
async function monitorServices() {
  const services = [
    { name: 'Account', url: 'http://localhost:8000' },
    { name: 'Terminal', url: 'http://localhost:8001' },
    { name: 'Master-data', url: 'http://localhost:8002' },
    { name: 'Cart', url: 'http://localhost:8003' },
    { name: 'Report', url: 'http://localhost:8004' },
    { name: 'Journal', url: 'http://localhost:8005' },
    { name: 'Stock', url: 'http://localhost:8006' }
  ];
  
  for (const service of services) {
    const isHealthy = await checkServiceHealth(service.url);
    console.log(`${service.name}: ${isHealthy ? 'Healthy' : 'Unhealthy'}`);
  }
}
```

## Support and Resources

- **API Documentation**: Swagger UI available at each service's `/docs` endpoint
- **Health Monitoring**: Health check available at each service's `/health` endpoint
- **Sample Code**: Sample implementations available in the `examples` directory
- **Issue Reporting**: Create tickets in the issue management system for bugs and problems