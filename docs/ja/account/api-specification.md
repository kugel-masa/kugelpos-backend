# アカウントサービスAPI仕様

## 概要

アカウントサービスは、Kugelpos POSシステムにおける認証とユーザー管理APIを提供します。ユーザー登録、認証、JWTトークン管理、セキュアなマルチテナントアーキテクチャによるテナント管理を処理します。

## ベースURL
- ローカル環境: `http://localhost:8000`
- 本番環境: `https://account.{domain}`

## 認証

アカウントサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークン取得元: アカウントサービスの `/api/v1/accounts/token`
- 管理操作に必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- POS端末操作に使用

## フィールド形式

すべてのAPIリクエストとレスポンスは**camelCase**フィールド命名規則を使用します。サービスは`BaseSchemaModel`とトランスフォーマーを使用して、内部のsnake_caseと外部のcamelCase形式を自動的に変換します。

## 共通レスポンス形式

ほとんどのエンドポイントは以下の形式でレスポンスを返します：

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": { ... },
  "operation": "function_name"
}
```

注意: `/token`エンドポイントはApiResponseラッパーを使用せず、OAuth2標準のレスポンス形式を返します。

## APIエンドポイント

### 1. ユーザー認証（ログイン）
**POST** `/api/v1/accounts/token`

ユーザー資格情報を認証し、JWTアクセストークンを返します。

**リクエストボディ（フォームデータ）:**
- `username` (string, 必須): ユーザー名
- `password` (string, 必須): パスワード  
- `client_id` (string, 必須): マルチテナント認証用のテナントID

**リクエスト例:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=password123&client_id=A1234"
```

**レスポンス例:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. スーパーユーザー登録（テナント作成）
**POST** `/api/v1/accounts/register`

新規スーパーユーザーを登録し、新規テナントを作成します。このエンドポイントは新規テナント用の初期管理者ユーザーを作成します。

**リクエストボディ:**
```json
{
  "username": "admin",
  "password": "securePassword123",
  "tenantId": "A1234"
}
```

**フィールド説明:**
- `username` (string, 必須): スーパーユーザーアカウントのユーザー名
- `password` (string, 必須): スーパーユーザーアカウントのパスワード
- `tenantId` (string, オプション): 特定のテナントID。提供されない場合は自動生成されます

**リクエスト例:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "securePassword123",
    "tenantId": "A1234"
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "スーパーユーザーの登録に成功しました",
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

### 3. 一般ユーザー登録
**POST** `/api/v1/accounts/register/user`

既存テナント内に新規一般ユーザーを登録します。スーパーユーザー認証が必要です。

**認証:** スーパーユーザーからのJWTトークンが必要

**リクエストボディ:**
```json
{
  "username": "user001",
  "password": "userPassword123"
}
```

**フィールド説明:**
- `username` (string, 必須): 新規ユーザーアカウントのユーザー名
- `password` (string, 必須): 新規ユーザーアカウントのパスワード

**リクエスト例:**
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/register/user" \
  -H "Authorization: Bearer {superuser_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user001",
    "password": "userPassword123"
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "ユーザーの登録に成功しました",
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

### 4. サービスヘルスチェック
**GET** `/health`

サービスヘルスとデータベース接続ステータスをチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8000/health"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "サービスは正常です",
  "data": {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

### 5. APIルート情報
**GET** `/`

基本的なAPI情報とサポートされているバージョンの詳細を取得します。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8000/"
```

**レスポンス例:**
```json
{
  "message": "KugelposアカウントサービスAPIへようこそ",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

## 認証フロー

### 1. 新規テナント登録フロー
```
1. POST /api/v1/accounts/register
   - スーパーユーザーとテナントを作成
   - 提供されない場合はテナントIDを自動生成
   - テナントデータベースとコレクションをセットアップ
   
2. POST /api/v1/accounts/token
   - 新しい資格情報で認証
   - APIアクセス用のJWTトークンを受信
   
3. 認証された操作にJWTトークンを使用
```

### 2. 一般ユーザー登録フロー
```
1. スーパーユーザーが認証: POST /api/v1/accounts/token
2. 一般ユーザーを作成: POST /api/v1/accounts/register/user
3. 新規ユーザーが認証可能: POST /api/v1/accounts/token
```

### 3. 日常認証フロー
```
1. POST /api/v1/accounts/token (ユーザー名、パスワード、テナントIDを使用)
2. JWTトークンを受信
3. 他のサービスへのAuthorizationヘッダーでトークンを使用
4. 設定された期間後にトークンが期限切れ
5. トークン期限切れ時に再認証
```

## JWTトークンの詳細

### トークン構造
JWTトークンには以下のクレームが含まれます：
- `sub`: ユーザー名
- `tenant_id`: テナント識別子
- `is_superuser`: 管理者権限フラグ
- `is_active`: アカウントステータス
- `exp`: トークン有効期限タイムスタンプ
- `iat`: トークン発行時刻タイムスタンプ

### トークンの使用
```javascript
// 他のサービスへのリクエストに含める
const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
};
```

### トークン検証
他のサービスは以下によってトークンを検証します：
1. JWT署名の検証
2. トークン有効期限のチェック
3. ユーザーの存在とアクティブステータスの検証
4. マルチテナント操作のためのテナントコンテキストの抽出

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 401,
  "message": "無効な資格情報が提供されました",
  "data": null,
  "operation": "login"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `400` - 不正なリクエスト（検証エラー）
- `401` - 認証失敗
- `403` - アクセス拒否（認可失敗）
- `409` - 競合（重複するユーザー名/テナント）
- `500` - 内部サーバーエラー

### エラーコードシステム

アカウントサービスは10XXX範囲のエラーコードを使用します：

- `10001` - 認証失敗（無効な資格情報）
- `10002` - ユーザーが見つかりません
- `10003` - 無効なトークン
- `10004` - テナント作成エラー
- `10005` - ユーザー登録エラー（重複するユーザー名）
- `10006` - 権限不足（スーパーユーザーが必要）
- `10007` - 非アクティブなユーザーアカウント
- `10008` - トークンの期限切れ
- `10099` - 一般的なサービスエラー

## セキュリティの考慮事項

### パスワード要件
- 最小長: 8文字（設定可能）
- 自動ソルト生成によるBCryptハッシュ化
- プレーンテキストパスワードはデータベースに保存されません
- パスワード複雑性検証（将来実装予定）

### トークンセキュリティ
- 設定可能な有効期限（デフォルト: 30分）
- セキュアな署名アルゴリズム（HS256）
- トークンには最小限のユーザー情報を含む
- 各リクエストでの自動トークン検証

### マルチテナントセキュリティ
- テナント間の完全なデータベース分離
- すべての操作でのテナントID検証
- クロステナントアクセス防止
- 一意のテナントID生成

## レート制限

現在、アカウントサービスは明示的なレート制限を実装していませんが、以下の制限が追加される可能性があります：

- IPアドレスごとに1分あたり10回のログイン試行
- ユーザーごとに1時間あたり100リクエスト
- ブルートフォース攻撃保護

## 設定オプション

### 環境変数
```bash
# データベース設定
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_account

# JWT設定  
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
TOKEN_EXPIRE_MINUTES=30

# サービス設定
DEBUG=false
DEBUG_PORT=5678
```

### データベースコレクション
- `user_accounts`: ユーザーアカウント情報
- `request_log`: HTTPリクエスト監査ログ

## 統合例

### フロントエンド認証
```javascript
// ログイン関数
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
  if (result.success) {
    localStorage.setItem('accessToken', result.data.accessToken);
    return result.data.accessToken;
  }
  throw new Error(result.message);
}

// トークンを使用したAPIリクエスト
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

### サービス間認証
```python
# 他のサービスでJWTトークンを検証
from jose import JWTError, jwt

def validate_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        is_active = payload.get("is_active", False)
        
        if not username or not tenant_id or not is_active:
            raise HTTPException(status_code=401, detail="無効なトークン")
            
        return {
            "username": username,
            "tenant_id": tenant_id,
            "is_superuser": payload.get("is_superuser", False)
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="無効なトークン")
```

## テスト

### 認証テスト
```bash
# ユーザー登録をテスト
curl -X POST "http://localhost:8000/api/v1/accounts/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'

# 認証をテスト
curl -X POST "http://localhost:8000/api/v1/accounts/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123&client_id=A1234"

# ヘルスチェックをテスト
curl -X GET "http://localhost:8000/health"
```

## 注意事項

1. **OAuth2準拠**: OAuth2パスワードフロー標準に従います
2. **マルチテナントアーキテクチャ**: 各テナントには分離されたデータとユーザーがあります
3. **セキュリティファースト**: BCryptハッシュ化、JWTトークン、包括的な検証
4. **CamelCase規約**: すべてのJSONフィールドはcamelCase形式を使用
5. **非同期アーキテクチャ**: パフォーマンスのためのフル非同期/await実装
6. **本番環境対応**: ヘルスモニタリング、ログ記録、エラー処理
7. **拡張可能な設計**: MFAやSSOなどの将来の拡張に対応

アカウントサービスは、Kugelpos POSシステム全体の基盤認証レイヤーを提供し、複数のテナント間でセキュアでスケーラブルなユーザー管理を保証します。