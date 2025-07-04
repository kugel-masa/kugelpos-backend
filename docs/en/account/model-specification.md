# Account Service Model Specification

## Overview

Account Service consists of data models for user authentication and account management, API schemas, and transformers that manage conversions between them. All models have strict type definitions and validation rules to ensure data integrity and security.

## Database Document Models

### 1. UserAccountDocument (User Account Document)

Main document for storing user account information with secure credential management.

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| username | string | ✓ | Unique username within tenant |
| hashed_password | string | ✓ | BCrypt hashed password with salt |
| tenant_id | string | ✓ | Tenant identifier for multi-tenant isolation |
| is_superuser | bool | ✓ | Admin privileges flag (default: False) |
| is_active | bool | ✓ | Account status flag (default: True) |
| created_at | datetime | ✓ | Account creation timestamp |
| updated_at | datetime | - | Last update timestamp |
| last_login | datetime | - | Last successful login timestamp |
| shard_key | string | ✓ | Sharding key (inherited from AbstractDocument) |
| etag | string | ✓ | ETag for optimistic locking (inherited from AbstractDocument) |

**Indexes:**
- Compound unique index: (tenant_id, username) - Ensures unique usernames per tenant
- Index: tenant_id
- Index: is_active
- Index: is_superuser

**Collection Name:** "user_accounts"

**Security Features:**
- Plain text passwords never stored
- BCrypt hashing with automatic salt generation
- Tenant isolation at database level
- Optimistic locking with ETag

## API Request Schemas

All schemas inherit from `BaseSchemaModel` and provide the following features:
- Automatic camelCase conversion for JSON fields (snake_case → camelCase)
- Pydantic validation with type safety
- Secure password handling

### 1. BaseUserAccount (Registration Request Schema)

Base schema for user account creation requests.

**Field Definitions:**

| Field Name | Type | Required | Validation | Description |
|------------|------|----------|------------|-------------|
| username | string | ✓ | 3-50 chars, alphanumeric + underscore | Username for authentication |
| password | string | ✓ | 8+ chars (configurable) | Plain text password (never stored) |
| tenantId | string | - | 5 chars: 1 letter + 4 digits | Tenant identifier (auto-generated if not provided) |

**Validation Rules:**
- `username`: Must be unique within tenant, 3-50 characters, alphanumeric and underscore only
- `password`: Minimum 8 characters, stored as BCrypt hash
- `tenantId`: Format validation (A1234), auto-generated for superuser registration

### 2. OAuth2PasswordRequestForm (Login Request)

Standard OAuth2 password flow request for authentication.

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| username | string | ✓ | User's username |
| password | string | ✓ | User's password |
| client_id | string | ✓ | Tenant ID (used as OAuth2 client identifier) |
| grant_type | string | - | OAuth2 grant type (default: "password") |
| scope | string | - | OAuth2 scope (default: "") |

**Usage Notes:**
- Follows OAuth2 password flow standard
- `client_id` field contains tenant ID for multi-tenant authentication
- Form-encoded request body (application/x-www-form-urlencoded)

## API Response Schemas

### 1. BaseUserAccountInDB (User Account Response)

Response schema for user account information with secure field handling.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| username | string | Username |
| password | string | Always masked as "*****" for security |
| tenantId | string | Tenant identifier |
| isSuperuser | bool | Admin privileges flag |
| isActive | bool | Account status |
| createdAt | datetime | Account creation timestamp |
| updatedAt | datetime (optional) | Last update timestamp |
| lastLogin | datetime (optional) | Last successful login timestamp |

**Security Features:**
- `password` field always returns "*****" to prevent exposure
- `hashedPassword` field never included in responses
- Automatic timestamp management
- CamelCase conversion for frontend compatibility

### 2. BaseLoginResponse (Authentication Response)

Response schema for successful authentication.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| access_token | string | JWT token for API authentication |
| token_type | string | Token type ("bearer") |

**Note:** This schema inherits from `BaseModel` (not `BaseSchemaModel`), so fields remain in snake_case format.

**Token Structure:**
The JWT token contains the following claims:
- `sub`: Username
- `tenant_id`: Tenant identifier
- `is_superuser`: Admin privileges flag
- `is_active`: Account status
- `exp`: Token expiration timestamp
- `iat`: Token issued at timestamp

### 3. HealthCheckResponse (Health Check Response)

Response schema for service health monitoring.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| status | string | Service status ("healthy", "unhealthy") |
| database | string | Database connection status ("connected", "disconnected") |
| timestamp | datetime | Health check timestamp |

## JWT Token Model

### JWT Claims Structure

The JWT token payload contains the following standardized claims:

```json
{
  "sub": "username",           // Subject (username)
  "tenant_id": "A1234",        // Tenant identifier
  "is_superuser": false,       // Admin privileges
  "is_active": true,           // Account status
  "exp": 1640995200,           // Expiration timestamp
  "iat": 1640991600            // Issued at timestamp
}
```

### Token Configuration

**Environment Settings:**
- `SECRET_KEY`: JWT signing secret
- `ALGORITHM`: Signing algorithm (default: HS256)
- `TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 30 minutes)

## Data Flow and Relationships

### 1. User Registration Flow
```
[API Request] → [Schema Validation] → [Password Hashing]
    ↓
[Tenant Validation/Generation] → [UserAccountDocument Creation]
    ↓
[Database Storage] → [Response Transformation] → [API Response]
```

### 2. Authentication Flow
```
[Login Request] → [Credential Validation] → [User Lookup]
    ↓
[Password Verification] → [JWT Token Generation] → [Login Timestamp Update]
    ↓
[Token Response] → [API Response]
```

### 3. Token Validation Flow
```
[Incoming Request] → [JWT Token Extraction] → [Token Verification]
    ↓
[Claims Extraction] → [User Status Validation] → [Request Authorization]
```

## Validation Rules

### 1. Username Validation
- **Length**: 3-50 characters
- **Characters**: Alphanumeric and underscore only (regex: `^[a-zA-Z0-9_]+$`)
- **Uniqueness**: Must be unique within tenant
- **Case Sensitivity**: Case-sensitive usernames

### 2. Password Validation
- **Minimum Length**: 8 characters (configurable via environment)
- **Hashing**: BCrypt with automatic salt generation
- **Storage**: Only hashed passwords stored in database
- **Validation**: Plain text password validated against hash

### 3. Tenant ID Validation
- **Format**: 1 letter followed by 4 digits (e.g., "A1234")
- **Generation**: Auto-generated if not provided during superuser registration
- **Uniqueness**: Must be unique across all tenants
- **Validation**: Regex pattern `^[A-Z][0-9]{4}$`

### 4. JWT Token Validation
- **Signature**: Verified using secret key and algorithm
- **Expiration**: Token must not be expired
- **Claims**: Required claims must be present and valid
- **User Status**: User must exist and be active

## Security Features

### 1. Password Security
- **BCrypt Hashing**: Industry-standard password hashing with salt
- **No Plain Text Storage**: Passwords never stored in plain text
- **Secure Comparison**: Constant-time password verification
- **Hash Strength**: Configurable work factor (default: 12 rounds)

### 2. Multi-tenant Isolation
- **Database Separation**: Each tenant has dedicated database
- **Access Control**: Cross-tenant access prevented at application level
- **Unique Constraints**: Username uniqueness within tenant scope
- **Data Isolation**: Complete separation of tenant data

### 3. JWT Token Security
- **Signed Tokens**: HMAC-SHA256 signature for integrity
- **Expiration**: Configurable token lifetime
- **Minimal Claims**: Only necessary information in payload
- **Stateless**: No server-side session storage required

### 4. Authentication Security
- **Active User Check**: Inactive users cannot authenticate  
- **Tenant Validation**: Tenant must exist for authentication
- **Audit Logging**: Login attempts and authentication events logged
- **Secure Endpoints**: Critical endpoints require proper authentication

## Field Naming Conventions

### 1. Database Models
- **Convention**: snake_case (e.g., `is_superuser`)
- **Reason**: Python and MongoDB standard naming
- **Consistency**: Matches other services in the system

### 2. API Schemas
- **Convention**: camelCase (e.g., `isSuperuser`)
- **Reason**: JavaScript/TypeScript frontend compatibility
- **Conversion**: Automatic conversion via `BaseSchemaModel`

### 3. Conversion Examples
```
Database: is_superuser → API: isSuperuser
Database: created_at → API: createdAt
Database: last_login → API: lastLogin
Database: tenant_id → API: tenantId
Database: hashed_password → API: (not exposed)
```

## Performance Optimization

### 1. Database Optimization
- **Indexes**: Optimized indexes on frequently queried fields
- **Compound Indexes**: Efficient multi-field queries
- **Connection Pooling**: Async connection management
- **Query Optimization**: Efficient lookup patterns

### 2. Authentication Optimization
- **Password Hashing**: Balanced security vs performance
- **Token Caching**: Stateless JWT reduces database lookups
- **Async Operations**: Non-blocking I/O throughout service
- **Minimal Payloads**: Compact token and response sizes

### 3. Memory Management
- **Lazy Loading**: Load user data only when needed
- **Connection Reuse**: Efficient database connection pooling
- **Garbage Collection**: Proper resource cleanup

## Error Handling

### 1. Validation Errors
- **Pydantic Validation**: Automatic request validation
- **Custom Validators**: Domain-specific validation rules
- **Error Messages**: Clear, actionable error descriptions
- **Field-level Errors**: Specific field validation feedback

### 2. Authentication Errors
- **Invalid Credentials**: Secure error messages (no user enumeration)
- **Token Errors**: Detailed JWT validation error handling
- **Permission Errors**: Clear authorization failure messages
- **Account Status**: Inactive account error handling

### 3. System Errors
- **Database Errors**: Graceful database connection failure handling
- **Service Errors**: Proper HTTP status code mapping
- **Logging**: Comprehensive error logging for debugging
- **Recovery**: Automatic retry and fallback mechanisms

## Testing Strategy

### 1. Unit Testing
- **Model Validation**: Test all schema validation rules
- **Password Hashing**: Verify secure password handling
- **JWT Operations**: Test token generation and validation
- **Business Logic**: Test user registration and authentication flows

### 2. Integration Testing
- **Database Operations**: Test all CRUD operations
- **Authentication Flow**: End-to-end authentication testing
- **Multi-tenant**: Test tenant isolation and security
- **API Endpoints**: Comprehensive API testing

### 3. Security Testing
- **Password Security**: Test hashing and verification
- **Token Security**: Test JWT token handling
- **Access Control**: Test authorization and permissions
- **Input Validation**: Test against malicious input

This model specification provides a comprehensive understanding of the Account Service data structures, security implementation, and enables effective development and maintenance of the authentication system.