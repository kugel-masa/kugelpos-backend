# Contract: master-data 従業員の照合（内部専用）

**Feature**: 323-staff-pin-verification

## エンドポイント

```
POST /api/v1/internal/tenants/{tenant_id}/staff/{staff_id}/verify
```

- **内部専用**: サービス間からだけ呼ぶ。端末・クライアントからの入り口は terminal のサインインだけ。サービスアカウントのトークンなら、どのサービスからでも呼べる（呼び出し元の `service` はログに残す）
- **認証**: `Authorization: Bearer <service-account JWT>`（`create_service_token` が発行するもの）
  - `Authorization` が無い（API キーだけ） → 401
  - 端末の JWT など `is_service_account` が無い → 403
  - パスの `tenant_id` と claim の `tenant_id` が違う → 400（`verify_tenant_id`）

## 要求

```json
{ "pin": "1234" }
```

- `pin` は省略できる。省略・`null`・空文字は「PIN なし」
- PIN はパス・クエリに載せない

## 判定

| 従業員 | PIN | 結果 |
|---|---|---|
| 存在しない | 問わない | 404 / `405701` |
| PIN を登録していない（`null` または空） | 問わない（無視） | 200 |
| PIN を登録している | なし・空 | 401 / `405702` |
| PIN を登録している | 不一致 | 401 / `405703` |
| PIN を登録している | 一致 | 200 |

比較は定数時間（`secrets.compare_digest`、bytes）。

## 応答

### 200

```json
{
  "success": true,
  "code": 200,
  "message": "Staff verified. staff_id: S001",
  "data": { "id": "S001", "name": "Ann" },
  "operation": "verify_staff"
}
```

`data` に `pin` の項目は無い（型に無い）。`roles` も返さない（端末が使うのは `id` と `name` だけ）。

### 失敗（例: 405703）

```json
{
  "success": false,
  "code": 401,
  "message": "Staff verification failed: PIN mismatch: staff_id->S001",
  "userError": { "code": "405703", "message": "PIN が一致しません" },
  "data": null,
  "operation": "app_exception_handler"
}
```

- `details` を持たない。メッセージにも PIN を入れない
- 呼び出し元は `userError.code` だけで判定する（HTTP ステータスでは判定しない）。エラー応答は移行期間中 `user_error` も持つが非推奨

## エラーコード（master-data、405 帯）

| コード | 日本語 | English |
|---|---|---|
| 405701 | 従業員が見つかりません | Staff not found |
| 405702 | 従業員の PIN が必要です | Staff PIN is required |
| 405703 | PIN が一致しません | PIN does not match |

## ログ

- 受け付け: テナント・従業員コード・呼び出し元のサービス（claim の `service`）。PIN は出さない
- 失敗: 例外のメッセージ（従業員コードと理由）を WARNING で。PIN は出さない

## 従業員の登録・更新（変更）

`POST /api/v1/tenants/{tenant_id}/staff`・`PUT /api/v1/tenants/{tenant_id}/staff/{staff_id}` の `pin` を**任意**にする。省略・空文字は「PIN なし」として保存する。PIN を指定した要求はこれまでどおり受け付ける。応答に PIN を返さないことは変わらない。
