# Contract: 受け手の失敗の記録・諦める判断・通知・掃除

report・journal・stock の購読の処理（`topic-tranlog`・`topic-cashlog`・`topic-opencloselog`）に足す。新しい Dapr のコンポーネント・購読・ルートは無い（R-1）。

## 受け手の処理の変更（R-3）

| サービス | 変更 |
|---|---|
| report（`app/api/v1/tran.py` の `handle_log`） | 本体（`Request` を受けず、`LogService` を自分で組み立て、処理の結果だけを返す）と、購読の薄いルートに分ける。`send_fatal_error_notification` を送らない（`app/services/log_service.py` の 3 か所も外す） |
| journal（`app/api/v1/tran.py` の購読の処理、`app/services/log_service.py`） | report と同じ |
| stock（`app/api/v1/stock.py` の `handle_transaction_log`） | 本体の切り出しだけ（Slack は送っていない）。中身をマスクせずに出しているログを直す（R-15） |

**本体の結果**（`HandlerOutcome`）

| 結果 | 意味 |
|---|---|
| `PROCESSED` | 処理できた |
| `ALREADY_PROCESSED` | イベント ID の記録があり、処理済み |
| `DROPPED(理由)` | 形が壊れていて処理できない |
| `FAILED(理由)` | 処理できなかった（例外の型と、中身を含まないメッセージ） |

本体は `record_failure` も、発行した側への「受け取った」の通知もしない。

**購読のルート**

| 本体の結果 | Dapr への応答 |
|---|---|
| `PROCESSED` / `ALREADY_PROCESSED` | 発行した側に「受け取った」を伝え（今と同じ best-effort）、SUCCESS |
| `DROPPED` | 今と同じ DROP |
| `FAILED` | `record_failure` を呼ぶ。下の表 |

## `record_failure`（`kugel_common.dead_letter`、R-4）

購読のルートだけが呼ぶ（流し直しは呼ばない）。

**受け取るもの**: DB、サービス名、トピック、CloudEvent（dict）、失敗の理由

**すること**: `dead_letter`（`_id` = イベント ID）を 1 回の `find_one_and_update`（パイプラインの更新、upsert、変更前を返す、外から来た値は `$literal`）で更新する（data-model の状態の表）。重複キーなら 1 回やり直す。1 回の記録は 5 秒まで。`GAVE_UP` なら通知の窓を進めて通知し（R-5a）、送れたら `notified_at` を書く。

**返すもの**

| 返り値 | いつ | 購読の応答 |
|---|---|---|
| `GAVE_UP` | 変更前が `—` / `failing` / `replayed` / `discarded` で、`episode_failure_count` が 17 に達した（「未対応になった」） | SUCCESS |
| `ALREADY_RECORDED` | 変更前が `pending` / `replaying` | SUCCESS（すぐ。通知しない） |
| `KEEP_RETRYING` | それ以外 | RETRY |
| 例外 | 記録が書けない・5 秒を超えた。上げ直す前に `notify_unrecordable` で知らせる（R-5c） | RETRY（使い切ったら `dlq-*`。R-5b） |

- 失敗の理由が MongoDB につながらないこと（`ConnectionFailure`・`ServerSelectionTimeoutError` など）なら、記録を試さずに `notify_unrecordable` だけをして RETRY
- 通知の失敗は返り値に影響しない
- 諦める回数は `DEAD_LETTER_GIVE_UP_AFTER_FAILURES`（既定 17）。環境変数で変えられる（e2e で小さくする）

## 定期の掃除（`kugel_common.dead_letter.sweep`、R-14）

各サービスが 5 分ごとに、全テナント（DB の名前 `db_<service>_<tenant>` から集める）について行う。テナントごとに 1 回 100 件まで。

| 対象 | 条件 | すること |
|---|---|---|
| 取り残された「失敗中」 | `state = failing`、`last_failed_at` が 30 分より前 | イベント ID の記録（状態ストア）があれば記録を消す。無ければ条件付きの更新で `pending` に上げ、通知の窓を進めて通知する |
| 送り損ねた通知 | `state = pending`、`notified_at` が空、`last_dead_at` が 2 分より前、`notify_attempts` < 5、`notify_claimed_at` が空か 10 分より前 | `notify_claimed_at` を書いて引き受け、`notify_attempts` を 1 足して送る。送れたら `notified_at`。窓は進めない |

サービスごとに、状態ストアでイベント ID を確かめる関数を渡す（購読の処理の重複の確かめと同じもの）。

## 受け直しの予算（`services/report/tests/unit/test_pubsub_redelivery_budget.py`）

既存の確かめ（`requeueInFailure: "false"`、`enableDeadLetter: "true"`、再試行の合計が `consumer_timeout` より短い）に、次を足す。

- 諦める回数の既定値（17）が、3 つのコンポーネントの resiliency の `maxRetries` + 1（今は 19）より 2 回以上少ない
- 再試行の待ち時間の合計に、1 回の配送の処理の枠（本体の処理 + 記録 5 秒 + 通知 5 秒）× 配送の回数を足しても、`consumer_timeout` より短い
- 掃除が「失敗中」を取り残しとみなす時間（30 分）が、再試行の待ち時間の最も遅い合計より長い

## 通知（Slack）

`send_warning_notification` を使う。送信は 5 秒まで。本文に中身を載せない。失敗の理由は例外の型だけ（R-15）。

```text
[report] Dead letter: topic-opencloselog
tenant: T001  event_id: e-123
store 5001 / terminal 1 / business date 20261124 / counter 7
last error: RuntimeError
gave up after 17 failures
GET /api/v1/tenants/T001/dead-letters/e-123
```

掃除が取り残しを上げたときは、`gave up after 17 failures` の代わりに `retries ran out before the subscriber gave up (N failures recorded); the original is also in dlq-report-topic-opencloselog` と書く。

前の窓で送らなかったものがあるとき（新しい窓の最初の通知）、末尾に足す:

```text
(23 more dead letters in the previous 5 minutes were not notified one by one; see GET /api/v1/tenants/T001/dead-letters)
```

まとめた通知（窓の 10 件目）:

```text
[report] Dead letters are piling up for tenant T001: 10 in 5 minutes (topic-tranlog 9, topic-cashlog 1). Further ones in this window are not notified one by one; see GET /api/v1/tenants/T001/dead-letters
```

## 記録できなかったもの（`notify_unrecordable`、R-5c）

記録が書けない失敗と、テナントのわからないイベント（R-6）は、記録の代わりに知らせる。

- 呼ぶところ: `record_failure` が例外を捕まえたとき（知らせてから上げ直す）、失敗の理由が MongoDB につながらないとき、report・journal の `get_log_service_from_request` の `tenant_id` が無くて 400 を返す分岐
- 窓: サービスのプロセスの中に 5 分。窓の最初の 1 件だけを送り、残りは数えて次の窓の最初の通知に添える（レプリカごと）
- 送信は 5 秒まで。送れなくても例外を出さない。購読の応答は変えない（RETRY / 400）
- 失敗はログに残る。受け直しを使い切ると `dlq-<app>-<topic>` に移る。見つけ方と戻し方は R-13

```text
[report] Events could not be recorded as dead letters: topic-tranlog
tenant: T001 (or "unknown")  event_id: e-123 (or "unknown")
reason: ServerSelectionTimeoutError
They are still being retried. If the retries run out they stay in dlq-report-topic-tranlog
(check with: rabbitmqctl list_queues name messages).
(7 more in the previous 5 minutes)
```
