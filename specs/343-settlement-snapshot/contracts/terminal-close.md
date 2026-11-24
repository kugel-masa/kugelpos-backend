# Contract: terminal の精算（閉設）

**Feature**: 343-settlement-snapshot

## `POST /api/v1/terminals/{terminal_id}/close`（既存）

**要求**（項目を1つ足す）:

```json
{ "physicalAmount": 52300.0, "seq": 35 }
```

| 項目 | 必須 | 内容 |
|---|---|---|
| `physicalAmount` | | 数えた現金（今と同じ） |
| `seq` | | この営業で、カートが運ぶ番号の系列で端末が最後に振った番号。新規・任意。0 以上。サーバー側の番号だけで動くクライアントは送らない |

**応答** 200（項目を足す）:

| 項目 | 内容 |
|---|---|
| 既存の項目 | 今と同じ（`physicalAmount` は精算実績の値） |
| `expectedCashTotal` | 理論在高 |
| `difference` | 過不足。数えていなければ `null` |
| `missingCount` | 取引の未着の件数 |
| `missingCashLogCount` | 入出金の未着の件数 |
| `settlementId` | 精算実績の識別子 |

**レシート**（`receiptText`・`journalText`）に足す行:
- 理論在高（例: `あるべき現金`）
- 過不足（数えていなければ印字しない）
- `未着の取引 N件`（N が 1 以上のときだけ）
- `未着の入出金 N件`（N が 1 以上のときだけ）

**エラー**（足すもの）:

| コード | 意味 | HTTP |
|---|---|---|
| `406016` | report で精算を確定できない（届かない・失敗・集計の失敗）。端末は開設のまま | 503 |

既存のエラー（端末が無い・開設していない・すでに閉設）は変わらない。すでに閉設した端末への再送は今までどおり `406003`（端末の状態のエラー。既存の挙動）。同じ端末の精算が同時に届いたら、1つだけが閉じ、もう一方は `406003`（端末の状態のエラー。既存の挙動）。

## report への依頼

`close` は、閉設ログを書く前に report の内部の口（report-settlement-api.md §1）を呼ぶ。トークンは `create_service_token(tenant_id, "terminal")`。接続先は `BASE_URL_REPORT`。タイムアウト 30 秒、再試行なし（1回だけ試す）。要求には `seq` と、terminal が手元で数えた入出金の件数（`cashLogCount`）を入れる。

| report の結果 | terminal の動き |
|---|---|
| 200 | 精算実績で閉設ログ・レシート・応答を作り、今までどおり保存・発行する |
| 接続できない・タイムアウト・5xx・404・401/403 | `406016`（503）。何も書かない |
| 400/422 | 要求の誤り（terminal の不具合）として `406008`（HTTP 400、既存の閉設のエラー） |

## 閉設ログ（発行するメッセージ）

足す項目: `settlement_id`、`expected_cash`、`difference`、`missing_count`、`missing_cash_log_count`。report は `settlement_id` で精算実績を確定する。
意味が変わる項目: `cart_transaction_count`・`cart_transaction_last_no` は `seq`（無ければ `null`）。

## `GET /api/v1/terminals/{terminal_id}/close-preview`（新規）

精算の前の確認。認証は `close` と同じ。クエリ `seq`・`physical_amount` は任意。terminal は、端末の営業（`business_counter`・`business_date`・`open_counter`）と手元で数えた入出金の件数を付けて、report の確認の口（report-settlement-api.md §2）を呼び、その結果を返す。何も保存しない。

| 項目 | 内容 |
|---|---|
| `expectedCashTotal`・`expectedCash` | 理論在高とその内訳 |
| `includedCount`・`missingCount`・`missingRanges` | 取引の件数と未着 |
| `missingCashLogCount` | 入出金の未着 |
| `difference` | `physical_amount` を渡したときの過不足 |
| `settled` | 確定した精算実績があるか |

エラー: 端末が開設していなければ `406003`。report で計算できなければ `406016`（503）。
