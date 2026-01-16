# ターミナルサービス モデル仕様

## 概要

ターミナルサービスのデータモデル仕様書です。MongoDBのコレクション構造、スキーマ定義、およびデータフローについて説明します。

## データベース設計

### データベース名
- `{tenant_id}_terminal` (例: `tenant001_terminal`)

### コレクション一覧

| コレクション名 | 用途 | 主なデータ |
|---------------|------|------------|
| tenant_info | テナント情報 | テナントと店舗の基本情報 |
| terminal_info | 端末情報 | 端末の詳細と状態管理 |
| cash_in_out_log | 現金入出金ログ | 現金操作の記録 |
| open_close_log | 開閉店ログ | 端末の開閉店記録 |
| terminallog_delivery_status | 配信ステータス | イベント配信の追跡 |

## 詳細スキーマ定義

### 1. tenant_info コレクション

テナントと店舗情報を管理するコレクション。店舗は埋め込みドキュメントとして保存。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "tenant_name": "string",
  "stores": [
    {
      "store_code": "string",
      "store_name": "string",
      "status": "string (active/inactive)",
      "business_date": "string (YYYYMMDD)",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 2. terminal_info コレクション

端末の詳細情報と現在状態を管理するコレクション。

```json
{
  "_id": "ObjectId",
  "terminal_id": "string (tenant_id-store_code-terminal_no)",
  "tenant_id": "string",
  "store_code": "string",
  "terminal_no": "integer (1-999)",
  "description": "string",
  "function_mode": "string (MainMenu/Sales/etc)",
  "status": "string (idle/opened/closed)",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "staff": {
    "staff_id": "string",
    "staff_name": "string"
  },
  "initial_amount": "decimal",
  "physical_amount": "decimal",
  "api_key": "string (hashed)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `terminal_id`: 端末の一意識別子（形式: tenant_id-store_code-terminal_no）
- `function_mode`: 現在のファンクションモード
- `status`: 端末の営業状態
- `open_counter`: 開店回数カウンター
- `business_counter`: ビジネス操作カウンター
- `api_key`: 端末認証用APIキー（SHA-256ハッシュ化）

### 3. cash_in_out_log コレクション

現金入出金操作の履歴を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "amount": "float (正: 入金, 負: 出金)",
  "description": "string (入出金の理由・説明)",
  "receipt_text": "string",
  "journal_text": "string",
  "generate_date_time": "string (ISO 8601)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `amount`: 入金の場合は正の値、出金の場合は負の値
- `description`: 入出金の理由や説明（旧フィールド名: reason/comment）

### 4. open_close_log コレクション

端末の開閉店操作の履歴を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "operation": "string (open/close)",
  "generate_date_time": "string (ISO 8601)",
  "terminal_info": {
    "/* 端末情報のスナップショット */"
  },
  "cart_transaction_count": "integer",
  "cart_transaction_last_no": "integer",
  "cash_in_out_count": "integer",
  "cash_in_out_last_datetime": "string",
  "receipt_text": "string",
  "journal_text": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 5. terminallog_delivery_status コレクション

イベント配信の状態を追跡するコレクション。

```json
{
  "_id": "ObjectId",
  "event_id": "string (UUID)",
  "published_at": "datetime",
  "status": "string (published/delivered/partially_delivered/failed)",
  "tenant_id": "string",
  "store_code": "string",
  "terminal_no": "integer",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "payload": {
    "/* イベントペイロード */"
  },
  "services": [
    {
      "service_name": "string",
      "received_at": "datetime (optional)",
      "status": "string (pending/received/failed)",
      "message": "string (optional, エラーメッセージ等)"
    }
  ],
  "last_updated_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `status`: 全体の配信状態（published → delivered/partially_delivered/failed）
- `services[].status`: 各サービスへの配信状態（pending → received/failed）
- `services[].received_at`: サービスがメッセージを受信した日時
- `services[].message`: エラー発生時のメッセージ

## インデックス定義

### tenant_info
- ユニークインデックス: `tenant_id`

### terminal_info
- ユニークインデックス: `terminal_id`
- 複合インデックス: `tenant_id + store_code + terminal_no`
- 単一インデックス: `api_key`

### cash_in_out_log
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date`
- 単一インデックス: `generate_date_time`

### open_close_log
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + operation`
- 単一インデックス: `generate_date_time`

### terminallog_delivery_status
- ユニークインデックス: `event_id`
- 複合インデックス: `tenant_id + status + published_at`

## 列挙型定義

### 端末状態（TerminalStatus）
- `idle`: 初期状態、営業開始前
- `opened`: 営業中（開店済み）
- `closed`: 営業終了（閉店済み）

### ファンクションモード（FunctionMode）
- `MainMenu`: メインメニュー
- `OpenTerminal`: 端末開店
- `Sales`: 販売処理
- `Returns`: 返品処理
- `Void`: 取消処理
- `Reports`: レポート表示
- `CloseTerminal`: 端末閉店
- `Journal`: ジャーナル表示
- `Maintenance`: メンテナンス
- `CashInOut`: 現金入出金

### 店舗状態（StoreStatus）
- `active`: 営業中
- `inactive`: 非営業

### 配信状態（DeliveryStatus）
- `published`: イベント発行済み
- `delivered`: 配信完了
- `partially_delivered`: 部分配信
- `failed`: 配信失敗

## データフロー

### 端末ライフサイクル
1. **端末作成**: テナント・店舗・端末番号を指定して作成
2. **APIキー生成**: 自動生成されハッシュ化して保存
3. **スタッフサインイン**: スタッフ情報を端末に紐付け
4. **開店処理**: 営業開始、初期現金設定
5. **日中操作**: 現金入出金、販売処理
6. **閉店処理**: 営業終了、現金確認
7. **ビジネス日付更新**: 次営業日への切り替え

### イベント配信フロー
1. **イベント生成**: 開閉店、現金操作時にイベント生成
2. **Dapr Pub/Sub**: 非同期でイベントを発行
3. **配信追跡**: delivery_statusで配信状態を管理
4. **再送制御**: 未配信イベントのバックグラウンド再送

### マルチテナント構造
```
テナント
├── 店舗（埋め込み）
└── 端末（別コレクション）
    ├── 現金入出金ログ
    └── 開閉店ログ
```

## セキュリティ

### APIキー管理
- 32バイトのセキュアランダム生成
- SHA-256でハッシュ化して保存
- 端末認証に使用

### データ分離
- テナント単位でデータベース分離
- すべての操作でテナントID検証
- クロステナントアクセス防止

## 特記事項

1. **端末ID形式**: `{tenant_id}-{store_code}-{terminal_no}`で統一
2. **店舗コード正規化**: 大文字に自動変換（store001 → STORE001）
3. **バックグラウンドジョブ**: 未配信イベントの定期的な再送処理
4. **監査証跡**: すべての操作をタイムスタンプ付きで記録
5. **サーキットブレーカー**: 外部サービス呼び出しの障害対応
6. **イベント駆動**: Dapr pub/subによる疎結合な連携