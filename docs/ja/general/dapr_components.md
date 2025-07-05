# Kugelpos Daprコンポーネント仕様

## 概要

KugelposシステムではDapr（Distributed Application Runtime）を以下の目的で使用しています：

- **ステートストア**: Redisベースのキャッシングと冪等性管理
- **Pub/Subメッセージング**: サービス間のイベント駆動通信
- **サーキットブレーカー**: 障害時の適切なフェイルオーバー

## Daprコンポーネント設定

### ステートストアコンポーネント

#### 1. statestore（汎用ステートストア）

**設定ファイル:** `/services/dapr/components/statestore.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "3600"
  - name: databaseIndex
    value: "1"
```

**用途:**
- 冪等性管理（重複イベント防止）
- 処理済みイベントIDの追跡
- サーキットブレーカーのバックアップ機能

**使用サービス:** Report, Journal, Stock

#### 2. cartstore（カート専用ステートストア）

**設定ファイル:** `/services/dapr/components/cartstore.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: cartstore
spec:
  type: state.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "36000"
  - name: databaseIndex
    value: "2"
```

**用途:**
- カートドキュメントのキャッシング
- トランザクション中の状態保持
- 高速アクセスのためのMongoDB補完

**使用サービス:** Cart

### Pub/Subコンポーネント

#### 1. pubsub-tranlog-report（取引ログ配信）

**設定ファイル:** `/services/dapr/components/pubsub_tranlog_report.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: pubsub-tranlog-report
spec:
  type: pubsub.redis
  metadata:
  - name: redisHost
    value: redis:6379
  - name: consumerID
    value: kugelpos-tranlog-consumer
  - name: processingTimeout
    value: "180"
```

**イベントフロー:**
- **Publisher:** Cart Service
- **Subscribers:** Report Service, Journal Service, Stock Service
- **トピック:** 取引完了、キャンセル、返金

#### 2. pubsub-cashlog-report（現金入出金ログ配信）

**設定ファイル:** `/services/dapr/components/pubsub_cashlog_report.yaml`

**イベントフロー:**
- **Publisher:** Terminal Service
- **Subscribers:** Report Service, Journal Service
- **トピック:** 現金入金、現金出金

#### 3. pubsub-opencloselog-report（開閉店ログ配信）

**設定ファイル:** `/services/dapr/components/pubsub_opencloselog_report.yaml`

**イベントフロー:**
- **Publisher:** Terminal Service
- **Subscribers:** Report Service, Journal Service
- **トピック:** 開店、閉店

## サービス別Dapr利用パターン

### Account Service
- **Dapr使用:** なし
- **通信:** 直接HTTP（JWT発行・検証）

### Terminal Service
- **Dapr使用:** Pub/Sub（Publisher）
- **発行イベント:**
  - `cashlog_report`: 現金入出金
  - `opencloselog_report`: 開店・閉店
- **実装:** PubsubManager → DaprClientHelper

### Master-data Service
- **Dapr使用:** なし
- **通信:** 直接HTTP（マスターデータ提供）

### Cart Service
- **Dapr使用:** ステートストア + Pub/Sub
- **ステートストア:** `cartstore`（カートキャッシング）
- **発行イベント:** `tranlog_report`（取引ログ）
- **パターン:** ステートマシン + プラグイン

### Report Service
- **Dapr使用:** ステートストア + Pub/Sub（Subscriber）
- **ステートストア:** `statestore`（冪等性管理）
- **受信イベント:** 全種類のログ
- **プラグイン:** レポート生成器

### Journal Service
- **Dapr使用:** ステートストア + Pub/Sub（Subscriber）
- **ステートストア:** `statestore`（冪等性管理）
- **受信イベント:** 全種類のログ
- **機能:** 電子ジャーナル保存

### Stock Service
- **Dapr使用:** ステートストア + Pub/Sub（Subscriber）
- **ステートストア:** `statestore`（冪等性管理）
- **受信イベント:** `tranlog_report`（在庫更新）
- **追加機能:** WebSocketアラート（Dapr非依存）

## 統一Daprクライアント実装

### DaprClientHelper

**実装場所:** `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**主要機能:**
- サーキットブレーカー内蔵（3回失敗で60秒ブロック）
- 自動リトライメカニズム
- pub/subとステートストアの統一API
- ノンブロッキングエラーハンドリング

**使用例:**
```python
async with get_dapr_client() as client:
    # イベント発行
    await client.publish_event("pubsub-tranlog-report", "tranlog_topic", data)
    
    # 状態保存
    await client.save_state("statestore", "event_123", {"processed": True})
    
    # 状態取得
    state = await client.get_state("statestore", "event_123")
```

### レガシー実装からの移行

**移行済み:**
- `PubsubManager` → `DaprClientHelper`
- `StateStoreManager` → `DaprClientHelper`

**統一による利点:**
- エラーハンドリングの一貫性
- サーキットブレーカーの統合
- 設定の集約化

## イベント駆動アーキテクチャパターン

### ファンアウトパターン

```
Cart Service → tranlog_report → ┌─ Report Service
                               ├─ Journal Service
                               └─ Stock Service

Terminal Service → cashlog_report → ┌─ Report Service
                                   └─ Journal Service

Terminal Service → opencloselog_report → ┌─ Report Service
                                        └─ Journal Service
```

### 冪等性保証パターン

**実装:**
1. イベント受信時にevent_idをチェック
2. 未処理の場合のみビジネスロジック実行
3. 処理完了後にevent_idを記録

**コード例:**
```python
async def handle_tranlog_event(event_data):
    event_id = event_data.get("event_id")
    
    # 冪等性チェック
    if await state_manager.is_processed(event_id):
        logger.info(f"Event {event_id} already processed")
        return
    
    # ビジネスロジック実行
    await process_transaction_log(event_data)
    
    # 処理完了マーク
    await state_manager.mark_processed(event_id)
```

## Redis設定とデータベース分離

### データベースインデックス割り当て

| DB Index | 用途 | TTL | 使用サービス |
|----------|------|-----|-------------|
| 0 | Redis default | - | 未使用 |
| 1 | statestore（冪等性） | 1時間 | Report, Journal, Stock |
| 2 | cartstore（キャッシング） | 10時間 | Cart |
| 3 | terminalstore | - | 未使用 |

### TTL設定理由

- **statestore（1時間）**: イベント重複防止に必要な短期保存
- **cartstore（10時間）**: 長時間取引に対応する中期保存

## パフォーマンス考慮事項

### 接続プール設定

```python
# httpx.AsyncClient設定
timeout=httpx.Timeout(30.0)
limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
```

### バッチ処理

- メッセージ受信時のバッチサイズ制限なし
- 順次処理による確実性重視
- サーキットブレーカーによる障害時保護

### モニタリング指標

- **接続数**: アクティブなDapr接続
- **サーキットブレーカー状態**: CLOSED/OPEN/HALF_OPEN
- **イベント処理率**: 成功/失敗/スキップ
- **レイテンシ**: pub/sub配信時間

## 運用上の注意事項

### サーキットブレーカー動作

1. **CLOSED（正常）**: 全リクエスト通過
2. **OPEN（遮断）**: 全リクエスト即座に失敗
3. **HALF_OPEN（回復試行）**: テストリクエストで状態判定

### 障害時の動作

- **Redis障害**: ステートストアフォールバック、重複処理許容
- **Pub/Sub障害**: イベント配信スキップ、ログ記録
- **ネットワーク障害**: 自動リトライ、指数バックオフ

### 設定変更時の影響

- **TTL変更**: 既存データには影響なし、新規データから適用
- **DB Index変更**: 既存データアクセス不可、慎重な移行必要
- **タイムアウト変更**: 即座に反映、処理中リクエストは継続