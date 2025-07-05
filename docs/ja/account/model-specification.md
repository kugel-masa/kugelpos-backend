# Account Service モデル仕様書

## 概要

Account サービスで使用されるデータモデルの詳細仕様です。全てのモデルは MongoDB に保存され、マルチテナント環境で動作します。

## データベース構成

### データベース名
- 形式: `db_account_{tenant_id}`
- 例: `db_account_A1234`
- 各テナントは独立したデータベースを持つ

### コレクション一覧
1. `user_accounts` - ユーザーアカウント情報
2. `request_log` - API リクエストログ（共通）

## モデル定義

### 1. UserAccount（API リクエスト用）

**実装ファイル**: app/api/v1/schemas.py:17-26  
**基底クラス**: BaseUserAccount (app/api/common/schemas.py:37-46)

| フィールド名 | 型 | 必須 | 説明 |
|------------|---|------|------|
| username | string | Yes | ユーザー名（ログインID） |
| password | string | Yes | パスワード（平文） |
| tenantId | string | No | テナントID（自動生成可能） |

**JSON 形式の例**:
```json
{
  "username": "admin",
  "password": "secure_password123",
  "tenantId": "A1234"
}
```

### 2. UserAccountInDB（データベース保存用）

**実装ファイル**: app/api/v1/schemas.py:29-38  
**基底クラス**: BaseUserAccountInDB (app/api/common/schemas.py:48-61)

| フィールド名 | 型 | 必須 | デフォルト | 説明 |
|------------|---|------|-----------|------|
| username | string | Yes | - | ユーザー名 |
| password | string | Yes | "*****" | マスク表示（実際には保存されない） |
| hashed_password | string | Yes | - | bcrypt ハッシュ化されたパスワード |
| tenant_id | string | Yes | - | テナントID |
| is_superuser | boolean | Yes | false | スーパーユーザーフラグ |
| is_active | boolean | Yes | true | アカウント有効フラグ |
| created_at | datetime | Yes | - | 作成日時 |
| updated_at | datetime | No | null | 更新日時 |
| last_login | datetime | No | null | 最終ログイン日時 |

**MongoDB 保存形式の例**:
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

### 3. LoginResponse（トークンレスポンス）

**実装ファイル**: app/api/v1/schemas.py:41-49  
**基底クラス**: BaseLoginResponse (app/api/common/schemas.py:63-71)

| フィールド名 | 型 | 必須 | 説明 |
|------------|---|------|------|
| access_token | string | Yes | JWT アクセストークン |
| token_type | string | Yes | トークンタイプ（常に "bearer"） |

**JSON 形式の例**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Sample（デモ用モデル）

**実装ファイル**: app/api/v1/schemas.py:52-60  
**基底クラス**: BaseSample (app/api/common/schemas.py:74-84)

| フィールド名 | 型 | 必須 | 説明 |
|------------|---|------|------|
| tenantId | string | Yes | テナントID |
| storeCode | string | Yes | 店舗コード |
| sampleId | string | Yes | サンプルID |
| sampleName | string | Yes | サンプル名 |

## コレクション詳細

### 1. user_accounts コレクション

**実装ファイル**: app/database/database_setup.py:41-58

**インデックス**:
```javascript
{
  "tenant_id": 1,
  "username": 1
}
// unique: true
```

**用途**: ユーザーアカウント情報の保存
- 各テナント内でユーザー名は一意
- bcrypt でハッシュ化されたパスワードを保存
- スーパーユーザーと一般ユーザーを区別
- 最終ログイン時刻を記録

### 2. request_log コレクション

**実装ファイル**: app/database/database_setup.py:61-80

**インデックス**:
```javascript
{
  "tenant_id": 1,
  "store_code": 1,
  "terminal_no": 1,
  "request_info.accept_time": 1
}
// unique: true
```

**用途**: API リクエストログの保存
- 全ての HTTP リクエストを記録
- 監査証跡として使用
- パフォーマンス分析に利用可能

## データ型変換

### camelCase 変換
**実装ファイル**: app/api/common/schemas.py:23-30

全ての API レスポンスは `BaseSchemaModel` を継承し、自動的に snake_case から camelCase に変換されます。

**変換例**:
- `tenant_id` → `tenantId`
- `is_superuser` → `isSuperuser`
- `created_at` → `createdAt`
- `last_login` → `lastLogin`
- `hashed_password` → `hashedPassword` （ただし、レスポンスには含まれない）

### 日時フォーマット
- ISO 8601 形式で保存・返却
- タイムゾーン: UTC
- 例: `2025-01-05T10:30:00.000Z`

## バリデーション

### テナントID
**実装ファイル**: app/dependencies/auth.py:207-210
- 形式: 大文字1文字 + 4桁数字
- 正規表現: `^[A-Z][0-9]{4}$`
- 例: `A1234`, `B9999`
- 生成ロジック: ランダムな大文字1文字 + 1000-9999 の数字

### パスワード
**実装ファイル**: app/dependencies/auth.py:44-68
- bcrypt によるハッシュ化
- コスト係数: デフォルト（12）
- 最小長: 制限なし（アプリケーション側で制御）
- 検証: `verify_password()` 関数で平文とハッシュを比較

### ユーザー名
- 最大長: 制限なし（アプリケーション側で制御）
- 使用可能文字: 制限なし（アプリケーション側で制御）
- 各テナント内で一意（データベースインデックスで強制）

## JWT トークン構造

**実装ファイル**: app/dependencies/auth.py:71-89

### トークンペイロード
```json
{
  "sub": "username",
  "tenant_id": "A1234",
  "is_superuser": true,
  "exp": 1704456000
}
```

### トークン設定
- `SECRET_KEY`: JWT 署名用の秘密鍵（環境変数）
- `ALGORITHM`: JWT アルゴリズム（デフォルト: "HS256"）
- `ACCESS_TOKEN_EXPIRE_MINUTES`: トークン有効期限（環境変数で設定）

## OAuth2PasswordRequestForm

**使用箇所**: app/api/v1/account.py:57

| フィールド名 | 型 | 必須 | 説明 |
|------------|---|------|------|
| username | string | Yes | ユーザー名 |
| password | string | Yes | パスワード |
| client_id | string | Yes | テナントID として使用 |
| grant_type | string | No | "password"（デフォルト） |
| scope | string | No | スコープ（未使用） |

**注意**: OAuth2 標準の `client_id` フィールドをテナントID として流用

## セキュリティ考慮事項

1. **パスワード保護**
   - 平文パスワードは一切保存されない
   - bcrypt によるソルト付きハッシュ化（app/dependencies/auth.py:58-68）
   - レスポンスでは "*****" でマスク

2. **テナント分離**
   - データベースレベルで完全分離
   - クロステナントアクセス不可
   - 各操作でテナントID を検証

3. **監査ログ**
   - 全てのリクエストを request_log に記録
   - 不正アクセスの追跡が可能

4. **JWT セキュリティ**
   - ステートレス認証
   - 署名付きトークン
   - 有効期限の自動チェック

## データベースセットアップ

**実装ファイル**: app/database/database_setup.py:101-118

**セットアップ手順**:
1. 新規テナント作成時に `execute()` 関数が呼ばれる
2. 必要なコレクションが作成される
   - `create_user_account_collection()`: user_accounts コレクション
   - `create_request_log_collection()`: request_log コレクション
3. インデックスが自動的に設定される

## 注意事項

1. **_id フィールド**: MongoDB の自動生成 ObjectId を使用
2. **大文字小文字**: ユーザー名は大文字小文字を区別
3. **削除フラグ**: 論理削除は実装されていない（`is_active` で管理）
4. **更新履歴**: `updated_at` は手動更新が必要
5. **トランザクション**: 現在未実装
6. **パスワード変更機能**: 現在未実装
7. **マイグレーション**: 専用のマイグレーションツールは未実装