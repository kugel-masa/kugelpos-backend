# ターミナルサービス モデル仕様

## 概要

ターミナルサービスのデータモデル仕様書です。MongoDBのコレクション構造、スキーマ定義、およびデータフローについて説明します。

## データベース設計

### データベース名
- `{tenant_id}_terminal` (例: `tenant001_terminal`)

### コレクション一覧

| コレクション名 | 用途 | 主なデータ |
|---------------|------|------------|
| info_tenant | テナント情報 | テナントと店舗の基本情報 |
| info_terminal | 端末情報 | 端末の詳細と状態管理 |
| log_cash_in_out | 現金入出金ログ | 現金操作の記録 |
| log_open_close | 開閉店ログ | 端末の開閉店記録 |
| status_terminal_delivery | 配信ステータス | イベント配信の追跡 |

**注:** コレクション名は `{種類}_{対象}` のパターンで統一されています（info_*, log_*, status_*）。

## 詳細スキーマ定義

### 1. info_tenant コレクション

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

### 2. info_terminal コレクション

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
  "api_key_hash": "string (SHA-256 16進)",
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
- `api_key_hash`: 端末のAPIキーのSHA-256ダイジェスト。キーそのものは保存しない（ハッシュ化済みのレコードには `api_key` がない）

### 3. log_cash_in_out コレクション

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

### 4. log_open_close コレクション

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

### 5. status_terminal_delivery コレクション

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

### info_tenant
- ユニークインデックス: `tenant_id`

### info_terminal
- ユニークインデックス: `terminal_id`
- ユニーク複合インデックス: `tenant_id + store_code + terminal_no`
- インデックス: `api_key_hash`（部分インデックス: 文字列のときだけ）

### log_cash_in_out
- ユニーク複合インデックス: `tenant_id + store_code + terminal_no + generate_date_time`
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + open_counter`

### log_open_close
- ユニーク複合インデックス: `tenant_id + store_code + terminal_no + business_counter + operation`（1 つの営業に開局と閉局が 1 件ずつ。`business_counter` は端末を登録し直しても引き継がれ、使い回されない。以前のキー `business_date + open_counter + operation` は `POST /api/v1/tenants` で入れ替わる）

### status_terminal_delivery
- ユニークインデックス: `event_id`
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + open_counter`
- 複合インデックス: `status + published_at`

## 列挙型定義

### 端末状態（TerminalStatus）
- `Idle`: 初期状態、営業開始前
- `Opened`: 営業中（開店済み）
- `Closed`: 営業終了（閉店済み）

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
2. **APIキー生成**: 自動生成し、ダイジェストだけを保存する。キーは作成時のレスポンスで1回だけ返す
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
- 32バイトのセキュアランダム生成（`secrets.token_urlsafe(32)`）
- `api_key_hash` にSHA-256ダイジェストだけを保存し、定数時間で照合する。256ビットの乱数なので遅いハッシュは不要で、塩なしのダイジェストならインデックスで検索できる（`terminal_id` なしの `POST /auth/token`）
- キーを読めるのは発行したレスポンスだけ: `POST /terminals` と `POST /terminals/{terminal_id}/api-key`。`GET /terminals/{terminal_id}` は常にマスクして返し、`include_api_key` パラメータは非推奨で無視される
- 紛失・漏洩したキーは取り出せないので再発行する: `POST /terminals/{terminal_id}/api-key`（ユーザーJWTのみ）が新しいキーを発行し、古いキーはその時点で無効になる。古いキーで取得済みの端末JWTは失効しない。各サービスがその場で検証するため、有効期限（`TERMINAL_TOKEN_EXPIRE_HOURS`、既定24時間）まで使える
- ダイジェスト導入前のレコードは `api_key` に平文を持つ。そのまま使え、キーの照合時と、テナントセットアップ（起動時に既存テナントにも実行）でハッシュ化される（ダイジェストを書き、平文を消す）
- ハッシュ化は一方向。ダイジェスト導入前の terminal サービスはハッシュ化済みのキーを照合できず、その書き込みで `api_key_hash` が消えて端末が認証できなくなる。旧リビジョンを新リビジョンと並べて動かさず、切り替えること。切り戻しの余地を残すなら `SEAL_LEGACY_TERMINAL_API_KEYS=false` にする（キーの照合は行われ、既存レコードはそのまま残る）。旧リビジョンがなくなってから有効にする。既定値は `true` なので、指定せずにデプロイすると最初の起動で既存のキーがすべてハッシュ化され、それらの端末は切り戻せない
- ハッシュ化を止めていても、アップグレード後に作成・再発行した端末はダイジェストしか持たない。切り戻すと認証できず、旧リビジョンにはキーを発行し直す手段がない。新リビジョンに戻すか、端末を削除して作り直す（カウンタや状態は失われる）
- キーが変わるのは作成・再発行・ハッシュ化のときだけ。サインイン・サインアウト・開店・閉店の書き込みは `api_key` と `api_key_hash` を書かないので、処理中に走った再発行を取り消さない
- terminal サービス自身が他サービスを呼ぶときは、APIキーではなく自分で発行した短命の端末JWTを使う

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