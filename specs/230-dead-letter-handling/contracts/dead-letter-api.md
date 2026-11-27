# Contract: デッドレターの API（report・journal・stock 共通）

3 サービスとも同じ形。ベースの URL だけが違う（report 8004、journal 8005、stock 8006）。

**認証**: 人がサインインして得た利用者の JWT（`Authorization: Bearer`）だけ（R-9）。

| 資格情報 | 結果 |
|---|---|
| 利用者の JWT、パスと同じテナント | 通る |
| 利用者の JWT、別のテナント | 403（既存の `verify_tenant_id` は 400 なので使わず、ルーターで比べる） |
| 端末の JWT | 403 |
| サービスアカウントの JWT | 403 |
| JWT なし（端末の API キーだけを含む） | 401 |

**応答**: 既存の `ApiResponse`（`success`、`code`、`message`、`data`、`metadata`、`operation`）。フィールド名は camelCase。

---

## 一覧

`GET /api/v1/tenants/{tenant_id}/dead-letters`

| クエリ | 既定 | 説明 |
|---|---|---|
| `state` | `pending` | `pending` / `replaying` / `replayed` / `discarded` / `all`。`failing` は一覧に出さない |
| `topic` | なし | `topic-tranlog` / `topic-cashlog` / `topic-opencloselog` |
| `notified` | なし | `false` で、通知が届いていない記録（`notifiedAt` が空）だけ |
| `dead_from` / `dead_to` | なし | 「未対応」になった日時の範囲（ISO 8601） |
| `limit` / `page` | 50 / 1 | `limit` は 1〜200 |

`data` は記録の配列（`message` を除く）。`id` はイベント ID。`lastError` は「例外の型: マスクして 200 文字で切ったメッセージ」（R-15）。`lastDeadAt` の新しい順。`metadata.total` に件数。

```json
{
  "id": "e-123",
  "service": "report",
  "topic": "topic-opencloselog",
  "eventId": "e-123",
  "state": "pending",
  "summary": {"storeCode": "5001", "terminalNo": 1, "businessDate": "20261124", "businessCounter": 7},
  "lastError": "RuntimeError: settlement could not be finalized",
  "failureCount": 17,
  "deadCount": 1,
  "firstDeadAt": "2026-11-25T10:00:00+09:00",
  "lastDeadAt": "2026-11-25T10:00:00+09:00",
  "notifiedAt": "2026-11-25T10:00:02+09:00",
  "resolvedAt": null,
  "resolvedBy": null,
  "resolutionNote": null
}
```

`deadCount` は「未対応」になった回数。`failureCount` は目安（二重の配送で多めに数えることがある）。`firstDeadAt` / `lastDeadAt` は「未対応」になった日時で、`dead_from` / `dead_to` もこれで絞る。

## 照会

`GET /api/v1/tenants/{tenant_id}/dead-letters/{id}`

一覧の項目に `message`（受け手に渡った CloudEvent）を加えて返す。`message` は `mask_loggable` でマスクする（開設精算のログの端末の `api_key` など。R-15）。保存されている中身は流し直しに使い、変えない。無ければ 404（`100001`）。

## 流し直す（1 件）

`POST /api/v1/tenants/{tenant_id}/dead-letters/{id}/replay`

本文なし。受け手の処理をその場で呼び、結果を返す（R-3）。1 件の時間の上限は 30 秒。

| 結果 | HTTP | `data.outcome` | 記録 |
|---|---|---|---|
| 処理できた | 200 | `replayed` | `replayed` |
| 受け手が捨てた（形が壊れている） | 200 | `discarded` | `discarded`（理由付き） |
| 処理できなかった（失敗・時間切れ） | 200 | `failed` | `pending`。`lastError`・`failureCount` を更新 |
| 状態が `pending` でない（ほかの人が操作した、引き受けの期限内の `replaying`） | 409 | — | 変えない。サービスごとのコード（R-10） |
| 記録が無い | 404 | — | `100001` |

`data` は `{"id", "outcome", "error"}`。処理できなかったことは、API の失敗ではなく `outcome: failed` で返す。

引き受け直された（期限を過ぎた）あとに遅れて終わった流し直しは、記録を書かない（R-7）。その応答の `outcome` は処理の結果のままで、`error` に「記録はほかの流し直しが持っている」と入る。

## 流し直す（まとめて）

`POST /api/v1/tenants/{tenant_id}/dead-letters/replay`

```json
{"ids": ["e-123", "e-456"]}
```

`ids` は 1〜100 件（超えたら 422、重複は 1 件にまとめる）。受け付けたら **202** を返し、サーバーの中の裏の処理で 1 件ずつ順に流し直す（R-7）。`data` は `{"accepted": ["e-123", "e-456"]}`。

- 結果は一覧（`state`）と照会で確かめる。`pending` でないもの・無いものは飛ばす（ログに残す）
- 要求の時間切れや接続の切断に縛られない
- 途中でサービスが落ちたら、引き受けたままの記録は 10 分で引き受け直せる。まだ引き受けていない記録は `pending` のまま残るので、もう一度送る
- 同じ記録を 2 回の要求に入れても、引き受けで 1 回だけ流れる

## 破棄する

`POST /api/v1/tenants/{tenant_id}/dead-letters/{id}/discard`

```json
{"reason": "test data from the e2e run"}
```

`reason` は必須（空なら 422）。`pending` だけ。それ以外は 409。成功したら更新した記録を返す。
