# Kugelpos システムアーキテクチャ

## 概要

Kugelposは、マイクロサービスアーキテクチャに基づいて構築されたPOSバックエンドシステムです。FastAPI、MongoDB、Dapr、Redisを中核技術として、高い可用性とスケーラビリティを実現しています。

## システム構成

### コアサービス

| サービス | ポート | 責務 | 実装場所 |
|---------|--------|------|----------|
| Account | 8000 | JWT認証、ユーザー管理 | `/services/account/` |
| Terminal | 8001 | 端末・店舗管理、開閉店処理 | `/services/terminal/` |
| Master-data | 8002 | 商品・マスターデータ管理 | `/services/master-data/` |
| Cart | 8003 | カート・取引処理（ステートマシン） | `/services/cart/` |
| Report | 8004 | レポート生成（プラグイン型） | `/services/report/` |
| Journal | 8005 | 電子ジャーナル・監査ログ | `/services/journal/` |
| Stock | 8006 | 在庫管理・WebSocketアラート | `/services/stock/` |

### 技術スタック

**フレームワーク・ライブラリ:**
- Python 3.12+ with FastAPI
- MongoDB (Motor非同期ドライバー)
- Redis (キャッシュ・pub/sub)
- Dapr (サービスメッシュ・ステート管理)
- Docker & Docker Compose

**共通ライブラリ:**
- `kugel_common`: 共通機能モジュール
  - 実装場所: `/services/commons/src/kugel_common/`
  - BaseSchemaModel、AbstractRepository、エラーハンドリング

## サービス間通信

### 1. HTTP通信（同期）

**HttpClientHelper統一実装:**
- 実装場所: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- 機能:
  - 自動リトライ（3回、指数バックオフ）
  - コネクションプーリング
  - サーキットブレーカーパターン
  - サービスディスカバリサポート

```python
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})
```

### 2. イベント通信（非同期）

**DaprClientHelper統一実装:**
- 実装場所: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`
- 機能:
  - サーキットブレーカー内蔵（3回失敗で60秒ブロック）
  - 自動リトライメカニズム
  - ノンブロッキングエラーハンドリング

**Pub/Subトピック:**
- `tranlog_report`: Cart → Report/Journal/Stock
- `tranlog_status`: Cart内部ステータス更新
- `cashlog_report`: Terminal → Report/Journal
- `opencloselog_report`: Terminal → Report/Journal

```python
async with get_dapr_client() as client:
    await client.publish_event("pubsub", "tranlog_report", transaction_data)
```

## データアーキテクチャ

### マルチテナント設計

**データベース分離:**
- パターン: `{tenant_id}_{service_name}`
- 例: `tenant001_cart`, `tenant001_stock`
- 完全なテナント別データ分離

**コレクション命名規則:**
- snake_case形式
- 例: `item_master`, `transaction_log`, `cart_documents`

### ベースドキュメントモデル

実装場所: `/services/commons/src/kugel_common/models/document/base_document_model.py`

```python
class BaseDocumentModel:
    id: ObjectId
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]
```

## アーキテクチャパターン

### 1. ステートマシンパターン（Cart Service）

**実装場所:** `/services/cart/app/services/cart_state_manager.py`

**状態遷移:**
```
initial → idle → entering_item → paying → completed
               ↘               ↗        ↘ cancelled
```

**状態実装:**
- InitialState, IdleState, EnteringItemState, PayingState
- CompletedState, CancelledState
- 各状態で許可される操作を定義

### 2. プラグインアーキテクチャ

**Cart Service実装:**
- 支払い戦略: `/services/cart/app/services/strategies/payments/`
- 販売促進: `/services/cart/app/services/strategies/promotions/`
- 設定ファイル: `plugins.json`

**Report Service実装:**
- レポート生成器: `/services/report/app/services/plugins/`
- 動的プラグインロード機能

### 3. リポジトリパターン

**実装場所:** `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`

```python
class AbstractRepository(ABC, Generic[Tdocument]):
    async def create_async(self, document: Tdocument) -> bool
    async def get_one_async(self, filter: dict) -> Tdocument
    async def update_one_async(self, filter: dict, new_values: dict) -> bool
```

**特徴:**
- ジェネリック型サポート
- 楽観的ロック with リトライ
- ページネーション対応

### 4. サーキットブレーカーパターン

**実装場所:** 
- HttpClientHelper: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- DaprClientHelper: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**設定:**
- 失敗閾値: 3回連続失敗
- 回復タイムアウト: 60秒
- 状態: CLOSED → OPEN → HALF_OPEN

**対象操作:**
- 外部HTTPサービス呼び出し
- Dapr pub/sub操作
- Daprステートストア操作

## セキュリティアーキテクチャ

### 認証・認可

**JWT認証:**
- 発行: Account Service
- 検証: 各サービスで独立実装
- Bearer Token形式

**API Key認証:**
- 端末固有APIキー（Terminal Service）
- SHA-256ハッシュ化保存

**マルチテナント分離:**
- データベースレベル分離
- テナントIDによる厳密なアクセス制御

### データ保護

- bcryptパスワードハッシュ化
- 環境変数による機密情報管理
- MongoDBレプリカセット構成

## パフォーマンス設計

### 非同期処理

**非同期I/O:**
- Motor（MongoDB非同期ドライバー）
- httpx（HTTP非同期クライアント）
- FastAPI非同期エンドポイント

**並行処理:**
- asyncio基盤の並列処理
- ノンブロッキングI/O操作

### キャッシング戦略

**Redisキャッシュ:**
- 端末情報キャッシュ（Cart Service）
- 日次カウンター管理
- セッション管理

**Daprステートストア:**
- カート状態管理
- 冪等性キー保存
- 取引ステータス追跡

### インデックス最適化

**MongoDB最適化:**
- 複合インデックス（tenant_id + 業務キー）
- TTLインデックス（自動データ削除）
- 部分インデックス（条件付き）

## エラーハンドリング

### 統一エラーコード体系

**形式:** XXYYZZ
- XX: サービス識別子
- YY: 機能・モジュール識別子  
- ZZ: 特定エラー番号

**サービス範囲:**
- 10XXX: Account Service
- 20XXX: Terminal Service
- 30XXX: Master-data Service
- 40XXX: Cart Service
- 41XXX: Report Service
- 42XXX: Journal Service
- 43XXX: Stock Service

### 多言語エラーメッセージ

**実装場所:** `/services/commons/src/kugel_common/exceptions/error_codes.py`

```python
class ErrorMessage:
    MESSAGES = {
        "ja": {"10001": "認証に失敗しました"},
        "en": {"10001": "Authentication failed"}
    }
```

## 運用・監視

### ヘルスチェック

**共通エンドポイント:** `GET /health`
- データベース接続確認
- Redis接続確認
- 依存サービス確認

### ログ管理

**統一ロギング:**
- Python logging module
- JSON構造化ログ
- リクエスト/レスポンス追跡

### メトリクス

**パフォーマンス指標:**
- レスポンス時間
- エラー率
- 接続数（WebSocket）
- サーキットブレーカー状態

## デプロイメント

### 開発環境

**Docker Compose構成:**
```yaml
services:
  mongodb:
    image: mongo:7.0
    command: ["--replSet", "rs0"]
  redis:
    image: redis:7-alpine
  # 各サービス定義
```

### 本番環境考慮事項

**スケーラビリティ:**
- ステートレス設計（カート除く）
- 水平スケーリング対応
- ロードバランサー対応

**高可用性:**
- MongoDBレプリカセット
- Redis Cluster（推奨）
- Dapr High Availability モード