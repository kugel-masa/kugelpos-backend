# ターミナルサービス API仕様

## 概要

ターミナルサービスは、Kugelpos POSシステムのテナント管理、店舗管理、端末管理機能を提供します。端末のライフサイクル管理、現金入出金操作、スタッフ管理、および店舗運営に必要な基本機能を実装しています。

## ベースURL
- ローカル環境: `http://localhost:8001`
- 本番環境: `https://terminal.{domain}`

## 認証

ターミナルサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるテナント・店舗・端末管理操作

### 2. 端末ID + APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- クエリパラメータ: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- 用途: 端末による操作（サインイン、開店、現金管理等）

## フィールド形式

すべてのAPIリクエスト/レスポンスは**camelCase**形式を使用します。

## 共通レスポンス形式

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": { ... },
  "operation": "function_name"
}
```

## 端末状態

| 状態 | 説明 |
|------|------|
| idle | 初期状態、営業開始前 |
| opened | 営業中（開店済み） |
| closed | 営業終了（閉店済み） |

## ファンクションモード

| モード | 説明 |
|--------|------|
| MainMenu | メインメニュー |
| OpenTerminal | 端末開店 |
| Sales | 販売処理 |
| Returns | 返品処理 |
| Void | 取消処理 |
| Reports | レポート表示 |
| CloseTerminal | 端末閉店 |
| Journal | ジャーナル表示 |
| Maintenance | メンテナンス |
| CashInOut | 現金入出金 |

## APIエンドポイント

### テナント管理

#### 1. テナント作成
**POST** `/api/v1/tenants`

新規テナントを作成し、各サービスを初期化します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "tenantId": "tenant001",
  "tenantName": "株式会社サンプル"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "Tenant created successfully",
  "data": {
    "tenantId": "tenant001",
    "tenantName": "株式会社サンプル",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_tenant"
}
```

#### 2. テナント情報取得
**GET** `/api/v1/tenants/{tenant_id}`

テナントの詳細情報を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

#### 3. テナント更新
**PUT** `/api/v1/tenants/{tenant_id}`

テナント情報を更新します。

**リクエストボディ:**
```json
{
  "tenantName": "株式会社サンプル（更新）"
}
```

#### 4. テナント削除
**DELETE** `/api/v1/tenants/{tenant_id}`

テナントと関連データを削除します。

### 店舗管理

#### 5. 店舗追加
**POST** `/api/v1/tenants/{tenant_id}/stores`

テナントに新規店舗を追加します。

**リクエストボディ:**
```json
{
  "storeCode": "STORE001",
  "storeName": "本店"
}
```

#### 6. 店舗一覧取得
**GET** `/api/v1/tenants/{tenant_id}/stores`

テナントの店舗一覧を取得します。

**クエリパラメータ:**
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100): ページサイズ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stores retrieved successfully",
  "data": {
    "stores": [
      {
        "storeCode": "STORE001",
        "storeName": "本店",
        "status": "active",
        "businessDate": "2024-01-01",
        "createdAt": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 100
  },
  "operation": "list_stores"
}
```

#### 7. 店舗情報取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

特定店舗の詳細情報を取得します。

#### 8. 店舗更新
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

店舗情報を更新します。

**リクエストボディ:**
```json
{
  "storeName": "本店（更新）",
  "status": "active",
  "businessDate": "2024-01-02"
}
```

#### 9. 店舗削除
**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

店舗を削除します。

### 端末管理

#### 10. 端末作成
**POST** `/api/v1/terminals`

新規端末を作成します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "storeCode": "STORE001",
  "terminalNo": 1,
  "description": "レジ1号機"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "Terminal created successfully",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "terminalNo": 1,
    "description": "レジ1号機",
    "status": "idle",
    "apiKey": "sk_live_1234567890abcdef",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_terminal"
}
```

#### 11. 端末一覧取得
**GET** `/api/v1/terminals`

端末一覧を取得します。

**認証:** JWTトークンが必要

**クエリパラメータ:**
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100): ページサイズ
- `store_code` (string): 店舗コードでフィルタ
- `status` (string): 状態でフィルタ

#### 12. 端末情報取得
**GET** `/api/v1/terminals/{terminal_id}`

端末の詳細情報を取得します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID（形式: tenant_id-store_code-terminal_no）

#### 13. 端末削除
**DELETE** `/api/v1/terminals/{terminal_id}`

端末を削除します。

**認証:** JWTトークンが必要

#### 14. 端末説明更新
**PATCH** `/api/v1/terminals/{terminal_id}/description`

端末の説明を更新します。

**リクエストボディ:**
```json
{
  "description": "レジ1号機（メンテナンス済み）"
}
```

#### 15. ファンクションモード更新
**PATCH** `/api/v1/terminals/{terminal_id}/function_mode`

端末のファンクションモードを更新します。

**リクエストボディ:**
```json
{
  "functionMode": "Sales"
}
```

### 端末操作

#### 16. スタッフサインイン
**POST** `/api/v1/terminals/{terminal_id}/sign-in`

スタッフが端末にサインインします。

**リクエストボディ:**
```json
{
  "staffId": "STAFF001",
  "staffName": "山田太郎"
}
```

#### 17. スタッフサインアウト
**POST** `/api/v1/terminals/{terminal_id}/sign-out`

スタッフが端末からサインアウトします。

**リクエストボディ:**
```json
{
  "staffId": "STAFF001"
}
```

#### 18. 端末開店
**POST** `/api/v1/terminals/{terminal_id}/open`

端末を開店状態にします。

**リクエストボディ:**
```json
{
  "staffId": "STAFF001",
  "staffName": "山田太郎",
  "cashAmount": 50000
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminal opened successfully",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "status": "opened",
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "openTime": "2024-01-01T09:00:00Z",
    "receiptText": "=== 開店 ===\n...",
    "journalText": "開店処理\n..."
  },
  "operation": "open_terminal"
}
```

#### 19. 端末閉店
**POST** `/api/v1/terminals/{terminal_id}/close`

端末を閉店状態にします。

**リクエストボディ:**
```json
{
  "staffId": "STAFF001",
  "staffName": "山田太郎",
  "cashAmount": 125000
}
```

### 現金管理

#### 20. 現金入金
**POST** `/api/v1/terminals/{terminal_id}/cash-in`

現金を入金します。

**リクエストボディ:**
```json
{
  "amount": 10000,
  "reason": "釣銭補充",
  "staffId": "STAFF001",
  "staffName": "山田太郎",
  "comment": "午後の釣銭補充"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Cash in completed successfully",
  "data": {
    "cashInOutId": "CI-20240101-001",
    "amount": 10000,
    "receiptText": "=== 現金入金 ===\n...",
    "journalText": "現金入金処理\n..."
  },
  "operation": "cash_in"
}
```

#### 21. 現金出金
**POST** `/api/v1/terminals/{terminal_id}/cash-out`

現金を出金します。

**リクエストボディ:**
```json
{
  "amount": 50000,
  "reason": "売上金回収",
  "staffId": "STAFF001",
  "staffName": "山田太郎",
  "comment": "中間回収"
}
```

### システム管理

#### 22. 配信ステータス更新
**POST** `/api/v1/terminals/{terminal_id}/delivery-status`

イベント配信ステータスを更新します（内部使用）。

**リクエストボディ:**
```json
{
  "eventId": "evt_123456",
  "eventType": "cashlog",
  "delivered": true
}
```

### 23. ヘルスチェック
**GET** `/health`

サービスの健全性を確認します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "サービスは正常です",
  "data": {
    "status": "healthy",
    "mongodb": "connected"
  },
  "operation": "health_check"
}
```

## イベント通知（Dapr Pub/Sub）

### 現金入出金イベント
**トピック:** `cashlog_report`

現金入出金時に発行されるイベント。

### 開閉店イベント
**トピック:** `opencloselog_report`

端末の開閉店時に発行されるイベント。

## エラーコード

ターミナルサービスは20XXX範囲のエラーコードを使用します：

- `20001`: テナントが見つかりません
- `20002`: 店舗が見つかりません
- `20003`: 端末が見つかりません
- `20004`: 端末が既に存在します
- `20005`: 無効な端末状態
- `20006`: スタッフが見つかりません
- `20007`: APIキーが無効です
- `20008`: 端末が既に開店しています
- `20009`: 端末が開店していません
- `20099`: 一般的なサービスエラー

## 特記事項

1. **端末ID形式**: `{tenant_id}-{store_code}-{terminal_no}`形式を使用
2. **APIキー**: 端末作成時に自動生成され、ハッシュ化して保存
3. **バックグラウンドジョブ**: 未配信メッセージの再送信を定期的に実行
4. **マルチテナント**: データベースレベルでの完全分離
5. **イベント駆動**: Dapr pub/subによる非同期イベント配信
6. **サーキットブレーカー**: 外部サービス呼び出しの障害対応