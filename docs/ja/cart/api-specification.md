# Cart Service API 仕様書

## 概要

Cart サービスは、ショッピングカートとトランザクション処理を管理するマイクロサービスです。ステートマシンパターンによるカート状態管理、商品操作、決済処理、プラグイン可能な拡張機能を提供します。

## サービス情報

- **ポート**: 8003
- **フレームワーク**: FastAPI
- **認証方式**: API キー認証
- **データベース**: MongoDB (Motor 非同期ドライバー)
- **状態管理**: ステートマシンパターン
- **プラグインシステム**: 決済・販促・レシートデータ

## API エンドポイント

### 1. ルートエンドポイント

**パス**: `/`  
**メソッド**: GET  
**認証**: 不要  
**説明**: サービスの稼働確認用エンドポイント

**レスポンス**:
```json
{
  "message": "Welcome to Kugel-POS Cart API. supoorted version: v1"
}
```

**実装ファイル**: app/main.py:68-76

### 2. ヘルスチェック

**パス**: `/health`  
**メソッド**: GET  
**認証**: 不要  
**説明**: サービスの健全性と依存関係の状態を確認

**レスポンスモデル**: `HealthCheckResponse`
```json
{
  "status": "healthy",
  "service": "cart",
  "version": "1.0.0",
  "checks": {
    "mongodb": {
      "status": "healthy",
      "details": {}
    },
    "dapr_sidecar": {
      "status": "healthy",
      "details": {}
    },
    "dapr_cartstore": {
      "status": "healthy",
      "details": {}
    },
    "dapr_pubsub_tranlog": {
      "status": "healthy",
      "details": {}
    },
    "background_jobs": {
      "status": "healthy",
      "details": {
        "scheduler_running": true,
        "job_count": 1,
        "job_names": ["republish_undelivered_tranlog"]
      }
    }
  }
}
```

**実装ファイル**: app/main.py:79-137

## Cart API (/api/v1/carts)

### 3. カート作成

**パス**: `/api/v1/carts`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 新規ショッピングカートを作成

**リクエストモデル**: `CartCreateRequest`
```json
{
  "transactionType": "standard",
  "userId": "STF001",
  "userName": "山田太郎"
}
```

**レスポンスモデル**: `ApiResponse[CartCreateResponse]`
```json
{
  "success": true,
  "code": 201,
  "message": "Cart Created. cart_id: cart_20250105_001",
  "data": {
    "cartId": "cart_20250105_001"
  },
  "operation": "create_cart"
}
```

**エラーレスポンス**:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 422: Unprocessable Entity
- 500: Internal Server Error

**実装詳細** (app/api/v1/cart.py:32-82):
- terminal_id は依存性注入で取得
- カート作成時に初期状態は "idle"
- ユーザー情報はオプション

### 4. カート取得

**パス**: `/api/v1/carts/{cart_id}`  
**メソッド**: GET  
**認証**: 必須（API キー）  
**説明**: カートの詳細情報を取得

**パスパラメータ**:
- `cart_id`: string - カートID

**レスポンスモデル**: `ApiResponse[Cart]`
```json
{
  "success": true,
  "code": 200,
  "message": "Cart found. cart_id: cart_20250105_001",
  "data": {
    "cartId": "cart_20250105_001",
    "status": "entering_item",
    "terminalId": "A1234-STORE01-1",
    "lineItems": [...],
    "subtotalAmount": 1000.0,
    "taxAmount": 100.0,
    "totalAmount": 1100.0,
    "balanceAmount": 1100.0
  },
  "operation": "get_cart"
}
```

**実装詳細** (app/api/v1/cart.py:84-128):
- SchemasTransformerV1 でモデル変換

### 5. カートキャンセル

**パス**: `/api/v1/carts/{cart_id}/cancel`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カートをキャンセル状態に遷移

**実装詳細** (app/api/v1/cart.py:131-172):
- 任意の状態からキャンセル可能
- キャンセル後は操作不可

### 6. 商品追加

**パス**: `/api/v1/carts/{cart_id}/lineItems`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カートに商品を追加

**リクエストモデル**: `list[Item]`
```json
[
  {
    "barcode": "4901234567890",
    "quantity": 2.0,
    "unitPrice": 100.0
  }
]
```

**実装詳細** (app/api/v1/cart.py:175-220):
- 複数商品の一括追加可能
- idle 状態から entering_item 状態へ自動遷移

### 7. 商品キャンセル

**パス**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/cancel`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 特定の商品をキャンセル

**パスパラメータ**:
- `cart_id`: string - カートID
- `lineNo`: integer - 行番号（1から開始）

**実装詳細** (app/api/v1/cart.py:223-266):
- キャンセルフラグをセット（物理削除なし）

### 8. 単価更新

**パス**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/unitPrice`  
**メソッド**: PATCH  
**認証**: 必須（API キー）  
**説明**: 商品の単価を更新

**リクエストモデル**: `ItemUnitPriceUpdateRequest`
```json
{
  "unitPrice": 150.0
}
```

**実装詳細** (app/api/v1/cart.py:269-315):
- 価格変更後、自動的に再計算

### 9. 数量更新

**パス**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/quantity`  
**メソッド**: PATCH  
**認証**: 必須（API キー）  
**説明**: 商品の数量を更新

**リクエストモデル**: `ItemQuantityUpdateRequest`
```json
{
  "quantity": 3.0
}
```

**実装詳細** (app/api/v1/cart.py:318-364):
- 数量変更後、自動的に再計算

### 10. 商品割引追加

**パス**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/discounts`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 特定商品に割引を適用

**リクエストモデル**: `list[DiscountRequest]`
```json
[
  {
    "discountCode": "DISC10",
    "discountAmount": 50.0,
    "discountType": "amount"
  }
]
```

**実装詳細** (app/api/v1/cart.py:367-415):
- 複数割引の適用可能

### 11. 小計計算

**パス**: `/api/v1/carts/{cart_id}/subtotal`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カートの小計と税額を計算

**実装詳細** (app/api/v1/cart.py:418-459):
- 商品入力後の小計計算
- entering_item 状態から paying 状態へ遷移

### 12. カート割引追加

**パス**: `/api/v1/carts/{cart_id}/discounts`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カート全体に割引を適用

**リクエストモデル**: `list[DiscountRequest]`

**実装詳細** (app/api/v1/cart.py:462-508):
- カートレベルの割引適用

### 13. 支払い追加

**パス**: `/api/v1/carts/{cart_id}/payments`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カートに支払いを追加

**リクエストモデル**: `list[PaymentRequest]`
```json
[
  {
    "paymentCode": "01",
    "paymentAmount": 1100.0,
    "paymentDetails": {
      "tenderedAmount": 2000.0
    }
  }
]
```

**実装詳細** (app/api/v1/cart.py:511-556):
- 複数決済方法の併用可能
- プラグインシステムによる決済処理

### 14. 会計処理

**パス**: `/api/v1/carts/{cart_id}/bill`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: カートを完了状態にして取引を確定

**実装詳細** (app/api/v1/cart.py:559-601):
- paying 状態から completed 状態へ遷移
- トランザクションログの生成と発行
- レシートデータの生成

### 15. 商品入力再開

**パス**: `/api/v1/carts/{cart_id}/resume-item-entry`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 支払い状態から商品入力状態に戻る

**実装詳細** (app/api/v1/cart.py:604-646):
- paying 状態から entering_item 状態へ戻る
- 支払い情報をクリア

## Transaction API

### 16. 取引一覧取得

**パス**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`  
**メソッド**: GET  
**認証**: 必須（API キー）  
**説明**: 条件に合致する取引一覧を取得

**クエリパラメータ**:
- `business_date`: string (YYYYMMDD) - 営業日
- `open_counter`: integer - オープンカウンター
- `transaction_type`: list[integer] - 取引タイプ
- `receipt_no`: integer - レシート番号
- `limit`: integer (デフォルト: 100) - 取得件数
- `page`: integer (デフォルト: 1) - ページ番号
- `sort`: string - ソート条件（例: "transaction_no:-1"）
- `include_cancelled`: boolean (デフォルト: false) - キャンセル済み含む

**実装詳細** (app/api/v1/tran.py:207-292)

### 17. 取引詳細取得

**パス**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}`  
**メソッド**: GET  
**認証**: 必須（API キー）  
**説明**: 特定の取引の詳細情報を取得

**実装詳細** (app/api/v1/tran.py:295-357)

### 18. 取引取消

**パス**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 取引を取消処理

**リクエストモデル**: `list[PaymentRequest]` - 返金用の支払い方法

**実装詳細** (app/api/v1/tran.py:360-438):
- 同一端末からのみ取消可能
- 取消用の支払い処理が必要

### 19. 返品処理

**パス**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 取引の返品処理

**リクエストモデル**: `list[PaymentRequest]` - 返金用の支払い方法

**実装詳細** (app/api/v1/tran.py:441-516):
- 同一店舗内からのみ返品可能
- 返品用の新規取引を作成

### 20. 配信状態更新

**パス**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status`  
**メソッド**: POST  
**認証**: 必須（JWT または内部認証）  
**説明**: トランザクションログの配信状態を更新

**リクエストモデル**: `DeliveryStatusUpdateRequest`
```json
{
  "eventId": "evt_123456",
  "service": "journal",
  "status": "delivered",
  "message": "Successfully processed"
}
```

**実装詳細** (app/api/v1/tran.py:520-594):
- Pub/Sub 通知用エンドポイント
- サービス間通信で使用

## Tenant API

### 21. テナント作成

**パス**: `/api/v1/tenants`  
**メソッド**: POST  
**認証**: 必須（API キー）  
**説明**: 新規テナントのデータベースセットアップ

**実装ファイル**: app/api/v1/tenant.py

## Cache API

### 22. ターミナルステータス更新

**パス**: `/api/v1/cache/terminal/status`  
**メソッド**: PUT  
**認証**: 必須（API キー）  
**説明**: ターミナルキャッシュのステータスを更新

**実装ファイル**: app/api/v1/cache.py

### 23. ターミナルキャッシュクリア

**パス**: `/api/v1/cache/terminal`  
**メソッド**: DELETE  
**認証**: 必須（API キー）  
**説明**: ターミナルキャッシュをクリア

**実装ファイル**: app/api/v1/cache.py

## ステートマシン

### カート状態遷移

**実装ディレクトリ**: app/services/states/

1. **InitialState** → **IdleState**
   - カート作成時の初期遷移

2. **IdleState** → **EnteringItemState**
   - 最初の商品追加時

3. **EnteringItemState** → **PayingState**
   - 小計計算実行時

4. **PayingState** → **CompletedState**
   - 会計処理完了時

5. **PayingState** → **EnteringItemState**
   - 商品入力再開時

6. **任意の状態** → **CancelledState**
   - キャンセル処理時

## プラグインシステム

### 決済プラグイン

**実装ディレクトリ**: app/services/strategies/payments/

- **PaymentByCash** (ID: "01"): 現金決済
- **PaymentByCashless** (ID: "11"): キャッシュレス決済
- **PaymentByOthers** (ID: "12"): その他決済

### 販促プラグイン

**実装ディレクトリ**: app/services/strategies/sales_promotions/

- **SalesPromoSample** (ID: "101"): サンプル販促

### レシートデータプラグイン

**実装ディレクトリ**: app/services/strategies/receipt_data/

- **ReceiptDataSample** (ID: "default", "32"): レシートデータ生成

## 定期実行ジョブ

### 未配信メッセージ再送信

**実装ファイル**: app/cron/republish_undelivery_message.py

- **実行間隔**: 5分ごと
- **チェック期間**: 過去24時間
- **失敗判定**: 15分以上経過
- **対象**: 未配信のトランザクションログ

## イベント発行

### Dapr Pub/Sub トピック

1. **tranlog_report**: トランザクションログ（レポート用）
2. **tranlog_status**: トランザクションステータス更新
3. **cashlog_report**: 現金入出金ログ
4. **opencloselog_report**: 開局/閉局ログ

## エラーコード

Cart サービスでは以下のエラーコード体系を使用：
- **30XXYY**: Cart サービス固有のエラー
  - XX: 機能識別子
  - YY: 具体的なエラー番号

## ミドルウェア

**実装ファイル**: app/main.py

1. **CORS** (53-59行目): 全オリジンからのアクセスを許可
2. **リクエストログ** (62行目): 全HTTPリクエストをログ記録
3. **例外ハンドラー** (65行目): 統一されたエラーレスポンス形式

## データベース

### コレクション
- `carts`: カート情報
- `terminal_counter`: 端末カウンター
- `tranlog`: トランザクションログ
- `transaction_status`: トランザクションステータス

### キャッシュ
- Dapr State Store (cartstore) を使用
- ターミナル情報のキャッシュ（TTL: 300秒）

## 注意事項

1. **API キー認証**: 全てのビジネスエンドポイントで必須
2. **ステートマシン**: 状態遷移ルールに従った操作のみ許可
3. **プラグイン設定**: plugins.json で動的ロード
4. **非同期処理**: 全ての DB 操作は非同期
5. **イベント発行**: Dapr 経由での非同期イベント
6. **マルチテナント**: テナントごとに独立したデータベース
7. **カート有効期限**: 作成から24時間