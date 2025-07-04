# Account Service API Specification

## Overview

Account Service provides authentication and user management APIs in the Kugelpos POS system. It handles user registration, authentication, JWT token management, and tenant administration with secure, multi-tenant architecture.

## Base URL
- Local environment: `http://localhost:8000`
- Production environment: `https://account.{domain}`

## Authentication

Account Service provides authentication for other services and uses JWT tokens for session management:

### JWT Token Authentication
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: `/api/v1/accounts/token`
- Token contains user information and tenant context

## Field Format

All API requests and responses use **camelCase** field naming conventions. The service automatically converts between internal snake_case and external camelCase formats.

## Common Response Format

Most endpoints return responses in the following format:

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": { ... },
  "operation": "function_name"
}
```

Note: The `/token` endpoint returns the OAuth2 standard response format without the ApiResponse wrapper.

## API Endpoints

### 1. User Authentication (Login)
**POST** `/api/v1/accounts/token`

Authenticate user credentials and return JWT access token.

**Request Body (Form Data):**
- `username` (string, required): User's username
- `password` (string, required): User's password  
- `client_id` (string, required): Tenant ID for multi-tenant authentication

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=password123&client_id=A1234"
```

**Response Example:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Register Superuser (Create Tenant)
**POST** `/api/v1/accounts/register`

Register a new superuser and create a new tenant. This endpoint creates the initial admin user for a new tenant.

**Request Body:**
```json
{
  "username": "admin",
  "password": "securePassword123",
  "tenantId": "A1234"
}
```

**Field Descriptions:**
- `username` (string, required): Username for the superuser account
- `password` (string, required): Password for the superuser account
- `tenantId` (string, optional): Specific tenant ID. If not provided, one will be auto-generated

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "securePassword123",
    "tenantId": "A1234"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Superuser registered successfully",
  "data": {
    "username": "admin",
    "password": "*****",
    "tenantId": "A1234",
    "isSuperuser": true,
    "isActive": true,
    "createdAt": "2024-01-01T10:00:00Z",
    "updatedAt": null,
    "lastLogin": null
  },
  "operation": "register_superuser"
}
```

### 3. Register Regular User
**POST** `/api/v1/accounts/register/user`

Register a new regular user within an existing tenant. Requires superuser authentication.

**Authentication:** JWT token from superuser required

**Request Body:**
```json
{
  "username": "user001",
  "password": "userPassword123"
}
```

**Field Descriptions:**
- `username` (string, required): Username for the new user account
- `password` (string, required): Password for the new user account

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/register/user" \
  -H "Authorization: Bearer {superuser_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user001",
    "password": "userPassword123"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "User registered successfully",
  "data": {
    "username": "user001",
    "password": "*****",
    "tenantId": "A1234",
    "isSuperuser": false,
    "isActive": true,
    "createdAt": "2024-01-01T10:30:00Z",
    "updatedAt": null,
    "lastLogin": null
  },
  "operation": "register_user"
}
```

### 4. Service Health Check
**GET** `/health`

Check service health and database connectivity status.

**Request Example:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

### 5. API Root Information
**GET** `/`

Get basic API information and supported version details.

**Request Example:**
```bash
curl -X GET "http://localhost:8000/"
```

**Response Example:**
```json
{
  "message": "Welcome to Kugelpos Account Service API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

## Authentication Flow

### 1. New Tenant Registration Flow
```
1. POST /api/v1/accounts/register
   - Create superuser and tenant
   - Auto-generate tenant ID if not provided
   - Set up tenant database and collections
   
2. POST /api/v1/accounts/token
   - Authenticate with new credentials
   - Receive JWT token for API access
   
3. Use JWT token for authenticated operations
```

### 2. Regular User Registration Flow
```
1. Superuser authenticates: POST /api/v1/accounts/token
2. Create regular user: POST /api/v1/accounts/register/user
3. New user can authenticate: POST /api/v1/accounts/token
```

### 3. Daily Authentication Flow
```
1. POST /api/v1/accounts/token (with username, password, tenant_id)
2. Receive JWT token
3. Use token in Authorization header for other services
4. Token expires after configured duration
5. Re-authenticate when token expires
```

## JWT Token Details

### Token Structure
The JWT token contains the following claims:
- `sub`: Username
- `tenant_id`: Tenant identifier
- `is_superuser`: Admin privileges flag
- `is_active`: Account status
- `exp`: Token expiration timestamp
- `iat`: Token issued at timestamp

### Token Usage
```javascript
// Include in requests to other services
const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
};
```

### Token Validation
Other services validate tokens by:
1. Verifying JWT signature
2. Checking token expiration
3. Validating user existence and active status
4. Extracting tenant context for multi-tenant operations

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 401,
  "message": "Invalid credentials provided",
  "data": null,
  "operation": "login"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request (validation error)
- `401` - Authentication failed
- `403` - Access denied (authorization failed)
- `409` - Conflict (duplicate username/tenant)
- `500` - Internal server error

### Error Code System

Account Service uses error codes in the 10XXX range:

- `10001` - Authentication failure (invalid credentials)
- `10002` - User not found
- `10003` - Invalid token
- `10004` - Tenant creation error
- `10005` - User registration error (duplicate username)
- `10006` - Insufficient permissions (superuser required)
- `10007` - Inactive user account
- `10008` - Token expired
- `10099` - General service error

## Security Considerations

### Password Requirements
- Minimum length: 8 characters (configurable)
- BCrypt hashing with automatic salt generation
- Plain text passwords never stored in database
- Password complexity validation (planned for future)

### Token Security
- Configurable expiration time (default: 30 minutes)
- Secure signing algorithm (HS256)
- Token contains minimal user information
- Automatic token validation on each request

### Multi-tenant Security
- Complete database isolation between tenants
- Tenant ID validation on all operations
- Cross-tenant access prevention
- Unique tenant ID generation

## Rate Limiting

Currently, Account Service does not implement explicit rate limiting, but the following limits may be added:

- 10 login attempts per minute per IP address
- 100 requests per hour per user
- Brute force attack protection

## Configuration Options

### Environment Variables
```bash
# Database Configuration
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_account

# JWT Configuration  
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
TOKEN_EXPIRE_MINUTES=30

# Service Configuration
DEBUG=false
DEBUG_PORT=5678
```

### Database Collections
- `user_accounts`: User account information
- `request_log`: HTTP request audit logs

## Integration Examples

### Frontend Authentication
```javascript
// Login function
async function login(username, password, tenantId) {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);
  formData.append('client_id', tenantId);
  
  const response = await fetch('/api/v1/accounts/token', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  if (result.access_token) {
    localStorage.setItem('accessToken', result.access_token);
    return result.access_token;
  }
  throw new Error('Authentication failed');
}

// API request with token
async function apiRequest(url, options = {}) {
  const token = localStorage.getItem('accessToken');
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    ...options.headers
  };
  
  return fetch(url, { ...options, headers });
}
```

### Service-to-Service Authentication
```python
# Validate JWT token in other services
from jose import JWTError, jwt

def validate_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        is_active = payload.get("is_active", False)
        
        if not username or not tenant_id or not is_active:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        return {
            "username": username,
            "tenant_id": tenant_id,
            "is_superuser": payload.get("is_superuser", False)
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Testing

### Authentication Testing
```bash
# Test user registration
curl -X POST "http://localhost:8000/api/v1/accounts/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'

# Test authentication
curl -X POST "http://localhost:8000/api/v1/accounts/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123&client_id=A1234"

# Test health check
curl -X GET "http://localhost:8000/health"
```

## Notes

1. **OAuth2 Compliance**: Follows OAuth2 password flow standards
2. **Multi-tenant Architecture**: Each tenant has isolated data and users
3. **Security First**: BCrypt hashing, JWT tokens, and comprehensive validation
4. **CamelCase Convention**: All JSON fields use camelCase formatting
5. **Async Architecture**: Full async/await implementation for performance
6. **Production Ready**: Health monitoring, logging, and error handling
7. **Extensible Design**: Ready for future enhancements like MFA and SSO

The Account Service provides the foundational authentication layer for the entire Kugelpos POS system, ensuring secure and scalable user management across multiple tenants.