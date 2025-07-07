# Account Service API 仕様書

## 概要

Account サービスは、ユーザー認証とJWT トークン管理を提供するマイクロサービスです。マルチテナント対応で、各テナントごとに独立したユーザー管理を実現します。

## サービス情報

- **ポート**: 8000
- **フレームワーク**: FastAPI
- **認証方式**: JWT (OAuth2PasswordBearer)
- **データベース**: MongoDB (Motor 非同期ドライバー)
- **パスワード暗号化**: bcrypt

## API エンドポイント

### 1. ルートエンドポイント

**パス**: `/`  
**メソッド**: GET  
**認証**: 不要  
**説明**: サービスの稼働確認用エンドポイント

**レスポンス**:
```json
{
  "message": "Welcome to Kugel-POS Auth API. supported version: v1"
}
```

**実装ファイル**: app/main.py:75-82

### 2. ヘルスチェック

**パス**: `/health`  
**メソッド**: GET  
**認証**: 不要  
**説明**: サービスの健全性を確認するエンドポイント

**レスポンスモデル**: `HealthCheckResponse`
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

**実装ファイル**: app/main.py:84-112

### 3. トークン取得

**パス**: `/api/v1/accounts/token`  
**メソッド**: POST  
**認証**: 不要  
**説明**: ユーザー認証を行い、JWT アクセストークンを発行

**リクエスト**: `OAuth2PasswordRequestForm`
- `username`: string (必須) - ユーザー名
- `password`: string (必須) - パスワード
- `client_id`: string (必須) - テナントID として使用

**レスポンスモデル**: `LoginResponse`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**エラーレスポンス**:
- 400: Bad Request
- 401: Unauthorized - 認証情報が正しくない場合
- 422: Unprocessable Entity
- 500: Internal Server Error

**実装詳細** (app/api/v1/account.py:46-101):
- ユーザー名、パスワード、テナントID を使用して認証
- 認証成功時、最終ログイン時刻を更新
- JWT トークンには username、tenant_id、is_superuser を含む
- トークン有効期限は環境変数 `TOKEN_EXPIRE_MINUTES` で設定

### 4. スーパーユーザー登録（テナント作成）

**パス**: `/api/v1/accounts/register`  
**メソッド**: POST  
**認証**: 不要  
**説明**: 新規テナントとスーパーユーザーを作成

**リクエストモデル**: `UserAccount`
```json
{
  "username": "admin",
  "password": "secure_password123",
  "tenantId": "A1234"  // オプション - 未指定時は自動生成
}
```

**レスポンスモデル**: `ApiResponse[UserAccountInDB]`
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

**エラーレスポンス**:
- 400: Bad Request
- 401: Unauthorized
- 422: Unprocessable Entity
- 500: Internal Server Error

**実装詳細** (app/api/v1/account.py:105-166):
- テナントID は自動生成または指定可能（形式: 大文字1文字 + 4桁数字）
- 新規テナント用のデータベースを作成
- 作成されたユーザーは自動的にスーパーユーザー権限を持つ
- Slack 通知を送信（設定されている場合）

### 5. 一般ユーザー登録

**パス**: `/api/v1/accounts/register/user`  
**メソッド**: POST  
**認証**: 必須（スーパーユーザーのみ）  
**説明**: 同一テナント内に一般ユーザーを作成

**リクエストヘッダー**:
```
Authorization: Bearer <JWT_TOKEN>
```

**リクエストモデル**: `UserAccount`
```json
{
  "username": "user01",
  "password": "user_password123"
}
```

**レスポンスモデル**: `ApiResponse[UserAccountInDB]`
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

**エラーレスポンス**:
- 400: Bad Request
- 401: Unauthorized - スーパーユーザー権限がない場合
- 422: Unprocessable Entity
- 500: Internal Server Error

**実装詳細** (app/api/v1/account.py:170-234):
- 現在のユーザーがスーパーユーザーであることを確認
- 新規ユーザーは現在のユーザーと同じテナントに作成される
- 作成されるユーザーは一般ユーザー権限（is_superuser = false）

## データモデル

### UserAccount (リクエスト用)
**実装ファイル**: app/api/v1/schemas.py:17-26
- `username`: string - ユーザー名
- `password`: string - パスワード（平文）
- `tenantId`: string (optional) - テナントID

### UserAccountInDB (データベース保存用)
**実装ファイル**: app/api/v1/schemas.py:29-38
- `username`: string - ユーザー名
- `password`: string - マスク表示（"*****"）
- `hashedPassword`: string - bcrypt でハッシュ化されたパスワード
- `tenantId`: string - テナントID
- `isSuperuser`: boolean - スーパーユーザーフラグ
- `isActive`: boolean - アカウント有効フラグ
- `createdAt`: datetime - 作成日時
- `updatedAt`: datetime (optional) - 更新日時
- `lastLogin`: datetime (optional) - 最終ログイン日時

### LoginResponse
**実装ファイル**: app/api/v1/schemas.py:41-49
- `access_token`: string - JWT アクセストークン
- `token_type`: string - トークンタイプ（"bearer"）

## 認証・認可

### JWT トークン構造
```json
{
  "sub": "username",
  "tenant_id": "A1234",
  "is_superuser": true,
  "exp": 1704456000
}
```

### 環境変数
**実装ファイル**: app/config/settings.py
- `SECRET_KEY`: JWT 署名用の秘密鍵
- `ALGORITHM`: JWT アルゴリズム（デフォルト: "HS256"）
- `TOKEN_EXPIRE_MINUTES`: トークン有効期限（分）
- `MONGODB_URI`: MongoDB 接続文字列（デフォルト: "mongodb://localhost:27017/?replicaSet=rs0"）
- `DB_NAME_PREFIX`: データベース名プレフィックス（デフォルト: "db_account"）

### 認証フロー
1. クライアントが `/api/v1/accounts/token` にユーザー名、パスワード、テナントID を送信
2. サーバーが認証情報を検証（app/dependencies/auth.py:106-127）
3. 認証成功時、JWT トークンを返却（app/dependencies/auth.py:71-89）
4. クライアントは以降のリクエストで `Authorization: Bearer <token>` ヘッダーを使用

### 認証依存関数
**実装ファイル**: app/dependencies/auth.py
- `get_current_user` (153-187行目): JWT トークンから現在のユーザー情報を取得
- `authenticate_user` (106-127行目): ユーザー認証
- `authenticate_superuser` (130-150行目): スーパーユーザー認証
- `generate_tenant_id` (190-231行目): テナントID の生成・検証

## エラーコード

Account サービスでは以下のエラーコード体系を使用：
- **10XXYY**: Account サービス固有のエラー
  - XX: 機能識別子
  - YY: 具体的なエラー番号

## ミドルウェア

**実装ファイル**: app/main.py
1. **CORS** (60-66行目): 全オリジンからのアクセスを許可
2. **リクエストログ** (69行目): 全HTTPリクエストをログ記録
3. **例外ハンドラー** (72行目): 統一されたエラーレスポンス形式

## データベース

### コレクション
**実装ファイル**: app/database/database_setup.py
- `user_accounts`: ユーザーアカウント情報
  - インデックス: `{tenant_id: 1, username: 1}` (unique)
- `request_log`: リクエストログ
  - インデックス: `{tenant_id: 1, store_code: 1, terminal_no: 1, request_info.accept_time: 1}` (unique)

### マルチテナント対応
- データベース名: `db_account_{tenant_id}`
- 各テナントは独立したデータベースを持つ
- テナントID 生成ロジック: app/dependencies/auth.py:190-231

## 注意事項

1. パスワードは bcrypt でハッシュ化して保存（app/dependencies/auth.py:58-68）
2. テナントID は大文字1文字 + 4桁数字の形式（例: A1234）
3. スーパーユーザーのみが新規ユーザーを作成可能
4. JWT トークンは Bearer 認証で使用
5. 最終ログイン時刻は自動的に更新される（app/api/v1/account.py:90-99）
6. 全ての API レスポンスは camelCase 形式（app/api/common/schemas.py:29）