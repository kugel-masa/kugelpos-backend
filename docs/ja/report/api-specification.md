# レポートサービスAPI仕様

## 概要

レポートサービスは、Kugelpos POSシステムの売上レポートと分析APIを提供します。日次・期間レポートの生成、リアルタイムKPI追跡、スケジュール実行、レポート配信を処理し、包括的なビジネスインテリジェンス機能を実現します。

## ベースURL
- ローカル環境: `http://localhost:8004`
- 本番環境: `https://report.{domain}`

## 認証

レポートサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークン取得元: アカウントサービスの `/api/v1/accounts/token`
- 管理操作とレポート生成に必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}_{store_code}_{terminal_no}`
- 端末からの基本レポートアクセスに使用

## フィールド形式

すべてのAPIリクエストとレスポンスは**camelCase**フィールド命名規則を使用します。サービスは`BaseSchemaModel`とトランスフォーマーを使用して、内部のsnake_caseと外部のcamelCase形式を自動的に変換します。

## 共通レスポンス形式

すべてのエンドポイントは以下の形式でレスポンスを返します：

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": { ... },
  "operation": "function_name"
}
```

## レポートタイプ

標準的なレポートタイプ：

| タイプID | 名称 | 説明 |
|----------|------|------|
| daily_sales | 日次売上レポート | 日別の売上集計 |
| payment_summary | 決済方法別集計 | 決済方法ごとの利用状況 |
| product_sales | 商品売上分析 | 商品別売上ランキング |
| hourly_analysis | 時間帯分析 | 時間帯別売上パターン |
| staff_performance | スタッフ実績 | スタッフ別販売実績 |
| category_analysis | カテゴリー分析 | カテゴリー別売上 |
| monthly_summary | 月次サマリー | 月間業績総括 |
| custom | カスタムレポート | ユーザー定義レポート |

## APIエンドポイント

### レポート生成

#### 1. レポート生成
**POST** `/api/v1/tenants/{tenant_id}/reports/generate`

指定されたタイプとパラメータでレポートを生成します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**リクエストボディ:**
```json
{
  "reportType": "daily_sales",
  "parameters": {
    "storeCode": "STORE001",
    "businessDate": "20240101",
    "includeDetails": true
  },
  "format": "pdf",
  "async": false
}
```

**フィールド説明:**
- `reportType` (string, 必須): レポートタイプID
- `parameters` (object, 必須): レポート生成パラメータ
- `format` (string, デフォルト: "pdf"): 出力形式（pdf/excel/csv/json）
- `async` (boolean, デフォルト: false): 非同期生成フラグ

**共通パラメータ:**
- `storeCode` (string/array): 店舗コード（複数指定可）
- `businessDate` (string): ビジネス日付（YYYYMMDD）
- `dateFrom` (string): 開始日
- `dateTo` (string): 終了日
- `includeDetails` (boolean): 詳細データ含有

**リクエスト例:**
```bash
curl -X POST "http://localhost:8004/api/v1/tenants/tenant001/reports/generate" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "reportType": "daily_sales",
    "parameters": {
      "storeCode": "STORE001",
      "businessDate": "20240101"
    },
    "format": "pdf"
  }'
```

**同期レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レポートが生成されました",
  "data": {
    "reportId": "rpt_20240101_001",
    "reportType": "daily_sales",
    "status": "completed",
    "createdAt": "2024-01-02T01:00:00Z",
    "fileUrl": "/api/v1/reports/rpt_20240101_001/download",
    "expiresAt": "2024-01-09T01:00:00Z",
    "metadata": {
      "pageCount": 5,
      "fileSize": 1048576,
      "format": "pdf"
    }
  },
  "operation": "generate_report"
}
```

**非同期レスポンス例:**
```json
{
  "success": true,
  "code": 202,
  "message": "レポート生成を開始しました",
  "data": {
    "reportId": "rpt_20240101_002",
    "status": "processing",
    "estimatedTime": 30,
    "statusUrl": "/api/v1/reports/rpt_20240101_002/status"
  },
  "operation": "generate_report_async"
}
```

#### 2. レポート取得
**GET** `/api/v1/tenants/{tenant_id}/reports/{report_id}`

生成済みレポートの情報を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `report_id` (string, 必須): レポートID

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レポート情報を取得しました",
  "data": {
    "reportId": "rpt_20240101_001",
    "reportType": "daily_sales",
    "reportName": "日次売上レポート - 2024年1月1日",
    "status": "completed",
    "parameters": {
      "storeCode": "STORE001",
      "businessDate": "20240101"
    },
    "format": "pdf",
    "createdAt": "2024-01-02T01:00:00Z",
    "completedAt": "2024-01-02T01:00:30Z",
    "fileUrl": "/api/v1/reports/rpt_20240101_001/download",
    "expiresAt": "2024-01-09T01:00:00Z",
    "createdBy": "user001",
    "summary": {
      "totalSales": 125000.00,
      "transactionCount": 150,
      "averageTicket": 833.33
    }
  },
  "operation": "get_report"
}
```

#### 3. レポートダウンロード
**GET** `/api/v1/tenants/{tenant_id}/reports/{report_id}/download`

レポートファイルをダウンロードします。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `report_id` (string, 必須): レポートID

**レスポンス:**
- Content-Type: application/pdf（またはレポート形式に応じる）
- Content-Disposition: attachment; filename="report_20240101.pdf"
- バイナリファイルデータ

#### 4. レポート一覧取得
**GET** `/api/v1/tenants/{tenant_id}/reports`

レポートの一覧を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `reportType` (string, オプション): レポートタイプでフィルタ
- `storeCode` (string, オプション): 店舗コードでフィルタ
- `dateFrom` (string, オプション): 作成日開始
- `dateTo` (string, オプション): 作成日終了
- `status` (string, オプション): ステータスでフィルタ
- `skip` (integer, デフォルト: 0): ページネーションオフセット
- `limit` (integer, デフォルト: 20, 最大: 100): ページサイズ
- `sort` (string, デフォルト: "createdAt:-1"): ソート順（フィールド名:1 昇順、フィールド名:-1 降順）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レポート一覧を取得しました",
  "data": {
    "items": [
      {
        "reportId": "rpt_20240101_001",
        "reportType": "daily_sales",
        "reportName": "日次売上レポート - 20240101",
        "status": "completed",
        "format": "pdf",
        "createdAt": "2024-01-02T01:00:00Z",
        "fileSize": 1048576,
        "storeCode": "STORE001"
      }
    ],
    "total": 150,
    "skip": 0,
    "limit": 20
  },
  "operation": "list_reports"
}
```

### レポートタイプ管理

#### 5. 利用可能なレポートタイプ取得
**GET** `/api/v1/reports/types`

利用可能なレポートタイプの一覧を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レポートタイプ一覧を取得しました",
  "data": {
    "items": [
      {
        "typeId": "daily_sales",
        "name": "日次売上レポート",
        "description": "日別の売上、取引数、決済方法別集計",
        "category": "sales",
        "parameters": [
          {
            "name": "storeCode",
            "type": "string",
            "required": true,
            "description": "店舗コード"
          },
          {
            "name": "businessDate",
            "type": "date",
            "required": true,
            "description": "ビジネス日付"
          }
        ],
        "formats": ["pdf", "excel", "csv"],
        "estimatedTime": 30,
        "sample": "/api/v1/reports/types/daily_sales/sample"
      }
    ]
  },
  "operation": "list_report_types"
}
```

### スケジュール管理

#### 6. スケジュール作成
**POST** `/api/v1/tenants/{tenant_id}/schedules`

レポートの自動生成スケジュールを作成します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**リクエストボディ:**
```json
{
  "name": "日次売上レポート自動生成",
  "reportType": "daily_sales",
  "parameters": {
    "storeCode": ["STORE001", "STORE002"],
    "includeDetails": true
  },
  "schedule": {
    "type": "cron",
    "expression": "0 1 * * *",
    "timezone": "Asia/Tokyo"
  },
  "delivery": {
    "email": {
      "enabled": true,
      "recipients": ["manager@example.com"],
      "subject": "日次売上レポート - {date}"
    },
    "storage": {
      "enabled": true,
      "provider": "google_drive",
      "folder": "/reports/daily"
    }
  },
  "format": "pdf",
  "isActive": true
}
```

**フィールド説明:**
- `name` (string, 必須): スケジュール名
- `reportType` (string, 必須): レポートタイプ
- `parameters` (object, 必須): レポートパラメータ
- `schedule` (object, 必須): スケジュール設定
  - `type` (string): "cron" または "interval"
  - `expression` (string): Cron式（cronタイプ）
  - `interval` (integer): 間隔（分）（intervalタイプ）
  - `timezone` (string): タイムゾーン
- `delivery` (object, オプション): 配信設定
- `format` (string): 出力形式
- `isActive` (boolean): 有効/無効

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "スケジュールが作成されました",
  "data": {
    "scheduleId": "sch_001",
    "name": "日次売上レポート自動生成",
    "nextRun": "2024-01-02T01:00:00Z",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_schedule"
}
```

#### 7. スケジュール一覧取得
**GET** `/api/v1/tenants/{tenant_id}/schedules`

スケジュールの一覧を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `isActive` (boolean, オプション): アクティブ状態でフィルタ
- `reportType` (string, オプション): レポートタイプでフィルタ

#### 8. スケジュール更新
**PUT** `/api/v1/tenants/{tenant_id}/schedules/{schedule_id}`

既存のスケジュールを更新します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `schedule_id` (string, 必須): スケジュールID

#### 9. スケジュール削除
**DELETE** `/api/v1/tenants/{tenant_id}/schedules/{schedule_id}`

スケジュールを削除します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `schedule_id` (string, 必須): スケジュールID

### レポート配信

#### 10. レポート送信
**POST** `/api/v1/tenants/{tenant_id}/reports/{report_id}/send`

生成済みレポートを送信します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `report_id` (string, 必須): レポートID

**リクエストボディ:**
```json
{
  "method": "email",
  "recipients": ["user@example.com"],
  "subject": "売上レポート",
  "message": "本日の売上レポートを送付します。"
}
```

**フィールド説明:**
- `method` (string, 必須): 送信方法（email/webhook）
- `recipients` (array[string], 必須): 送信先
- `subject` (string, email時必須): 件名
- `message` (string, オプション): メッセージ

### リアルタイムデータ

#### 11. 現在のKPI取得
**GET** `/api/v1/tenants/{tenant_id}/kpi/current`

現在のKPI値を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `storeCode` (string, 必須): 店舗コード
- `metrics` (string, オプション): 取得する指標（カンマ区切り）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "KPIデータを取得しました",
  "data": {
    "timestamp": "2024-01-01T15:30:00Z",
    "storeCode": "STORE001",
    "metrics": {
      "todaySales": 75000.00,
      "transactionCount": 89,
      "averageTicket": 842.70,
      "itemsSold": 215,
      "customerCount": 85,
      "conversionRate": 95.5,
      "targetAchievement": 75.0,
      "hourlyTrend": [
        {"hour": 9, "sales": 5000},
        {"hour": 10, "sales": 8000},
        {"hour": 11, "sales": 12000}
      ]
    }
  },
  "operation": "get_current_kpi"
}
```

#### 12. WebSocketダッシュボード接続
**WebSocket** `/ws/dashboard`

リアルタイムダッシュボードデータのWebSocket接続。

**接続パラメータ:**
- `token` (string, 必須): JWTトークン
- `tenant_id` (string, 必須): テナントID
- `store_code` (string, 必須): 店舗コード

**メッセージ形式:**
```json
{
  "type": "kpi_update",
  "data": {
    "timestamp": "2024-01-01T15:30:00Z",
    "sales": 75000.00,
    "transactions": 89
  }
}
```

### データエクスポート

#### 13. 一括データエクスポート
**POST** `/api/v1/tenants/{tenant_id}/export`

指定条件でデータを一括エクスポートします。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**リクエストボディ:**
```json
{
  "dataType": "transactions",
  "dateFrom": "2024-01-01",
  "dateTo": "2024-01-31",
  "storeCode": ["STORE001", "STORE002"],
  "format": "csv",
  "compression": "zip"
}
```

**フィールド説明:**
- `dataType` (string, 必須): データタイプ（transactions/products/customers）
- `dateFrom` (string, 必須): 開始日
- `dateTo` (string, 必須): 終了日
- `storeCode` (array[string], オプション): 店舗コード
- `format` (string, 必須): 出力形式
- `compression` (string, オプション): 圧縮形式

### システムエンドポイント

#### 14. ヘルスチェック
**GET** `/health`

サービスヘルスと依存関係ステータスをチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8004/health"
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
    "cache": "connected",
    "scheduler": "running",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

## イベント受信（Dapr Pub/Sub）

### トランザクションログイベント
**トピック:** `tranlog_report`

取引データを受信してリアルタイム集計を更新：
```json
{
  "eventId": "evt_123456",
  "tenantId": "tenant001",
  "storeCode": "STORE001",
  "terminalNo": 1,
  "transactionNo": "0001",
  "transactionType": 101,
  "businessDate": "20240101",
  "amount": 990.00,
  "items": [...],
  "timestamp": "2024-01-01T10:15:00Z"
}
```

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "指定されたレポートが見つかりません",
  "data": null,
  "operation": "get_report"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `202` - 受理されました（非同期処理）
- `400` - 不正なリクエスト
- `401` - 認証失敗
- `403` - アクセス拒否
- `404` - リソースが見つかりません
- `500` - 内部サーバーエラー

### エラーコードシステム

レポートサービスは60XXX範囲のエラーコードを使用します：

- `60001` - レポートタイプが見つかりません
- `60002` - レポート生成エラー
- `60003` - データ不足エラー
- `60004` - 権限不足
- `60005` - スケジュール設定エラー
- `60006` - 配信エラー
- `60007` - テンプレートエラー
- `60008` - 集計エラー
- `60009` - エクスポートエラー
- `60099` - 一般的なサービスエラー

## レート制限

レポートサービスは以下のレート制限を実装しています：

- レポート生成: 1分あたり10リクエスト
- データエクスポート: 1時間あたり5リクエスト
- KPI取得: 1秒あたり10リクエスト
- 一般的なAPI: 1分あたり100リクエスト

## キャッシング

レポートデータは以下のようにキャッシュされます：

- 完了レポート: 7日間
- KPIデータ: 5分間
- 集計結果: 1時間
- レポートタイプ情報: 24時間

## 注意事項

1. **非同期処理**: 大きなレポートは非同期で生成
2. **ファイル有効期限**: 生成されたファイルは7日後に削除
3. **同時実行制限**: テナントあたり5つの同時レポート生成
4. **CamelCase規約**: すべてのJSONフィールドはcamelCase形式を使用
5. **タイムゾーン**: すべての日時はUTC（特に指定がない限り）
6. **データ保持**: 生レポートデータは90日間保持
7. **マルチテナント**: 完全なテナント分離を実施

レポートサービスは、Kugelpos POSシステムのビジネスインテリジェンス機能を提供し、データ駆動型の意思決定と業績管理を支援します。