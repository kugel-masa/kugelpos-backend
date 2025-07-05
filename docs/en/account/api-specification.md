# Account Service API Specification

## Overview

The Account service is a microservice that provides user authentication and JWT token management. It supports multi-tenancy, enabling independent user management for each tenant.

## Service Information

- **Port**: 8000
- **Framework**: FastAPI
- **Authentication**: JWT (OAuth2PasswordBearer)
- **Database**: MongoDB (Motor async driver)
- **Password Encryption**: bcrypt

## API Endpoints

### 1. Root Endpoint

**Path**: `/`  
**Method**: GET  
**Authentication**: Not required  
**Description**: Service health check endpoint

**Response**:
```json
{
  "message": "Welcome to Kugel-POS Auth API. supoorted version: v1"
}
```

**Implementation File**: app/main.py:75-82

### 2. Health Check

**Path**: `/health`  
**Method**: GET  
**Authentication**: Not required  
**Description**: Endpoint to check service health

**Response Model**: `HealthCheckResponse`
```json
{
  "status": "healthy",
  "service": "account",
  "version": "1.0.0",
  "checks": {
    "mongodb": {
      "status": "healthy",
      "details": {}
    }
  }
}
```

**Implementation File**: app/main.py:84-112

### 3. Token Generation

**Path**: `/api/v1/accounts/token`  
**Method**: POST  
**Authentication**: Not required  
**Description**: Authenticate user and issue JWT access token

**Request**: `OAuth2PasswordRequestForm`
- `username`: string (required) - Username
- `password`: string (required) - Password
- `client_id`: string (required) - Used as tenant ID

**Response Model**: `LoginResponse`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses**:
- 400: Bad Request
- 401: Unauthorized - Invalid credentials
- 422: Unprocessable Entity
- 500: Internal Server Error

**Implementation Details** (app/api/v1/account.py:46-101):
- Authenticates using username, password, and tenant ID
- Updates last login time on successful authentication
- JWT token includes username, tenant_id, and is_superuser
- Token expiration is set via `TOKEN_EXPIRE_MINUTES` environment variable

### 4. Super User Registration (Tenant Creation)

**Path**: `/api/v1/accounts/register`  
**Method**: POST  
**Authentication**: Not required  
**Description**: Create new tenant and super user

**Request Model**: `UserAccount`
```json
{
  "username": "admin",
  "password": "secure_password123",
  "tenantId": "A1234"  // Optional - auto-generated if not specified
}
```

**Response Model**: `ApiResponse[UserAccountInDB]`
```json
{
  "success": true,
  "code": 201,
  "message": "User registration successful",
  "data": {
    "username": "admin",
    "password": "*****",
    "hashedPassword": "$2b$12$...",
    "tenantId": "A1234",
    "isSuperuser": true,
    "isActive": true,
    "createdAt": "2025-01-05T10:30:00",
    "updatedAt": null,
    "lastLogin": null
  },
  "operation": "register_super_user"
}
```

**Error Responses**:
- 400: Bad Request
- 401: Unauthorized
- 422: Unprocessable Entity
- 500: Internal Server Error

**Implementation Details** (app/api/v1/account.py:105-166):
- Tenant ID can be auto-generated or specified (format: 1 uppercase letter + 4 digits)
- Creates database for new tenant
- Created user automatically has super user privileges
- Sends Slack notification (if configured)

### 5. Regular User Registration

**Path**: `/api/v1/accounts/register/user`  
**Method**: POST  
**Authentication**: Required (Super users only)  
**Description**: Create regular user within the same tenant

**Request Headers**:
```
Authorization: Bearer <JWT_TOKEN>
```

**Request Model**: `UserAccount`
```json
{
  "username": "user01",
  "password": "user_password123"
}
```

**Response Model**: `ApiResponse[UserAccountInDB]`
```json
{
  "success": true,
  "code": 201,
  "message": "User registration successful",
  "data": {
    "username": "user01",
    "password": "*****",
    "hashedPassword": "$2b$12$...",
    "tenantId": "A1234",
    "isSuperuser": false,
    "isActive": true,
    "createdAt": "2025-01-05T11:00:00",
    "updatedAt": null,
    "lastLogin": null
  },
  "operation": "register_user_by_superuser"
}
```

**Error Responses**:
- 400: Bad Request
- 401: Unauthorized - No super user privileges
- 422: Unprocessable Entity
- 500: Internal Server Error

**Implementation Details** (app/api/v1/account.py:170-234):
- Verifies current user is a super user
- New user is created in the same tenant as current user
- Created user has regular privileges (is_superuser = false)

## Data Models

### UserAccount (For Requests)
**Implementation File**: app/api/v1/schemas.py:17-26
- `username`: string - Username
- `password`: string - Password (plain text)
- `tenantId`: string (optional) - Tenant ID

### UserAccountInDB (For Database Storage)
**Implementation File**: app/api/v1/schemas.py:29-38
- `username`: string - Username
- `password`: string - Masked display ("*****")
- `hashedPassword`: string - bcrypt hashed password
- `tenantId`: string - Tenant ID
- `isSuperuser`: boolean - Super user flag
- `isActive`: boolean - Account active flag
- `createdAt`: datetime - Creation date/time
- `updatedAt`: datetime (optional) - Update date/time
- `lastLogin`: datetime (optional) - Last login date/time

### LoginResponse
**Implementation File**: app/api/v1/schemas.py:41-49
- `access_token`: string - JWT access token
- `token_type`: string - Token type ("bearer")

## Authentication & Authorization

### JWT Token Structure
```json
{
  "sub": "username",
  "tenant_id": "A1234",
  "is_superuser": true,
  "exp": 1704456000
}
```

### Environment Variables
**Implementation File**: app/config/settings.py
- `SECRET_KEY`: Secret key for JWT signing
- `ALGORITHM`: JWT algorithm (default: "HS256")
- `TOKEN_EXPIRE_MINUTES`: Token expiration time (minutes)
- `MONGODB_URI`: MongoDB connection string (default: "mongodb://localhost:27017/?replicaSet=rs0")
- `DB_NAME_PREFIX`: Database name prefix (default: "db_account")

### Authentication Flow
1. Client sends username, password, and tenant ID to `/api/v1/accounts/token`
2. Server validates credentials (app/dependencies/auth.py:106-127)
3. On successful authentication, returns JWT token (app/dependencies/auth.py:71-89)
4. Client uses `Authorization: Bearer <token>` header for subsequent requests

### Authentication Dependencies
**Implementation File**: app/dependencies/auth.py
- `get_current_user` (lines 153-187): Get current user info from JWT token
- `authenticate_user` (lines 106-127): User authentication
- `authenticate_superuser` (lines 130-150): Super user authentication
- `generate_tenant_id` (lines 190-231): Generate/validate tenant ID

## Error Codes

Account service uses the following error code system:
- **10XXYY**: Account service specific errors
  - XX: Feature identifier
  - YY: Specific error number

## Middleware

**Implementation File**: app/main.py
1. **CORS** (lines 60-66): Allow access from all origins
2. **Request Logging** (line 69): Log all HTTP requests
3. **Exception Handler** (line 72): Unified error response format

## Database

### Collections
**Implementation File**: app/database/database_setup.py
- `user_accounts`: User account information
  - Index: `{tenant_id: 1, username: 1}` (unique)
- `request_log`: Request logs
  - Index: `{tenant_id: 1, store_code: 1, terminal_no: 1, request_info.accept_time: 1}` (unique)

### Multi-tenant Support
- Database name: `db_account_{tenant_id}`
- Each tenant has an independent database
- Tenant ID generation logic: app/dependencies/auth.py:190-231

## Notes

1. Passwords are hashed with bcrypt before storage (app/dependencies/auth.py:58-68)
2. Tenant ID format: 1 uppercase letter + 4 digits (e.g., A1234)
3. Only super users can create new users
4. JWT tokens use Bearer authentication
5. Last login time is automatically updated (app/api/v1/account.py:90-99)
6. All API responses use camelCase format (app/api/common/schemas.py:29)