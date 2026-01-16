# アカウントサービス API仕様書

## 概要

ユーザー認証とJWTトークン管理を提供するサービスです。

## サービス情報

- **ポート**: 8000
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8000`
- 本番環境: `https://account.{domain}`

## 認証

以下の認証方法をサポートしています：

### APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からのAPI呼び出し

### JWTトークン認証
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるシステム操作

## 共通レスポンス形式

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": {
    "...": "..."
  },
  "operation": "operation_name"
}
```

## APIエンドポイント

### システム

### 1. ルートエンドポイント

**GET** `/`

ルートエンドポイントです。ウェルカムメッセージとAPI情報を返します。

**レスポンス:**

### 2. ヘルスチェック

**GET** `/health`

ヘルスチェックエンドポイントです。サービスの稼働状態を監視します。

**レスポンス:**

**レスポンス例:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "service": "string",
  "version": "string",
  "checks": {}
}
```

### アカウント

### 3. スーパーユーザー登録

**POST** `/api/v1/accounts/register`

スーパーユーザーを登録し、新しいテナントを作成します。

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | No | - |

**リクエスト例:**
```json
{
  "username": "string",
  "password": "string",
  "tenantId": "string"
}
```

**レスポンス:**

**dataフィールド:** `UserAccountInDB`

| フィールド | 型 | 必須 | 説明 |
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

**レスポンス例:**
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

### 4. ユーザー登録

**POST** `/api/v1/accounts/register/user`

スーパーユーザーを登録し、新しいテナントを作成します。

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `username` | string | Yes | - |
| `password` | string | Yes | - |
| `tenantId` | string | No | - |

**リクエスト例:**
```json
{
  "username": "string",
  "password": "string",
  "tenantId": "string"
}
```

**レスポンス:**

**dataフィールド:** `UserAccountInDB`

| フィールド | 型 | 必須 | 説明 |
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

**レスポンス例:**
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

### 5. アクセストークン取得

**POST** `/api/v1/accounts/token`

ユーザーを認証し、JWTアクセストークンを発行します。

**レスポンス:**

**レスポンス例:**
```json
{
  "access_token": "string",
  "token_type": "string"
}
```

## エラーコード

エラーレスポンスは以下の形式で返されます：

```json
{
  "success": false,
  "code": 400,
  "message": "エラーメッセージ",
  "errorCode": "ERROR_CODE",
  "operation": "operation_name"
}
```
