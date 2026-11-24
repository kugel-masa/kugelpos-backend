# Contract: report の精算実績の API

**Feature**: 343-settlement-snapshot

応答は既存の `ApiResponse` の封筒（`success`・`code`・`message`・`data`・`userError`）。項目名は camelCase。

---

## 1. 精算の確定（内部・サービスアカウントだけ）

`POST /api/v1/internal/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlements`

**認証**: サービスアカウントのトークン（`get_service_account_info`）。パスのテナントがトークンのテナントと違えば 400（既存の `verify_tenant_id` と同じ）。端末のトークン・利用者のトークン・API キーは 401/403。

**要求**:

```json
{
  "businessCounter": 12,
  "businessDate": "20261124",
  "openCounter": 1,
  "seq": 35,
  "cashLogCount": 3,
  "physicalAmount": 52300.0,
  "settledBy": "staff:S001",
  "settledAt": "2026-11-24T21:03:11+09:00"
}
```

| 項目 | 必須 | 内容 |
|---|---|---|
| `businessCounter` | ○ | 営業の番号（1 以上） |
| `businessDate` | ○ | 営業日（YYYYMMDD） |
| `openCounter` | ○ | 開設の回数（1 以上） |
| `seq` | | カートが運ぶ番号の系列で、端末が最後に振った番号（0 以上）。無ければ「名乗りなし」 |
| `cashLogCount` | | 端末が記録した、その営業の入出金ログの件数（0 以上） |
| `physicalAmount` | | 数えた現金 |
| `settledBy` | | 精算した担当者 |
| `settledAt` | ○ | 端末が精算した日時 |

**応答** 200（作った・作り直した・確定済みを返した、のどれも同じ形）:

```json
{
  "settlementId": "6f0c…",
  "tenantId": "T001", "storeCode": "5001", "terminalNo": 1,
  "businessCounter": 12, "businessDate": "20261124", "openCounter": 1,
  "settledBy": "staff:S001", "settledAt": "…", "recordedAt": "…",
  "declaredCount": 35, "declaredSource": "pos",
  "state": "provisional",
  "includedCount": 34, "includedRanges": [{"first": 1, "last": 33}, {"first": 35, "last": 35}],
  "missingCount": 1, "missingRanges": [{"first": 34, "last": 34}],
  "duplicateNumbers": [], "serverNumberedCount": 0,
  "declaredCashLogCount": 3, "cashLogCount": 3, "missingCashLogCount": 0,
  "expectedCash": {"cashSales": 31800.0, "cashIn": {"amount": 20500.0, "count": 2}, "cashOut": {"amount": 0.0, "count": 0}, "total": 52300.0},
  "physicalAmount": 52300.0, "difference": 0.0,
  "created": true
}
```

- `created`: この要求で作った・作り直したなら `true`、確定済みのものを返したなら `false`
- 「仮」があれば計算し直して置き換える。「確定」があれば計算せずに返す（R-6）
- 計算はすべて同じ締めの時刻（届いた時刻）で絞ったデータで行う（R-12）
- 確定集計は応答に含めない
- 未着・重複・件数の不一致では断らない

**エラー**: 400（要求の形）、401/403（認証）、422（項目の値）、500 `413008`（確定集計の集計に失敗した、または大きすぎて保存できない。何も保存しない）、500（保存の失敗）。

---

## 2. 精算前の確認（内部・サービスアカウントだけ）

`GET /api/v1/internal/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlement-preview?business_counter=12&business_date=20261124&open_counter=1&seq=35&cash_log_count=3&physical_amount=52300`

`seq`・`cash_log_count`・`physical_amount` は任意。**何も保存しない**。確定集計は作らない（件数・未着・理論在高だけ）。端末からは terminal の `close-preview`（terminal-close.md）を通して呼ぶ。

**応答** 200: §1 の応答から `settlementId`・`recordedAt`・`created`・`state` を除いたものに、`settled: bool` を足す。確定した精算実績があれば `settled: true` で、**保存されている値**を返す。「仮」は無視して計算する。

---

## 3. 精算実績の一覧

`GET /api/v1/tenants/{tenant_id}/stores/{store_code}/settlements`

**認証**: 利用者のトークンだけ（テナントの照合）。端末の API キー・端末のトークンは受け付けない。

| クエリ | 内容 |
|---|---|
| `terminal_no` | 任意 |
| `business_counter` | 任意 |
| `state` | 任意。`provisional` / `final` |
| `business_date_from` / `business_date_to` | 任意。片方だけは 400 |
| `limit` | 既定 100、上限 1000 |
| `page` | 既定 1 |

**応答** 200: §1 の応答の形（`created` を除く）の配列。並びは `businessDate`・`terminalNo`・`businessCounter` の昇順。確定集計は含めない。`metadata` に総件数・`limit`・`page`。

---

## 4. 日報（既存の API の挙動の変化）

`GET /api/v1/tenants/{tenant_id}/stores/{store_code}/reports` と `GET …/terminals/{terminal_no}/reports` の `report_scope=daily`:

| 場合 | 今 | 変更後 |
|---|---|---|
| 確定した営業だけ | 照合してからその場で集計 | 確定集計を返す（複数なら合算） |
| 対象の営業が無い | 空の日報 | 空の日報（同じ） |
| 精算していない営業（確定した精算実績が無い営業）がある | 照合に失敗すると 403 `412101` | 403 `412101`、`data` に `unsettledSessions: [{terminalNo, businessCounter, businessDate, openCounter}]` |
| 精算のあとに届いた取引 | 日報に入る | 入らない |
| 期間の日報 | 照合せずにその場で集計 | 範囲の確定集計を合算。精算していない営業があれば 403 `412101` |
| `limit` / `page` | 集計に使う | 使わない（丸ごと返す） |
| 期間の日報の現金の欄 | 空 | 確定集計の合算の値 |

応答の文書に `missingCount` と `missingRanges`（`[{businessCounter, first, last}]`）が足される。

`report_scope=flash` は変わらない。

---

## 5. 閉設ログを受け取ったとき（pub/sub、既存の口）

report は、`settlement_id` を持つ閉設ログを受け取ったら、同じ営業の「仮」の精算実績を「確定」にする（R-6）。閉設ログに `settlement_id` が無ければ何もしない（古い terminal）。

## 6. エラーコード

| コード | 意味 | HTTP |
|---|---|---|
| `412101` | 精算していない | 403 |
| `413007` | 精算実績が見つからない | 404 |
| `413008` | 精算の確定の集計に失敗した・大きすぎて保存できない | 500 |
