# Contract: 取引ログの支払行とレポートの支払

---

## 取引ログ（pub/sub `topic-tranlog` 等・journal の保存・report の入力）

`payments[]` の各要素（snake_case のまま運ばれる）:

| 項目 | 変更 |
|---|---|
| `payment_no`・`payment_code`・`deposit_amount`・`amount`・`detail` | 変更なし |
| `description` | サブコードで記帳した行はサブコードの名前 |
| `variant_code` | **追加**（`null` 可） |
| `builtin_description` | **追加**（`null` 可・販売時点の支払方法の名前） |

追加の項目を知らない受け手は無視してよい。

---

## 売上レポート

`GET /api/v1/tenants/{tenant_id}/stores/{store_code}/reports?report_scope=...&report_type=sales...`（既存）

`payments[]` の各要素:

```json
{
  "paymentCode": "11",
  "paymentName": "キャッシュレス",
  "amount": 3500.0,
  "count": 3,
  "variants": [
    {"variantCode": "PAYPAY", "variantName": "PayPay", "amount": 2500.0, "count": 2},
    {"variantCode": "VISA", "variantName": "VISA", "amount": 1000.0, "count": 1}
  ]
}
```

- `paymentName`: 販売時点の支払方法の名前（`builtin_description`）。無い行（本フィーチャーの前）は支払行の名前
- `variants`: `variantCode` の昇順、`null`（サブコードなし）は末尾。`amount`・`count` の合計は行と一致する（`count` は支払行の数）
- 取引種別の符号（取消・返品はマイナス）は現行どおり内訳にも掛かる
- 内訳の名前・行の名前: 期間内で最も新しい販売時点の名前（販売日時の降順に並べて先頭を取る）

---

## 支払レポート

`report_type=payment`（既存）

`payment_summary[]` の各要素（支払レポートは現行どおり文書を snake_case のまま返す）:

```json
{
  "payment_code": "11",
  "payment_name": "キャッシュレス",
  "count": 3,
  "amount": 3500.0,
  "ratio": 35.0,
  "variants": [
    {"variant_code": "PAYPAY", "variant_name": "PayPay", "amount": 2500.0, "count": 2},
    {"variant_code": "VISA", "variant_name": "VISA", "amount": 1000.0, "count": 1}
  ]
}
```

- `payment_name`・`variant_name`: 現在の支払マスタの名前（現行の支払レポートと同じ）。マスタに無いサブコードは支払行の名前
- `count`: 取引の数（現行どおり）。内訳の `count` も取引の数なので、1 つの取引で同じ支払方法の 2 つのサブコードを使うと、内訳の合計が行を上回る
- `ratio` は行にだけ付ける
- マスタの名前は支払マスタの全ページから引く（現行の 100 件の 1 ページだけの取得を直す）

件数の例（取引種別の符号を含む）:

| 取引 | 支払行 |
|---|---|
| T1 売上 | `11/VISA 1000`・`11/PAYPAY 2000` |
| T2 売上 | `11/PAYPAY 500` |
| T3 T1 の取消 | `11/VISA 1000`・`11/PAYPAY 2000`（支払行の金額は正のまま。取消の取引種別に符号 -1 が掛かる） |

| 行・内訳 | 金額 | 件数 |
|---|---|---|
| `11` | 500 | 1（T1 +1・T2 +1・T3 -1） |
| `11/PAYPAY` | 500 | 1（T1 +1・T2 +1・T3 -1） |
| `11/VISA` | 0 | 0（T1 +1・T3 -1） |

T3 が無いときは `11` 3,500 円・2 件、内訳は `PAYPAY` 2,500 円・2 件、`VISA` 1,000 円・1 件（内訳の件数の合計 3 は行の 2 を上回る）。

---

## 印字（レシートデータ）

売上レポート・支払レポートの印字は変えない（内訳は出さない）。取引のレシートは支払行の名前（サブコードの名前）を印字する。
