# APIコントラクト: ターミナルJWT認証

**ブランチ**: `feature/67-terminal-jwt-auth` | **日付**: 2026-03-23

## エンドポイント

### POST /api/v1/auth/token

APIキーからJWTトークンを取得する。

**リクエスト:**
```
POST /api/v1/auth/token
Headers:
  X-API-KEY: <terminal_api_key>
```

**レスポンス (200 OK):**
```json
{
  "success": true,
  "data": {
    "access_token": "<jwt_token>",
    "token_type": "bearer",
    "expires_in": 86400
  },
  "error": null
}
```

**エラーレスポンス (401 Unauthorized):**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "200101",
    "message": "Invalid API key"
  }
}
```

**備考:**
- terminal_id はAPIキーからDBルックアップで特定される
- 返されるJWTには現在のターミナル状態が反映される

---

## レスポンスヘッダー: X-New-Token

ライフサイクル状態変更APIのレスポンスに含まれる新しいJWTトークン。

**対象エンドポイント:**
- `POST /api/v1/terminals/{terminal_id}/open`
- `POST /api/v1/terminals/{terminal_id}/sign-in`
- `POST /api/v1/terminals/{terminal_id}/sign-out`
- `POST /api/v1/terminals/{terminal_id}/close`

**レスポンスヘッダー:**
```
X-New-Token: <new_jwt_token>
```

**備考:**
- レスポンスボディのスキーマは変更なし
- クライアントはこのヘッダーの値を保存し、以降のリクエストで使用する
- ヘッダーが存在しない場合（旧バージョン互換）、既存トークンを継続使用

---

## 認証方式: ターミナルJWT

JWT取得後、各サービスへのリクエストで使用する。

**リクエスト:**
```
GET /api/v1/tenants/{tenant_id}/stores/{store_code}/items
Headers:
  Authorization: Bearer <terminal_jwt_token>
```

**検証フロー:**
1. Bearer トークンをデコード
2. `token_type` クレームを確認（"terminal" であること）
3. 署名検証（SECRET_KEY + HS256）
4. 有効期限チェック
5. tenant_id クレームからテナント特定

**エラーレスポンス (401 Unauthorized):**
```json
{
  "detail": "Invalid or expired terminal token"
}
```

---

## 後方互換: 既存APIキー認証

移行期間中、既存のX-API-KEY認証も引き続き動作する。

**リクエスト（旧方式）:**
```
GET /api/v1/tenants/{tenant_id}/stores/{store_code}/items?terminal_id=T001-001-01
Headers:
  X-API-KEY: <api_key>
```

**認証優先順位:**
1. Authorization ヘッダーの Bearer トークン（token_type="terminal"）
2. Authorization ヘッダーの Bearer トークン（ユーザーJWT）
3. X-API-KEY ヘッダー + terminal_id パラメータ
