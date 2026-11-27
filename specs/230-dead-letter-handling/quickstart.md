# Quickstart: デッドレターの記録・通知・流し直し

**Feature**: `230-dead-letter-handling`

ローカルのスタック（`./scripts/start.sh`）で確かめる手順と、配備・運用の手順。

---

## 1. 必ず失敗するイベントで記録を作る

ふだんは 17 回の失敗（標準 10 分）で諦める。e2e では、諦める回数と受け直しを小さくした設定を上書きで入れたスタックで行う（`DEAD_LETTER_GIVE_UP_AFTER_FAILURES=2`、resiliency は `maxRetries: 3`、`maxInterval: 1s`。諦める回数は `maxRetries` + 1 より 2 回以上少なくする）。上書きの compose と resiliency は e2e 用に置く。

1. journal だけが処理できない取引ログを `topic-tranlog` に出す。故障はテストから入れて戻せるものにする（e2e のテスト用の故障の入れ方。手で試すなら、journal の DB の対象のコレクションに、同じキーで型の違う文書を先に入れて保存を失敗させ、あとで消す）
2. journal は失敗するたびに記録の回数を足し、2 回目で諦めて記録を「未対応」にし、RabbitMQ には成功を返す。`dlq-journal-topic-tranlog` には何も入らない
3. 通知が 1 回届く

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8005/api/v1/tenants/$TENANT/dead-letters?state=pending" | jq '.data[] | {id, topic, eventId, lastError, failureCount, deadCount}'
```

- 記録が 1 件、`failureCount` は 2、`deadCount` は 1、`lastError` に失敗の理由
- Slack（ローカルでは通知のログ）に 1 回だけ。失敗のたびの重大エラーの通知は無い。記録の `notifiedAt` に送った日時
- report には記録が無い（report は処理できた）

## 2. 流し直す

原因を取り除いてから（例: journal の不具合を直して作り直す）:

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8005/api/v1/tenants/$TENANT/dead-letters/$ID/replay" | jq .data
# {"id": "…", "outcome": "replayed", "error": null}
```

- journal にその取引が 1 件入る。report の件数は変わらない
- 原因が残っていれば `outcome: failed`、記録は `pending` のまま（`failureCount` が増え、`lastError` が変わる）。一覧から消えない

## 3. 精算の確定に失敗した閉設ログ（#343）

1. report の精算の確定が失敗するようにして（例: 精算実績の文書をテストで壊す）、端末を精算する
2. 閉設ログの記録が report で「未対応」になり、通知に店舗・端末・営業日・営業の通し番号が出る。日報は 403（`412101`）
3. 原因を取り除いて閉設ログを流し直すと、精算実績が確定になり、日報が出る

## 4. 破棄する

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"reason": "test data"}' \
  "http://localhost:8005/api/v1/tenants/$TENANT/dead-letters/$ID/discard"
```

## 5. 記録が書けないとき（最後の受け皿）

1. journal の MongoDB を止めて、取引ログを出す
2. journal は記録も書けないので RETRY を返し続ける。「記録できない」の知らせが Slack に 1 回届く（5 分に 1 回まで）。受け直しを使い切ると `dlq-journal-topic-tranlog` に 1 件入る
3. MongoDB を戻し、下の「`dlq-*` に落ちたものを戻す」の手順で戻すと、journal がまた受け直し、処理できるか、諦めて記録する

---

## 配備のとき

1. report・journal・stock を配備する。Dapr のコンポーネント、resiliency、RabbitMQ の設定は変えない
2. 配備より前から `dlq-*` にメッセージがたまっている環境では（古いデータのある環境だけ。新しく作る環境では要らない）、下の手順で受け手に戻す。受け手が受け直し、処理できなければ記録する

## 運用

- 通知が来たら、記録を照会して原因を直し、流し直す。流し直す必要の無いものは、理由を付けて破棄する
- 通知は「未対応」になったときに送り、届かなかったものは 5 分ごとの掃除が送り直す（5 回まで。まれに 2 回届く）。それでも届かなかったものは `GET …/dead-letters?notified=false` で見つかる
- 受け手が失敗を数えられずに受け直しを使い切ったもの（受け手の再起動が重なったときなど）は、掃除が受け直しの終わったころ（最後の失敗から 30 分）に見つけて「未対応」にし、通知する。同じイベントは `dlq-*` にも残っている（通知に「the original is also in dlq-…」と出る）。記録から流し直せばよく、`dlq-*` の控えをあとで R-13 の手順で戻しても、受け手は処理済みとして二重に数えない
- まとめて流し直すときは `POST …/dead-letters/replay` に `{"ids": [...]}`（100 件まで）。202 が返り、結果は一覧で見る
- 精算が確定した営業の取引を report に流し直しても、確定した日報は変わらない（#343）。取引のログが入るだけ
- cart は、届かなかった取引ログを 15 分後に別に通知する。デッドレターの通知（受け手ごと）とは別
- `dlq-*` は最後の受け皿で、ふだんは 0 件。期限で消えない。「Events could not be recorded as dead letters」の知らせが来たら、原因を直してから件数を見る。知らせが来ていなくても、ときどき件数を見る

  ```bash
  rabbitmqctl list_queues name messages | grep '^dlq-' | awk '$2 > 0'
  ```

### `dlq-*` に落ちたものを戻す（R-13）

原因（MongoDB の障害、テナントの無い中身など）を取り除いてから行う。

1. 念のため書き出す（管理画面の Queues → `dlq-<app>-<topic>` → Get messages を requeue ありで、または `rabbitmqadmin get queue=dlq-<app>-<topic> ackmode=ack_requeue_true count=<件数>`）
2. shovel のプラグインを有効にする（`rabbitmq-plugins enable rabbitmq_shovel rabbitmq_shovel_management`。終わったら `rabbitmq-plugins disable` で戻してよい）
3. キューごとに動的な shovel を作る。元はキュー `dlq-<app>-<topic>`、先はその受け手の購読のキュー `<app>-<topic>`、`src-delete-after` は `queue-length`

   ```bash
   rabbitmqctl set_parameter shovel requeue-<app>-<topic> \
     '{"src-protocol":"amqp091","src-uri":"amqp://","src-queue":"dlq-<app>-<topic>","src-delete-after":"queue-length",
       "dest-protocol":"amqp091","dest-uri":"amqp://","dest-queue":"<app>-<topic>"}'
   ```

   始めた時点の件数だけを移して止まる。購読のキューに直接入れるので、ほかの受け手には届かない
4. 確かめる: `dlq-*` が空になり、戻したものが受け手で処理されたか、記録が `pending` になったか（一覧と受け手のログ）
