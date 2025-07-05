# Account Service Model Specification

## Overview

This document provides detailed specifications for data models used in the Account service. All models are stored in MongoDB and operate in a multi-tenant environment.

## Database Configuration

### Database Name
- Format: `db_account_{tenant_id}`
- Example: `db_account_A1234`
- Each tenant has an independent database

### Collection List
1. `user_accounts` - User account information
2. `request_log` - API request logs (common)

## Model Definitions

### 1. UserAccount (For API Requests)

**Implementation File**: app/api/v1/schemas.py:17-26  
**Base Class**: BaseUserAccount (app/api/common/schemas.py:37-46)

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| username | string | Yes | Username (login ID) |
| password | string | Yes | Password (plain text) |
| tenantId | string | No | Tenant ID (can be auto-generated) |

**JSON Format Example**:
```json
{
  "username": "admin",
  "password": "secure_password123",
  "tenantId": "A1234"
}
```

### 2. UserAccountInDB (For Database Storage)

**Implementation File**: app/api/v1/schemas.py:29-38  
**Base Class**: BaseUserAccountInDB (app/api/common/schemas.py:48-61)

| Field Name | Type | Required | Default | Description |
|------------|------|----------|---------|-------------|
| username | string | Yes | - | Username |
| password | string | Yes | "*****" | Masked display (not actually stored) |
| hashed_password | string | Yes | - | bcrypt hashed password |
| tenant_id | string | Yes | - | Tenant ID |
| is_superuser | boolean | Yes | false | Super user flag |
| is_active | boolean | Yes | true | Account active flag |
| created_at | datetime | Yes | - | Creation date/time |
| updated_at | datetime | No | null | Update date/time |
| last_login | datetime | No | null | Last login date/time |

**MongoDB Storage Format Example**:
```json
{
  "_id": ObjectId("..."),
  "username": "admin",
  "password": "*****",
  "hashed_password": "$2b$12$...",
  "tenant_id": "A1234",
  "is_superuser": true,
  "is_active": true,
  "created_at": ISODate("2025-01-05T10:30:00.000Z"),
  "updated_at": null,
  "last_login": ISODate("2025-01-05T11:00:00.000Z")
}
```

### 3. LoginResponse (Token Response)

**Implementation File**: app/api/v1/schemas.py:41-49  
**Base Class**: BaseLoginResponse (app/api/common/schemas.py:63-71)

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| access_token | string | Yes | JWT access token |
| token_type | string | Yes | Token type (always "bearer") |

**JSON Format Example**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Sample (Demo Model)

**Implementation File**: app/api/v1/schemas.py:52-60  
**Base Class**: BaseSample (app/api/common/schemas.py:74-84)

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenantId | string | Yes | Tenant ID |
| storeCode | string | Yes | Store code |
| sampleId | string | Yes | Sample ID |
| sampleName | string | Yes | Sample name |

## Collection Details

### 1. user_accounts Collection

**Implementation File**: app/database/database_setup.py:41-58

**Index**:
```javascript
{
  "tenant_id": 1,
  "username": 1
}
// unique: true
```

**Purpose**: Store user account information
- Username is unique within each tenant
- Store bcrypt hashed passwords
- Distinguish between super users and regular users
- Record last login time

### 2. request_log Collection

**Implementation File**: app/database/database_setup.py:61-80

**Index**:
```javascript
{
  "tenant_id": 1,
  "store_code": 1,
  "terminal_no": 1,
  "request_info.accept_time": 1
}
// unique: true
```

**Purpose**: Store API request logs
- Record all HTTP requests
- Used as audit trail
- Can be used for performance analysis

## Data Type Conversion

### camelCase Conversion
**Implementation File**: app/api/common/schemas.py:23-30

All API responses inherit from `BaseSchemaModel` and automatically convert from snake_case to camelCase.

**Conversion Examples**:
- `tenant_id` → `tenantId`
- `is_superuser` → `isSuperuser`
- `created_at` → `createdAt`
- `last_login` → `lastLogin`
- `hashed_password` → `hashedPassword` (not included in responses)

### Date/Time Format
- Stored and returned in ISO 8601 format
- Timezone: UTC
- Example: `2025-01-05T10:30:00.000Z`

## Validation

### Tenant ID
**Implementation File**: app/dependencies/auth.py:207-210
- Format: 1 uppercase letter + 4 digits
- Regex: `^[A-Z][0-9]{4}$`
- Examples: `A1234`, `B9999`
- Generation logic: Random uppercase letter + number between 1000-9999

### Password
**Implementation File**: app/dependencies/auth.py:44-68
- Hashed with bcrypt
- Cost factor: Default (12)
- Minimum length: No restriction (controlled at application level)
- Verification: Compare plain text with hash using `verify_password()` function

### Username
- Maximum length: No restriction (controlled at application level)
- Allowed characters: No restriction (controlled at application level)
- Unique within each tenant (enforced by database index)

## JWT Token Structure

**Implementation File**: app/dependencies/auth.py:71-89

### Token Payload
```json
{
  "sub": "username",
  "tenant_id": "A1234",
  "is_superuser": true,
  "exp": 1704456000
}
```

### Token Configuration
- `SECRET_KEY`: Secret key for JWT signing (environment variable)
- `ALGORITHM`: JWT algorithm (default: "HS256")
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time (set via environment variable)

## OAuth2PasswordRequestForm

**Usage**: app/api/v1/account.py:57

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| username | string | Yes | Username |
| password | string | Yes | Password |
| client_id | string | Yes | Used as tenant ID |
| grant_type | string | No | "password" (default) |
| scope | string | No | Scope (unused) |

**Note**: OAuth2 standard `client_id` field is repurposed as tenant ID

## Security Considerations

1. **Password Protection**
   - Plain text passwords are never stored
   - Salted hashing with bcrypt (app/dependencies/auth.py:58-68)
   - Masked with "*****" in responses

2. **Tenant Isolation**
   - Complete separation at database level
   - Cross-tenant access not possible
   - Tenant ID validated for each operation

3. **Audit Logging**
   - All requests recorded in request_log
   - Unauthorized access tracking possible

4. **JWT Security**
   - Stateless authentication
   - Signed tokens
   - Automatic expiration checking

## Database Setup

**Implementation File**: app/database/database_setup.py:101-118

**Setup Process**:
1. `execute()` function called when creating new tenant
2. Required collections created:
   - `create_user_account_collection()`: user_accounts collection
   - `create_request_log_collection()`: request_log collection
3. Indexes automatically configured

## Notes

1. **_id field**: Uses MongoDB's auto-generated ObjectId
2. **Case sensitivity**: Username is case-sensitive
3. **Deletion flag**: Logical deletion not implemented (managed with `is_active`)
4. **Update history**: `updated_at` requires manual updating
5. **Transactions**: Currently not implemented
6. **Password change feature**: Currently not implemented
7. **Migration**: Dedicated migration tool not implemented