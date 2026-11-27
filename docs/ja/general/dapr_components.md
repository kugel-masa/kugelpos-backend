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

#### 受け手が諦めて記録する（#230）

受け手は RabbitMQ のデッドレターキューを待ちません。イベントの失敗を、受け手のテナントの DB の `dead_letter` の記録（イベント ID ごとに 1 件）に数え、最後の失敗の理由を、イベントの値を含まない形で残します。一続きの失敗が 17 回目（`DEAD_LETTER_GIVE_UP_AFTER_FAILURES`）になると、記録は **未対応（pending）** になって CloudEvent を保存し、受け手は `SUCCESS` を返します。イベントはキューから消え、記録がその控えになります。受け直しは約 10 分（ゆらぎで 5〜15 分）で、サイドカーの 19 回より 2 回手前です。受け手に届かなかった配送（再起動中、トークンの拒否）は数えられないためです。回数を増やすことは予算のテストが止め、減らすことはいつでも安全です。すでに未対応の記録があるイベントの失敗は、すぐに受け取ったことにします。

記録が未対応になると、Slack に 1 回知らせます。テナントと受け手ごとの 5 分の窓で 9 件までは 1 件ずつ、10 件目でまとめて 1 回、以降は次の窓まで送らず、次の窓の最初の通知に送らなかった件数を添えます。通知には要約（店舗・端末・営業日・通し番号）、例外の型、API のパスを載せ、イベントの中身は載せません。report と journal は、失敗のたびの Slack の通知をやめました。

デッドレターキュー `dlq-<app-id>-<topic>` は、記録できないイベントのための最後の受け皿として残ります。失敗のあいだ DB につながらなかったとき（受け手は「Events could not be recorded as dead letters」を 5 分に 1 回知らせ、受け直しを求め続けます）と、テナントのわからないイベントです。ほかに控えが無いので、期限は付けません。

各受け手は 5 分ごとにテナントを掃除します。

- 最後の失敗から 30 分たった「失敗中」の記録は、受け直しが終わっています。状態ストアにイベント ID があれば、途中で処理できていたので記録を消します。無ければサイドカーが先に使い切ったので、未対応にして知らせます（「retries ran out before the subscriber gave up」）。
- 通知が送れなかった未対応の記録（Slack の失敗、プロセスの停止）は、5 回まで送り直します。そのため、通知がまれに 2 回届くことがあります。

**デッドレターの対応。** `GET /api/v1/tenants/{tenant_id}/dead-letters` で一覧し（既定は `state=pending`、通知が届かなかったものは `notified=false`）、1 件を照会し（`GET .../{id}`、中身はマスク）、原因を直して流し直します（`POST .../{id}/replay`）。この受け手の処理をこのサービスの中で呼ぶので、ほかの受け手には何も届きません。応答は `replayed`・`discarded`・`failed` のどれかです。まとめては `POST .../replay`（100 件まで、202 で受け付けて裏で流す）。流し直す必要の無いものは、理由を付けて破棄します（`POST .../{id}/discard`）。精算が確定した営業の取引を流し直しても、取引のログが入るだけで、確定した日報は変わりません（#343）。人の利用者だけが使えます。端末とサービスアカウントのトークンは断ります。

**デッドレターキュー。** ふだんは空です。「記録できない」の知らせが来たら、原因を直してから件数を見ます。

```bash
rabbitmqctl list_queues name messages | grep '^dlq-' | awk '$2 > 0'
```

残っていたら、動的な shovel でその受け手の購読のキューに戻します。そのキューはその受け手だけが読みます。そのときだけプラグインを有効にし（`rabbitmq-plugins enable rabbitmq_shovel rabbitmq_shovel_management`）、控えが欲しければ先に書き出してから:

```bash
rabbitmqctl set_parameter shovel requeue-<app>-<topic> \
  '{"src-protocol":"amqp091","src-uri":"amqp://","src-queue":"dlq-<app>-<topic>","src-delete-after":"queue-length",
    "dest-protocol":"amqp091","dest-uri":"amqp://","dest-queue":"<app>-<topic>"}'
```

受け手が受け直し、なお失敗するものを記録します。配備の側の監視で、`dlq-*` の長さに警報を付けることを勧めます。Azure Container Apps では、resiliency を `pubsub-resiliency.yaml` ではなく環境の側で設定します。手元と同じ（exponential、`maxInterval: 3m`、`maxRetries: 18`）にしてください。違うと、受け手が諦める前に、失敗するイベントがすべて `dlq-*` に移ります。`scripts/azure-pubsub-resiliency.sh` が `pubsub-resiliency.yaml` をもとに確かめ、`--apply` を付けると設定します。それでも回数が足りないときは、掃除の通知が知らせます。受け直しが尽きて取り残された記録の通知に、受け手に要る `maxRetries` を書きます。

発行側では、cart と terminal がイベントごとに配信状態を持ちます。ログを保存するトランザクションの中で `pending` として作り、ブローカーが受け取ると `published`、受け取らなかったときは `publish_failed` になります。再発行ジョブ（5 分ごと、24 時間）が送り直すのは `pending` と `publish_failed`、それに `handed_off_at` のない `failed` だけです。最後の `failed` は状態を分ける前に書かれたもので、ブローカーが受け取らなかった発行です。ブローカーが受け取ったイベントは永続キューが保持しているので、送り直しても別のコピーとして配信されるだけです。例外は、消費者が読み飛ばしたイベントです。ブローカーに渡してから（`handed_off_at`）15 分を過ぎ、消費者がそれより後に渡したイベントは受け取ったのに、このイベントはまだ受け取っていない場合です。キューには残っていない可能性が高い（購読側のキューができる前に発行された、または処理済みで受信の通知だけが失われた）ので、1 回だけ送り直します（`republished_at`）。送り直すのは、引き受け（claim）を取った 1 つのワーカーだけです。15 分を過ぎても届かないイベントは、状態に関係なく 1 回だけ警告します。`warning_sent_at` を条件付き更新で書けたワーカーだけが送るので、uvicorn のワーカーごとに動く cron でも警告は増えません。RabbitMQ はデータを `rabbitmq_data` ボリュームに固定のホスト名で保存するので、コンテナを作り直してもキューの中身は残ります（`stop.sh --clean` で削除されます）。

### 配送の認証

購読用の経路（report と journal の `/api/v1/tranlog`、`/api/v1/cashlog`、`/api/v1/opencloselog`、stock の `/api/v1/tranlog`）は JWT を持たず、書き込み先のテナントの DB を本文から決めます。そのため、そのサービス自身のサイドカーが配送したものだけを受け付けます（#134）。環境変数 `APP_API_TOKEN` を持って起動した daprd は、アプリへのすべてのリクエストにその値を `dapr-api-token` ヘッダーで付けます。経路はそれをアプリの `APP_API_TOKEN` と比べ、ヘッダーがないか値が違うリクエストを、ハンドラーが動く前に 401 で拒否します。

アプリとサイドカーには同じ値が必要です。購読するサービスは、値がないとき、または `docker-compose.yaml` で公開されている開発用トークンのときは、`ALLOW_INSECURE_DEV_SECRETS=true` を設定しない限り起動しません。`docker-compose.prod.yaml` では必須です。ほかのサービスは何も購読しないので、この値は要りません。

## Redis設定とキーの分離

### キーの置き場所

ステートストアのキーは、どれも Redis の DB 0 に入ります。Dapr は、書き込んだサービスの app id をキーの先頭に付けます（`<app-id>||<key>`）。この接頭辞で分かれるのはサービスどうしで、ストアどうしではありません。1 つのサービスが使うストアは同じ接頭辞を共有するので、キーが重ならないようにする必要があります。cart の cartstore と masterstore はどちらも `cart||` の下に書き込みます。重ならないのは、masterstore のキーが必ず `mdcache:` で始まり、カートのキーは `<tenant_id>:<カートの UUID>` の形で、masterstore のキーがこの形になることはないからです（#332）。値は `data` と `version` を持つ Redis のハッシュです。読むときは `GET` ではなく `HGET <key> data` を使います。

| ストア | キー | TTL | 使用サービス |
|--------|------|-----|-------------|
| statestore | `<app-id>\|\|<event id>`（冪等性） | 48時間（キーごと） | Report, Journal, Stock |
| cartstore | `cart\|\|<tenant_id>:<cart_id>` (#332) | 10時間 | Cart |
| masterstore | `cart\|\|mdcache:…` | 300秒（既定値） | Cart |
| terminalstore | - | - | 未使用 |

```bash
docker compose exec redis redis-cli -n 0 --scan --pattern 'cart||*'
docker compose exec redis redis-cli -n 0 HGET 'cart||<tenant_id>:<cart_id>' data
```

Dapr の `state.redis` が DB 番号として読むのは `redisDB` だけです。以前のコンポーネントは `databaseIndex`（1・2・3）を指定していましたが、Dapr はこれを読まないので、ストアは最初からすべて DB 0 にありました。ストアを別の DB に移すのは設定の変更ではなく移行です。サイドカーが切り替わった時点で、DB 0 にあるキー（処理中のカートを含む）が見つからなくなります。ローリング更新の途中では、古い DB を見るレプリカと新しい DB を見るレプリカで、見えるカートが食い違います。また、`maxmemory` と追い出しは Redis のインスタンス全体にかかるので、DB を分けてもカートを追い出しから守ることにはなりません。

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