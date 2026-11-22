# Contract: master-data 支払マスタのサブコード

JSON は既存の API と同じく camelCase。応答は既存の `ApiResponse` で包む（`success`・`code`・`message`・`data`・`operation`）。以下は `data` の形。

---

## 支払マスタの取得・一覧（既存・応答に追加）

`GET /api/v1/tenants/{tenant_id}/payments/{payment_code}`
`GET /api/v1/tenants/{tenant_id}/payments`

```json
{
  "paymentCode": "11",
  "description": "キャッシュレス",
  "limitAmount": 0.0,
  "canRefund": true,
  "canDepositOver": false,
  "canChange": false,
  "isActive": true,
  "variants": [
    {"variantCode": "PAYPAY", "name": "PayPay", "isActive": true,
     "entryDatetime": "2026-11-22 10:00:00", "lastUpdateDatetime": null},
    {"variantCode": "VISA", "name": "VISA", "isActive": false,
     "entryDatetime": "2026-11-22 10:00:00", "lastUpdateDatetime": "2026-11-23 09:00:00"}
  ],
  "entryDatetime": "2026-01-01 00:00:00",
  "lastUpdateDatetime": null
}
```

- `variants` は `variantCode` の昇順。停止中も含む。サブコードが無ければ `[]`
- 作成（`POST /payments`）・更新（`PUT /payments/{payment_code}`）の要求は変えない（`variants` を受けない）。更新は既存の `variants` を保つ
- 削除（`DELETE /payments/{payment_code}`）はサブコードも一緒に消す

---

## サブコードの登録

`POST /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants` → **201**

権限: 支払マスタの作成と同じ（テナントのトークン。端末からは不可）

要求:

```json
{"variantCode": "PAYPAY", "name": "PayPay", "isActive": true}
```

| 項目 | 必須 | 規則 |
|---|---|---|
| `variantCode` | ✓ | `^[A-Za-z0-9_-]{1,20}$` |
| `name` | ✓ | 空でない |
| `isActive` | | 既定 `true` |

応答（`data`）: 登録したサブコード

```json
{"variantCode": "PAYPAY", "name": "PayPay", "isActive": true,
 "entryDatetime": "2026-11-22 10:00:00", "lastUpdateDatetime": null}
```

エラー:

| 場面 | HTTP | 例外 |
|---|---|---|
| 支払方法が無い | 404 | `DocumentNotFoundException` |
| 同じ支払方法に同じ `variantCode` がある | 400（既存の `DocumentAlreadyExistsException` の応答。支払マスタの重複と同じ） | `DocumentAlreadyExistsException` |
| `variantCode`・`name` の形式違反 | 422 | 検証エラー |
| パスのテナントとトークンのテナントが違う・端末からの呼び出し | 既存の支払マスタの作成と同じ | |

---

## サブコードの一覧

`GET /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants` → 200

権限: 支払マスタの取得と同じ（`terminal_id` のクエリによる API キーも可）

応答（`data`）: サブコードの配列（`variantCode` の昇順・停止中も含む）。ページングしない。

| 場面 | HTTP |
|---|---|
| 支払方法が無い | 404 |

---

## サブコードの取得

`GET /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants/{variant_code}` → 200

応答（`data`）: サブコード 1 件。

| 場面 | HTTP |
|---|---|
| 支払方法が無い・その支払方法にサブコードが無い | 404 |

---

## サブコードの変更

`PUT /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants/{variant_code}` → 200

権限: 支払マスタの更新と同じ

要求:

```json
{"name": "PayPay（QR）", "isActive": false}
```

| 項目 | 必須 | 規則 |
|---|---|---|
| `name` | ✓ | 空でない |
| `isActive` | ✓ | |

`variantCode` は変更できない。この要求のスキーマだけは追加の項目を許さない（`extra="forbid"`）ので、`variantCode` を含めると黙って無視せず 422 で拒否する（master-data の他の要求スキーマは追加の項目を無視する現行のまま）。

応答（`data`）: 変更後のサブコード。

| 場面 | HTTP |
|---|---|
| 支払方法が無い・その支払方法にサブコードが無い | 404 |
| 形式違反 | 422 |

---

## サブコードの削除

提供しない（`DELETE` は 405 Method Not Allowed）。停止は `PUT` で `isActive: false`。
