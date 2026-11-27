# Data Model: 処理できなかったイベントを見えるようにし、直したあとに流し直せるようにする

**Feature**: `230-dead-letter-handling` | **Date**: 2026-11-25（2026-11-27 改訂: 受け手の中で諦める形、レビューの反映）

report・journal・stock のそれぞれのテナントごとの DB（`db_report_<tenant>`、`db_journal_<tenant>`、`db_stock_<tenant>`）に置く。文書とリポジトリは `kugel_common.dead_letter` に置き、3 サービスで共有する。

---

## `dead_letter`（デッドレターの記録）

受け手 1 つ（＝このサービス）でのイベント 1 件。受け手の処理が失敗したときに作り、失敗が続いて受け手が諦めたら（または掃除が取り残しを見つけたら）「未対応」になる（R-1、R-4、R-14）。

| フィールド | 型 | 説明 |
|---|---|---|
| `_id` | string | イベント ID。API のパスの `{id}` もこれ。DB がサービス・テナントごとなので、これだけで 1 件に決まる（R-4） |
| `event_id` | string | イベント ID（`_id` と同じ。読みやすさのため） |
| `tenant_id` | string | テナント |
| `service` | string | 受け手（`report` / `journal` / `stock`） |
| `topic` | string | 元のトピック（`topic-tranlog` / `topic-cashlog` / `topic-opencloselog`）。購読の処理が知っている |
| `state` | string | `failing` / `pending` / `replaying` / `replayed` / `discarded`（R-7） |
| `message` | object | 受け手に渡った CloudEvent（`data` を含む）。最初の失敗で保存する（`replayed`・`discarded` からまた失敗したら書き直す）。ログには出さない。照会の API ではマスクして返す（R-15） |
| `summary` | object | 通知と一覧のための要約。`store_code`、`terminal_no`、`transaction_no`、`business_date`、`business_counter`（あるものだけ） |
| `last_error` | string \| null | 最後の失敗の理由。「例外の型: マスクして 200 文字で切ったメッセージ」（R-15） |
| `failure_count` | int | 処理が失敗した回数の合計（受け直し・流し直しを含む。二重の配送で多めに数えることがある） |
| `episode_failure_count` | int | 今回の一続きの失敗の回数。17（`DEAD_LETTER_GIVE_UP_AFTER_FAILURES`）に達したら「未対応」にする。`replayed`・`discarded` になったら 0 に戻す（R-4） |
| `dead_count` | int | 「未対応」になった回数（正確。R-5b） |
| `first_failed_at` / `last_failed_at` | datetime \| null | 最初と最後に処理が失敗した日時 |
| `first_dead_at` / `last_dead_at` | datetime \| null | 最初と最後に「未対応」になった日時 |
| `notified_at` | datetime \| null | 「未対応」になったことを通知した日時。「未対応」になるときに消し、送れたら書く（R-5） |
| `notify_claimed_at` | datetime \| null | 掃除が通知の送り直しを引き受けた日時（10 分を過ぎたら引き受け直せる。R-14） |
| `notify_attempts` | int | 通知を送ろうとした回数。「未対応」になるときに 0 に戻す。5 回で送り直しをやめる（R-5） |
| `replay_claim_id` | string \| null | 流し直しを引き受けたときの ID（UUID）。結果を書く更新の条件（R-7） |
| `replay_claimed_at` | datetime \| null | 流し直しを引き受けた日時（10 分を過ぎたら引き受け直せる） |
| `resolved_at` | datetime \| null | 流し直し済み・破棄になった日時 |
| `resolved_by` | string \| null | 流し直した・破棄した利用者（JWT の利用者名）。受け手が捨てたときは `system` |
| `resolution_note` | string \| null | 破棄の理由。受け手が捨てたときは `dropped by the handler: <理由>` |
| `purge_at` | datetime \| null | 消してよい日時（R-8）。`pending` と `replaying` には付けない |
| `created_at` / `updated_at` | datetime | |

外から来た値（`message`・`summary`・`last_error`・`topic`）は、パイプラインの更新では `{"$literal": …}` で包んで書く（R-4）。

**索引**

| 名前 | キー | 備考 |
|---|---|---|
| 一意 | `_id`（イベント ID） | 既定の索引。索引の準備を待たずに 1 件に決まる |
| 一覧 | `(state, last_dead_at desc)` | FR-016 |
| 一覧（トピック） | `(topic, state, last_dead_at desc)` | |
| 掃除 | `(state, last_failed_at)` | R-14 の取り残された「失敗中」 |
| 掃除（通知） | `(state, notified_at, last_dead_at)` | R-14 の送り損ねた通知 |
| TTL | `(purge_at)`、`expireAfterSeconds: 0` | R-8 |

既存のテナントには、各サービスの起動時の索引の準備で作る（#343 と同じ）。

**状態の移り変わり**（行が今の状態、列ができごと。「—」は記録が無い。N = 17）

| 今の状態 | 処理の失敗（購読、R-4） | 掃除（R-14） | 流し直す（R-7） | 破棄する |
|---|---|---|---|---|
| — | 作る → `failing`（`episode_failure_count` 1、`message` を保存、`purge_at` +1 日）。RETRY | — | 404 | 404 |
| `failing` | `episode_failure_count` +1。N 未満なら `purge_at` を延ばして RETRY。N に達したら → `pending`、`purge_at` を外す、通知、SUCCESS | 最後の失敗から 30 分: 処理済み（イベント ID の記録あり）なら消す。無ければ → `pending`、通知 | 409 | 409 |
| `pending` | 理由と回数だけ。すぐ SUCCESS、通知しない | 通知が届いていなければ送り直す | 引き受ける → `replaying` | → `discarded`（`purge_at` +90 日） |
| `replaying`（10 分以内） | 理由と回数だけ。すぐ SUCCESS | — | 409 | 409 |
| `replaying`（10 分超） | 理由と回数だけ。すぐ SUCCESS | — | 引き受け直す（新しい `replay_claim_id`） | 409 |
| `replayed` | `episode_failure_count` +1、`message` を書き直す、`purge_at` を now + 1 日まで延ばす、状態は変えずに RETRY。N に達したら → `pending`（上と同じ）、通知、SUCCESS | — | 409 | 409 |
| `discarded` | 同上 | — | 409 | 409 |

「処理の失敗」は 1 回のパイプラインの `find_one_and_update`（upsert、変更前の文書を返す）で行い、変更前の文書から `GAVE_UP` / `ALREADY_RECORDED` / `KEEP_RETRYING` を決める（R-4）。`pending` に変わるときは `notified_at`・`notify_claimed_at`・`resolved_*`・`replay_claim_*` を消し、`notify_attempts` を 0 にし、`dead_count` を 1 足して `first_dead_at`（無ければ）と `last_dead_at` を書く。

記録が書けない（例外・5 秒の時間切れ）ときは、「記録できない」の知らせ（R-5c）を出して RETRY。Dapr が受け直しを使い切ると、RabbitMQ の `dlq-*` に移る（最後の受け皿。R-1、R-13）。

流し直しの結果（`state = replaying` と自分の `replay_claim_id` が条件。合わなければ何も書かない。R-3）:

| 本体の結果 | 記録 |
|---|---|
| `PROCESSED` / `ALREADY_PROCESSED` | → `replayed`、`resolved_at`・`resolved_by`、`episode_failure_count` 0、`purge_at` +90 日。そのあと発行した側に「受け取った」を best-effort で伝える |
| `DROPPED` | → `discarded`、`resolved_by = system`、`resolution_note`、`episode_failure_count` 0、`purge_at` +90 日 |
| `FAILED`・例外・時間切れ | → `pending`、`last_error`・`last_failed_at`・`failure_count` +1 を流し直しが書く。通知しない |

破棄（`pending` だけ）は `episode_failure_count` を 0 に戻す。

---

## `dead_letter_alert`（通知の窓）

テナントと受け手ごとに 1 文書。FR-004 のまとめた通知のため（R-5a）。

| フィールド | 型 | 説明 |
|---|---|---|
| `_id` | string | `alert-window`（DB がテナント・サービスごとなので 1 つ） |
| `window_started_at` | datetime | 窓の始まり |
| `count` | int | 窓の中で `pending` になった記録の数 |
| `suppressed` | int | 窓の中で送らなかった通知の数（11 件目から） |
| `carried_suppressed` | int | 前の窓で送らなかった数。新しい窓の最初の通知に添える |
| `topics` | object | 窓の中のトピックごとの数。キーは記録の `topic` と同じ（`topic-tranlog` / `topic-cashlog` / `topic-opencloselog`） |

窓の切り替えと数えは、1 回のパイプラインの `find_one_and_update`（upsert、変更後の文書を返す）で行う（R-5a）。掃除が送り直す通知（R-14）は窓を進めない（1 回目の送信で数えてある）。

---

## 変わらないもの

- 受け手の購読のキュー、デッドレターの交換機、`dlq-*`（R-1）。`dlq-*` は最後の受け皿で、期限を付けない（R-12）
- 受け直しの設定（`pubsub-resiliency.yaml`、`requeueInFailure: "false"`、`enableDeadLetter: "true"`）
- 状態ストアのイベント ID の記録（48 時間）。R-14 の掃除が、処理済みかどうかを見るのに使う
- 発行した側（cart・terminal）の配信状態
