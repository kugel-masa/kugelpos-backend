# Terminal Service API Specification

## Overview

Terminal Service manages POS terminals, stores, and cash operations in the Kugelpos POS system. It provides endpoints for terminal lifecycle management, staff authentication, business session control, and multi-tenant store administration with comprehensive audit trails.

## Base URL
- Local environment: `http://localhost:8001`
- Production environment: `https://terminal.{domain}`

## Authentication

Terminal Service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: Account Service's `/api/v1/accounts/token`
- Required for administrative operations and tenant management

### 2. API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- Used for POS terminal operations

## Field Format

All API requests and responses use **camelCase** field naming conventions. The service uses `BaseSchemaModel` and transformers to automatically convert between internal snake_case and external camelCase formats.

## Common Response Format

All endpoints return responses in the following format:

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": { ... },
  "operation": "function_name"
}
```

## Enumerations

### Terminal Status
- `Idle` - Terminal is not opened for business
- `Opened` - Terminal is active and ready for operations
- `Closed` - Terminal has been closed for the day

### Function Modes
- `MainMenu` - Default display mode
- `OpenTerminal` - Terminal opening operations
- `Sales` - Sales transaction processing
- `Returns` - Return transaction processing
- `Void` - Transaction voiding
- `Reports` - Report generation
- `CloseTerminal` - Terminal closing operations
- `Journal` - Transaction history viewing
- `Maintenance` - System maintenance
- `CashInOut` - Cash drawer operations

## API Endpoints

### 1. Create Terminal
**POST** `/api/v1/terminals`

Create a new POS terminal device with store association.

**Request Body:**
```json
{
  "storeCode": "store001",
  "terminalNo": 1,
  "description": "Front Counter Terminal"
}
```

**Field Descriptions:**
- `storeCode` (string, required): Store code where the terminal will be created
- `terminalNo` (integer, required): Terminal number unique within the store (1-999)
- `description` (string, required): Terminal description

**Note:** The tenant ID is extracted from the JWT authentication token, not from the request body.

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "storeCode": "store001",
    "terminalNo": 1,
    "description": "Front Counter Terminal"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Terminal created successfully",
  "data": {
    "terminalId": "tenant001-store001-001",
    "tenantId": "tenant001",
    "storeCode": "store001",
    "terminalNo": 1,
    "description": "Front Counter Terminal",
    "status": "Idle",
    "functionMode": "MainMenu",
    "apiKey": "term_k3y_a1b2c3d4e5f6...",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_terminal"
}
```

### 2. Get Terminal List
**GET** `/api/v1/terminals`

Retrieve list of terminals with pagination and filtering.

**Query Parameters:**
- `tenant_id` (string, optional): Filter by tenant ID
- `store_code` (string, optional): Filter by store code
- `terminal_id` (string, optional): Terminal ID for API key authentication
- `skip` (integer, default: 0): Number of items to skip
- `limit` (integer, default: 10, max: 100): Maximum number of items to return

**Request Example:**
```bash
curl -X GET "http://localhost:8001/api/v1/terminals?tenant_id=tenant001&store_code=store001&skip=0&limit=20" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminals retrieved successfully",
  "data": {
    "items": [
      {
        "terminalId": "tenant001-store001-001",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "terminalNo": 1,
        "description": "Front Counter Terminal",
        "status": "Opened",
        "functionMode": "Sales",
        "businessDate": "2024-01-01",
        "staff": {
          "staffId": "STF001",
          "name": "John Doe"
        },
        "openCounter": 1,
        "businessCounter": 100
      }
    ],
    "total": 5,
    "skip": 0,
    "limit": 20
  },
  "operation": "get_terminals"
}
```

### 3. Get Terminal Details
**GET** `/api/v1/terminals/{terminal_id}`

Retrieve detailed information for a specific terminal.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier (format: tenant_id-store_code-terminal_no)

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8001/api/v1/terminals/tenant001-store001-001" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminal retrieved successfully",
  "data": {
    "terminalId": "tenant001-store001-001",
    "tenantId": "tenant001",
    "storeCode": "store001",
    "terminalNo": 1,
    "description": "Front Counter Terminal",
    "status": "Opened",
    "functionMode": "Sales",
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "businessCounter": 100,
    "staff": {
      "staffId": "STF001",
      "name": "John Doe",
      "signInTime": "2024-01-01T09:00:00Z"
    },
    "initialAmount": 500.00,
    "physicalAmount": null,
    "tags": ["POS", "Front"]
  },
  "operation": "get_terminal"
}
```

### 4. Delete Terminal
**DELETE** `/api/v1/terminals/{terminal_id}`

Delete a terminal (must be in Idle status).

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Example:**
```bash
curl -X DELETE "http://localhost:8001/api/v1/terminals/tenant001-store001-001" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminal deleted successfully",
  "data": null,
  "operation": "delete_terminal"
}
```

### 5. Update Terminal Description
**PATCH** `/api/v1/terminals/{terminal_id}/description`

Update the terminal's description.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "description": "Main Checkout Terminal"
}
```

**Request Example:**
```bash
curl -X PATCH "http://localhost:8001/api/v1/terminals/tenant001-store001-001/description" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"description": "Main Checkout Terminal"}'
```

### 6. Update Function Mode
**PATCH** `/api/v1/terminals/{terminal_id}/function_mode`

Update the terminal's operational mode.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "functionMode": "Sales"
}
```

**Field Descriptions:**
- `functionMode` (string, required): One of the valid function modes

**Request Example:**
```bash
curl -X PATCH "http://localhost:8001/api/v1/terminals/tenant001-store001-001/function_mode" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"functionMode": "Sales"}'
```

### 7. Staff Sign-in
**POST** `/api/v1/terminals/{terminal_id}/sign-in`

Sign in a staff member to the terminal.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "staffCode": "STF001",
  "pin": "1234"
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals/tenant001-store001-001/sign-in" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "staffCode": "STF001",
    "pin": "1234"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Staff signed in successfully",
  "data": {
    "staff": {
      "staffId": "STF001",
      "name": "John Doe",
      "signInTime": "2024-01-01T09:00:00Z"
    }
  },
  "operation": "sign_in"
}
```

### 8. Staff Sign-out
**POST** `/api/v1/terminals/{terminal_id}/sign-out`

Sign out the currently signed-in staff member.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals/tenant001-store001-001/sign-out" \
  -H "X-API-Key: {api_key}"
```

### 9. Open Terminal
**POST** `/api/v1/terminals/{terminal_id}/open`

Open the terminal for business operations.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "businessDate": "2024-01-01",
  "initialAmount": 500.00
}
```

**Field Descriptions:**
- `businessDate` (string, required): Business date in YYYY-MM-DD format
- `initialAmount` (number, optional): Opening cash drawer amount

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals/tenant001-store001-001/open" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "businessDate": "2024-01-01",
    "initialAmount": 500.00
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminal opened successfully",
  "data": {
    "terminalId": "tenant001-store001-001",
    "status": "Opened",
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "businessCounter": 100,
    "initialAmount": 500.00,
    "receiptText": "=== TERMINAL OPEN ===\n...",
    "journalText": "Terminal Open\n..."
  },
  "operation": "open_terminal"
}
```

### 10. Close Terminal
**POST** `/api/v1/terminals/{terminal_id}/close`

Close the terminal and end the business session.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "physicalAmount": 1250.00
}
```

**Field Descriptions:**
- `physicalAmount` (number, optional): Physical cash count at closing

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals/tenant001-store001-001/close" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"physicalAmount": 1250.00}'
```

### 11. Cash In Operation
**POST** `/api/v1/terminals/{terminal_id}/cash-in`

Record cash added to the drawer.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "amount": 100.00,
  "reason": "Float Addition",
  "note": "Additional change required"
}
```

**Field Descriptions:**
- `amount` (number, required): Amount to add (must be positive)
- `reason` (string, optional): Reason for cash in
- `note` (string, optional): Additional notes

**Request Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals/tenant001-store001-001/cash-in" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "reason": "Float Addition"
  }'
```

### 12. Cash Out Operation
**POST** `/api/v1/terminals/{terminal_id}/cash-out`

Record cash removed from the drawer.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "amount": 50.00,
  "reason": "Bank Deposit",
  "note": "Daily deposit"
}
```

**Field Descriptions:**
- `amount` (number, required): Amount to remove (must be positive)
- `reason` (string, optional): Reason for cash out
- `note` (string, optional): Additional notes

### 13. Update Delivery Status
**POST** `/api/v1/terminals/{terminal_id}/delivery-status`

Update the delivery status of published events.

**Path Parameters:**
- `terminal_id` (string, required): Terminal identifier

**Request Body:**
```json
{
  "eventId": "evt_123456",
  "delivered": true
}
```

## Tenant Management Endpoints

### 14. Create Tenant
**POST** `/api/v1/tenants`

Create a new tenant with initial setup.

**Request Body:**
```json
{
  "tenantId": "tenant001",
  "tenantName": "Example Retail Store",
  "tenantNameLocal": "サンプル小売店"
}
```

**Authentication:** Requires JWT token

### 15. Get Tenant Details
**GET** `/api/v1/tenants/{tenant_id}`

Retrieve tenant information and store list.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

### 16. Update Tenant
**PUT** `/api/v1/tenants/{tenant_id}`

Update tenant information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "tenantName": "Updated Store Name",
  "tenantNameLocal": "更新された店舗名"
}
```

### 17. Delete Tenant
**DELETE** `/api/v1/tenants/{tenant_id}`

Delete a tenant (requires no active terminals).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

## Store Management Endpoints

### 18. Add Store
**POST** `/api/v1/tenants/{tenant_id}/stores`

Add a new store to a tenant.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "storeCode": "store001",
  "storeName": "Downtown Branch",
  "storeNameLocal": "ダウンタウン支店",
  "address": "123 Main St",
  "phone": "555-0123"
}
```

### 19. Get Store List
**GET** `/api/v1/tenants/{tenant_id}/stores`

Retrieve all stores for a tenant.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

### 20. Get Store Details
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Retrieve specific store information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

### 21. Update Store
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Update store information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

### 22. Delete Store
**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Delete a store (requires no active terminals).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

## System Endpoints

### 23. Health Check
**GET** `/health`

Check service health and dependencies.

**Request Example:**
```bash
curl -X GET "http://localhost:8001/health"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "mongodb": "connected",
    "dapr_sidecar": "connected",
    "pubsub_topics": "available",
    "background_jobs": "running"
  },
  "operation": "health_check"
}
```

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 404,
  "message": "Terminal not found: tenant001-store001-001",
  "data": null,
  "operation": "get_terminal"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request
- `401` - Authentication error
- `403` - Access denied
- `404` - Resource not found
- `409` - Conflict (e.g., terminal already exists)
- `500` - Internal server error

### Error Code System

Terminal Service uses error codes in the 20XXX range:

- `20001` - Terminal not found
- `20002` - Terminal already exists
- `20003` - Invalid terminal status for operation
- `20004` - Staff authentication failed
- `20005` - Cash operation error
- `20006` - Tenant operation error
- `20007` - Store operation error
- `20008` - Invalid function mode
- `20099` - General terminal service error

## Event Publishing

The terminal service publishes events to the following Dapr pub/sub topics:

### Cash Operation Events
- **Topic**: `topic-cashlog`
- **Events**: Cash in/out operations

### Terminal Session Events
- **Topic**: `topic-opencloselog`
- **Events**: Terminal open/close operations

## Receipt and Journal Text

Cash operations and terminal open/close operations generate:
- **Receipt Text**: Formatted text for customer receipts
- **Journal Text**: Detailed internal audit trail text

## Business Rules

1. **Terminal Status Transitions**:
   - Idle → Opened (via open operation)
   - Opened → Closed (via close operation)
   - Closed → Idle (automatic)

2. **Operation Restrictions**:
   - Staff must be signed in for most operations
   - Terminal must be opened for cash operations
   - Cannot delete terminal unless in Idle status
   - Cannot open terminal if already opened

3. **Multi-tenancy**:
   - All operations are tenant-scoped
   - API keys are terminal-specific
   - Cross-tenant operations are prohibited

## Notes

1. **Terminal ID Format**: Always `{tenant_id}-{store_code}-{terminal_no}`
2. **Terminal Number**: Padded to 3 digits (e.g., 001, 002, 999)
3. **CamelCase Convention**: All JSON fields use camelCase
4. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
5. **API Key**: Generated automatically when terminal is created
6. **Authentication**: Use JWT for management, API key for terminal operations
7. **Idempotency**: Terminal creation is idempotent based on terminal ID