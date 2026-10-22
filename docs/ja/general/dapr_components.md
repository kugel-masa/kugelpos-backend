# Kugelpos Daprコンポーネント仕様

## 概要

KugelposシステムではDapr（Distributed Application Runtime）を以下の目的で使用しています：

- **ステートストア**: Redisベースのキャッシングと冪等性管理
- **Pub/Subメッセージング**: RabbitMQによるサービス間のイベント駆動通信
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
  type: pubsub.rabbitmq
  metadata:
  - name: connectionString
    value: amqp://guest:guest@rabbitmq:5672
  - name: consumerID
    value: kugelpos-tranlog-consumer
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

event_id は、発行元の delivery-status への通知より前に記録します。通知はベストエフォートで、ログを保存した後は、通知に失敗してもイベントを失敗にしません。処理済みと分かった再配信でも `received` を通知し直します。1 回目の通知が失われた場合に備えるためです。

### 再配信とデッドレター

処理できなかったイベントには 500 で `RETRY` を返し、Dapr のサイドカーが再試行します（`dapr/components/pubsub-resiliency.yaml`：指数バックオフ・上限 3 分・18 回、合計で約 16〜24 分）。再試行を使い切ると、report 系のコンポーネント（`requeueInFailure: "false"`、`enableDeadLetter: "true"`）がメッセージを RabbitMQ のデッドレターキュー `dlq-<app-id>-<topic>` に移し、そこに残ります。再試行の合計は RabbitMQ の `consumer_timeout`（30 分）より短くなければなりません。超えると、ブローカーが未 ack のメッセージをキューに戻し、再試行が最初からやり直しになります。この 2 点は `services/report/tests/unit/test_pubsub_redelivery_budget.py` で確認しています。

何度配信しても成功しないイベント（`event_id` がない、スキーマに合わない）には 200 で `DROP` を返し、再試行しません。

デッドレターキューを読む仕組みはまだありません（#230）。

発行側では、cart と terminal がイベントごとに配信状態を持ちます。ログを保存するトランザクションの中で `pending` として作り、ブローカーが受け取ると `published`、受け取らなかったときは `publish_failed` になります。再発行ジョブ（5 分ごと、24 時間）が送り直すのは `pending` と `publish_failed` だけです。ブローカーが受け取ったイベントは永続キューが保持しているので、送り直しても別のコピーとして配信されるだけです。例外は、消費者が読み飛ばしたイベントです。ブローカーに渡してから（`handed_off_at`）15 分を過ぎ、消費者がそれより後に渡したイベントは受け取ったのに、このイベントはまだ受け取っていない場合です。キューには残っていない可能性が高い（購読側のキューができる前に発行された、または処理済みで受信の通知だけが失われた）ので、1 回だけ送り直します（`republished_at`）。送り直すのは、引き受け（claim）を取った 1 つのワーカーだけです。15 分を過ぎても届かないイベントは、状態に関係なく 1 回だけ警告します。`warning_sent_at` を条件付き更新で書けたワーカーだけが送るので、uvicorn のワーカーごとに動く cron でも警告は増えません。RabbitMQ はデータを `rabbitmq_data` ボリュームに固定のホスト名で保存するので、コンテナを作り直してもキューの中身は残ります（`stop.sh --clean` で削除されます）。

## Redis設定とデータベース分離

### データベースインデックス割り当て

| DB Index | 用途 | TTL | 使用サービス |
|----------|------|-----|-------------|
| 0 | Redis default | - | 未使用 |
| 1 | statestore（冪等性） | 48時間（キーごと） | Report, Journal, Stock |
| 2 | cartstore（キャッシング） | 10時間 | Cart |
| 3 | terminalstore | - | 未使用 |

### TTL設定理由

- **statestore（48時間）**: 冪等性のキーごとに `ttlInSeconds` を付けます（report・journal・stock の `EVENT_IDEMPOTENCY_TTL_SECONDS`）。コンポーネントの既定値（1 時間）より優先されます。発行元の再発行の期間より長くなければなりません。cart と terminal は、ブローカーに渡せていないイベントを元の event_id のまま 24 時間再発行します
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
- **Pub/Sub（RabbitMQ）障害**: イベント配信スキップ、ログ記録
- **ネットワーク障害**: 自動リトライ、指数バックオフ

### 設定変更時の影響

- **TTL変更**: 既存データには影響なし、新規データから適用
- **DB Index変更**: 既存データアクセス不可、慎重な移行必要
- **タイムアウト変更**: 即座に反映、処理中リクエストは継続