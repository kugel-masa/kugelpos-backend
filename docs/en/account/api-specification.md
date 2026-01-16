# Account Service API Specification

## Overview

Provides user authentication and JWT token management.

## Service Information

- **Port**: 8000
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8000`
- Production Environment: `https://account.{domain}`

## Authentication

The following authentication methods are supported:

### API Key Authentication
- Header: `X-API-Key: {api_key}`
- Usage: API calls from terminals

### JWT Token Authentication
- Header: `Authorization: Bearer {token}`
- Usage: System operations by administrators

## Common Response Format

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": {
    "...": "..."
  },
  "operation": "operation_name"
}
```

## API Endpoints

### System

### 1. Root

**GET** `/`

Root endpoint that returns a welcome message.
Useful for health checks and API verification.

**Response:**

### 2. Health Check

**GET** `/health`

Health check endpoint for monitoring service health.

**Response:**

**Response Example:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "service": "string",
  "version": "string",
  "checks": {}
}
```

### Account

### 3. Register Super User

**POST** `/api/v1/accounts/register`

Register a new superuser and create a new tenant

This endpoint is used for initial setup of a tenant and its admin user

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | No | - |

**Request Example:**
```json
{
  "username": "string",
  "password": "string",
  "tenantId": "string"
}
```

**Response:**

**data Field:** `UserAccountInDB`

| Field | Type | Required | Description |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `hashedPassword` | string | Yes | - |
| `isSuperuser` | boolean | No | - |
| `isActive` | boolean | No | - |
| `createdAt` | string | Yes | - |
| `updatedAt` | string | No | - |
| `lastLogin` | string | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "username": "string",
    "password": "string",
    "tenantId": "string",
    "hashedPassword": "string",
    "isSuperuser": false,
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "lastLogin": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 4. Register User By Superuser

**POST** `/api/v1/accounts/register/user`

Register a new regular user in the tenant by a superuser

This endpoint is protected and can only be called by authenticated superusers

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | No | - |

**Request Example:**
```json
{
  "username": "string",
  "password": "string",
  "tenantId": "string"
}
```

**Response:**

**data Field:** `UserAccountInDB`

| Field | Type | Required | Description |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `hashedPassword` | string | Yes | - |
| `isSuperuser` | boolean | No | - |
| `isActive` | boolean | No | - |
| `createdAt` | string | Yes | - |
| `updatedAt` | string | No | - |
| `lastLogin` | string | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "username": "string",
    "password": "string",
    "tenantId": "string",
    "hashedPassword": "string",
    "isSuperuser": false,
    "isActive": true,
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "lastLogin": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 5. Login For Access Token

**POST** `/api/v1/accounts/token`

Authenticate user and provide a JWT access token

The client_id field in the form is used as the tenant_id for multi-tenant support

**Response:**

**Response Example:**
```json
{
  "access_token": "string",
  "token_type": "string"
}
```

## Error Codes

Error responses are returned in the following format:

```json
{
  "success": false,
  "code": 400,
  "message": "Error message",
  "errorCode": "ERROR_CODE",
  "operation": "operation_name"
}
```
