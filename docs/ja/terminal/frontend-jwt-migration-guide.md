# フロントエンド向け: ターミナル JWT 認証への移行ガイド

本ドキュメントは、cart をはじめとする業務サービスへのリクエストを `terminal_id + api_key` 方式から **ターミナル JWT トークン方式** に切り替えるための、フロントエンド開発者向け移行ガイドです。

- 対応する issue: [#67](https://github.com/kugel-masa/kugelpos-public/issues/67)
- 実装 PR: [#68](https://github.com/kugel-masa/kugelpos-public/pull/68)
- バックエンド側の変更はすでにマージ済みで、**api_key 方式は後方互換のためそのまま使えます**。切り替えは段階的に行えます。

---

## 1. 背景 — なぜ変えるのか

### 現在のフロー (api_key 方式)

```
POS フロント ─[X-API-KEY + terminal_id]→ cart
                                           │
                                           ▼ HTTP 呼び出しで毎回 api_key を検証
                                       terminal サービス ─→ MongoDB
```

- cart などの全業務 API が、リクエストごとに terminal サービスへ HTTP 呼び出しを発生させて api_key を検証していました。
- cart はさらに、取得した `api_key` を使って master-data にも呼び出しを連鎖させていました。
- サービス間トラフィックとレイテンシのオーバーヘッドが大きいのが課題でした。

### 新しいフロー (JWT 方式)

```
POS フロント ─[X-API-KEY]→ POST /auth/token ─ JWT 発行
POS フロント ─[Authorization: Bearer JWT]→ 各サービス (ローカルで署名検証 のみ)
```

- 一度 JWT を取得すれば、各サービスは **自前で署名検証するだけ** で済み、サービス間通信が不要になります。
- JWT にはターミナル状態 (store_code、staff_id、business_date など) が claim として入っているため、cart などは DB を見に行く必要もありません。

### 効果 (PR #68 の本番相当構成 A/B 計測)

| エンドポイント | api_key 平均 | JWT 平均 | 改善 |
|----------------|:------------:|:--------:|:----:|
| Create Cart    |  105 ms      |  38 ms   | **-64%** |
| Add Item       |  101 ms      |  30 ms   | **-70%** |
| Cancel Cart    |  614 ms      | 261 ms   | **-57%** |
| **全体平均**   | **114 ms**   | **36 ms**| **-68%** |

P95 も 200 ms → 98 ms (**-51%**) と大きく改善します。

---

## 2. 現在のフロントエンド実装 (変更前)

cart 操作は、クエリパラメータ `terminal_id` とヘッダ `X-API-KEY` を付けてリクエストしている想定です。

```http
POST /api/v1/carts?terminal_id=tenant001-S0001-01
X-API-KEY: <terminal_api_key>
Content-Type: application/json

{
  "transaction_type": 101,
  "user_id": "C001",
  "user_name": "Customer"
}
```

- `terminal_id` フォーマット: `{tenant_id}-{store_code}-{terminal_no}`
- `X-API-KEY` はターミナル登録時に発行される固定の API キー

## 3. 新しいフロー (変更後の全体像)

```
[1] 起動 / 再ログイン時
      POS フロント ──POST /api/v1/auth/token─→ terminal  (X-API-KEY)
                  ←─── JWT (24h 有効)

[2] ライフサイクル操作 (open / sign-in / sign-out / close)
      POS フロント ──Bearer JWT──→ terminal
                  ←─── 本文 + X-New-Token ヘッダ (更新 JWT)
      POS フロント: ローカル保持の JWT を X-New-Token で置き換え

[3] 業務操作 (cart / master-data / journal / report / stock)
      POS フロント ──Bearer JWT──→ 各サービス (ローカル検証)

[4] 401 を受けた場合
      → /auth/token へ再ログインして JWT を取り直す
```

以降、各ステップの詳細 API 仕様を説明します。

---

## 4. API 仕様

### 4.1. `POST /api/v1/auth/token` — 初回ログイン (JWT 発行)

`X-API-KEY` を JWT に交換するエンドポイントです。**ターミナル起動時および JWT の期限切れ時に呼び出します。**

- **サービス**: terminal (port 8001)
- **メソッド**: `POST`
- **パス**: `/api/v1/auth/token`
- **ヘッダ**:
  - `X-API-KEY: <api_key>` (必須)
- **クエリパラメータ**:
  - `terminal_id` (任意だが **強く推奨**): `{tenant_id}-{store_code}-{terminal_no}` 形式
    - 指定あり: 対象テナント DB を O(1) ルックアップ
    - 指定なし: 後方互換のため全テナント DB をスキャン (遅い)

#### リクエスト例

```http
POST /api/v1/auth/token?terminal_id=tenant001-S0001-01 HTTP/1.1
Host: terminal.example.com
X-API-KEY: abc123def456...
```

#### 成功レスポンス (200)

```json
{
  "success": true,
  "code": 200,
  "message": "Token issued for terminal tenant001-S0001-01",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

- `access_token`: 以降のリクエストに付与する JWT 本体
- `token_type`: 常に `"bearer"`
- `expires_in`: 有効期限 (秒)。デフォルト `86400` (= 24 時間、`TERMINAL_TOKEN_EXPIRE_HOURS` で変更可)

#### 失敗レスポンス (401)

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: API-Key

{ "detail": "API key is required" }   // もしくは "Invalid API key"
```

---

### 4.2. 通常の業務リクエスト — `Authorization: Bearer` を付ける

取得した JWT を **`Authorization: Bearer <token>`** ヘッダで業務サービスに送ります。cart は `terminal_id` クエリも `X-API-KEY` も **不要** になります (JWT から claim として取り出すため)。

#### cart 作成 (JWT 方式)

```http
POST /api/v1/carts HTTP/1.1
Host: cart.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "transaction_type": 101,
  "user_id": "C001",
  "user_name": "Customer"
}
```

以降の cart 操作 (item 追加、discount、payment、cancel、void ...) も、同じ `Authorization: Bearer` を付与するだけで動作します。

#### 他サービスも同じ形式

| サービス     | ポート | JWT 対応 | 備考 |
|--------------|:------:|:--------:|------|
| cart         | 8003   | ✔        | `terminal_id` / `X-API-KEY` 不要に |
| master-data  | 8002   | ✔        | tenant_id は JWT claim から取得 |
| report       | 8004   | ✔        | staff_id は JWT claim から取得 |
| journal      | 8005   | ✔        | tenant_id は JWT claim から取得 |
| stock        | 8006   | ✔        | tenant_id は JWT claim から取得 |
| terminal     | 8001   | ✔        | 既存のユーザー JWT とは別枠で受け付け |

---

### 4.3. ライフサイクル操作 — `X-New-Token` で JWT を更新する

以下 4 つのエンドポイントは、**成功時にレスポンスヘッダ `X-New-Token` に更新後の JWT** を返します。フロントはこの値をローカル保持の JWT に **必ず上書き** してください。なぜなら、これらの操作で JWT に含まれる claim (status、business_date、open_counter、staff_id など) が変わるためです。

| 操作     | エンドポイント                                    | 変わる claim |
|----------|---------------------------------------------------|--------------|
| open     | `POST /api/v1/terminals/{terminal_id}/open`       | `status`, `business_date`, `open_counter`, `business_counter` |
| sign-in  | `POST /api/v1/terminals/{terminal_id}/sign-in`    | `staff_id`, `staff_name` が付与される |
| sign-out | `POST /api/v1/terminals/{terminal_id}/sign-out`   | `staff_id`, `staff_name` が消える |
| close    | `POST /api/v1/terminals/{terminal_id}/close`      | `status` が `Closed` に |

#### 例: sign-in

```http
POST /api/v1/terminals/tenant001-S0001-01/sign-in HTTP/1.1
Authorization: Bearer <現在の JWT>
Content-Type: application/json

{ "staff_id": "S001" }
```

```http
HTTP/1.1 200 OK
X-New-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   ← これに差し替える

{ "success": true, "code": 200, "message": "...", "data": { ... } }
```

> **注意** — `X-New-Token` が返っても body のスキーマは変わりません。他のエンドポイント (`/cart` 系など) では `X-New-Token` は **返りません**。

---

### 4.4. 401 Unauthorized の扱い

JWT の有効期限 (デフォルト 24 時間) が切れた場合や、JWT が破損している場合は `401 Unauthorized` が返ります。フロントは:

1. 保持している JWT を破棄
2. `POST /api/v1/auth/token` に `X-API-KEY` で再ログインして新しい JWT を取得
3. 失敗したリクエストを新しい JWT でリトライ

というフローでリカバリしてください。業務の途中でセッションが途切れないよう、`expires_in` を参考に期限前 (例: 残り 5 分) に先回りで再取得する設計を推奨します。

---

## 5. JWT Claims の中身

発行される JWT には以下の claim が含まれます。参考のために記載しますが、**フロント側で claim を解釈する必要は基本的にありません** (staff_name の表示などに使いたい場合は利用可)。

```json
{
  "sub": "terminal:tenant001-S0001-01",
  "tenant_id": "tenant001",
  "store_code": "S0001",
  "terminal_no": "01",
  "terminal_id": "tenant001-S0001-01",
  "status": "Opened",
  "token_type": "terminal",
  "iss": "terminal-service",
  "iat": 1742691600,
  "exp": 1742778000,

  "business_date": "20260421",      // open 後に付与
  "open_counter": 1,                // open 後に付与
  "business_counter": 5,            // open 後に付与

  "staff_id": "S001",               // sign-in 後に付与
  "staff_name": "Tanaka Taro"       // sign-in 後に付与
}
```

- 署名アルゴリズム: `HS256` (共有秘密鍵)
- `token_type` が `"terminal"` であること、および `tenant_id` の存在は各サービスが検証します

---

## 6. フロント側の実装パターン (TypeScript 例)

### 6.1. 認証クライアント

```ts
// /api/terminalAuth.ts
type TokenResponse = {
  success: boolean;
  data: { access_token: string; token_type: "bearer"; expires_in: number };
};

export async function acquireTerminalToken(params: {
  terminalId: string;
  apiKey: string;
}): Promise<{ token: string; expiresAt: number }> {
  const url = `/api/v1/auth/token?terminal_id=${encodeURIComponent(params.terminalId)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "X-API-KEY": params.apiKey },
  });

  if (!res.ok) throw new Error(`token acquisition failed: ${res.status}`);
  const body: TokenResponse = await res.json();

  return {
    token: body.data.access_token,
    expiresAt: Date.now() + body.data.expires_in * 1000,
  };
}
```

### 6.2. 共通 fetch ラッパ (JWT 差し替え・401 リカバリ・X-New-Token 自動更新)

```ts
// /api/authedFetch.ts
import { acquireTerminalToken } from "./terminalAuth";

type Session = {
  token: string;
  expiresAt: number;
  terminalId: string;
  apiKey: string; // 401 時のリカバリ用に保持
};

let session: Session | null = null; // メモリ常駐。永続化する場合は secure storage を使用

export async function initSession(terminalId: string, apiKey: string) {
  const { token, expiresAt } = await acquireTerminalToken({ terminalId, apiKey });
  session = { token, expiresAt, terminalId, apiKey };
}

export async function authedFetch(input: RequestInfo, init: RequestInit = {}): Promise<Response> {
  if (!session) throw new Error("session not initialized");

  // 残り 5 分を切っていたら先回り更新
  if (session.expiresAt - Date.now() < 5 * 60 * 1000) {
    const { token, expiresAt } = await acquireTerminalToken(session);
    session.token = token;
    session.expiresAt = expiresAt;
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.token}`);

  let res = await fetch(input, { ...init, headers });

  // 401 → 一度だけ再取得してリトライ
  if (res.status === 401) {
    const { token, expiresAt } = await acquireTerminalToken(session);
    session.token = token;
    session.expiresAt = expiresAt;
    headers.set("Authorization", `Bearer ${session.token}`);
    res = await fetch(input, { ...init, headers });
  }

  // X-New-Token が付いていたら差し替え (open / sign-in / sign-out / close のときだけ)
  const newToken = res.headers.get("X-New-Token");
  if (newToken) {
    session.token = newToken;
    // 新トークンの exp は従来通り 24h 相当なので expiresAt も伸ばす
    session.expiresAt = Date.now() + 24 * 60 * 60 * 1000;
  }

  return res;
}
```

### 6.3. 使い方

```ts
// アプリ起動時
await initSession("tenant001-S0001-01", "<api_key>");

// 以後はすべて authedFetch 経由で呼ぶ
await authedFetch("/api/v1/terminals/tenant001-S0001-01/sign-in", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ staff_id: "S001" }),
});

await authedFetch("/api/v1/carts", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ transaction_type: 101, user_id: "C001", user_name: "Customer" }),
});
```

ポイントは 3 つだけ:

1. **起動時に 1 回** `/auth/token` を叩いて JWT を取る
2. 以降はすべて **`Authorization: Bearer`** で呼ぶ
3. レスポンスヘッダ `X-New-Token` が来たら **無条件で差し替える**

---

## 7. 後方互換について

- 既存の `terminal_id` (クエリ) + `X-API-KEY` (ヘッダ) 方式は **そのまま使えます**。切り替えは段階的で構いません。
- JWT と `X-API-KEY` が同時に送られた場合は **JWT が優先** されます。
- cart → master-data などのサービス間通信も、cart が受けた JWT をそのまま転送する設計になっています。フロント側で両サービスに別々のヘッダを送る必要はありません。
- 将来的に api_key 方式は非推奨化される可能性があります。新規実装は JWT 方式で作成してください。

---

## 8. 移行チェックリスト

- [ ] 起動シーケンスに `POST /api/v1/auth/token` (X-API-KEY + terminal_id クエリ) を追加
- [ ] 取得した `access_token` をメモリに保持する仕組みを用意
- [ ] 共通 fetch ラッパを用意し、以降のリクエストには `Authorization: Bearer` を自動付与
- [ ] レスポンスヘッダ `X-New-Token` を検出したら保持トークンを上書きする処理を追加
- [ ] 401 応答時に `/auth/token` で再取得してリトライする処理を追加
- [ ] `expires_in` (デフォルト 24h) に対して期限前の先回り更新を追加
- [ ] 既存の `?terminal_id=...` クエリと `X-API-KEY` ヘッダを JWT 経路から除去 (移行完了後)
- [ ] ターミナル open / sign-in / sign-out / close の 4 箇所で X-New-Token のハンドリングを確認
- [ ] 動作確認: cart の create / item 追加 / 決済 / cancel / void が JWT 単独で通ること

---

## 9. 参考リンク / ファイル

- JWT 発行エンドポイント: `services/terminal/app/api/v1/auth.py`
- JWT 生成ユーティリティ: `services/commons/src/kugel_common/utils/terminal_auth.py`
- cart の JWT 対応依存関数: `services/cart/app/dependencies/terminal_cache_dependency.py` (`get_terminal_info_with_jwt_or_cache`)
- JWT 検証と claim 変換: `services/commons/src/kugel_common/security.py` (`verify_terminal_token`, `terminal_claims_to_terminal_info`)
- X-New-Token を返すライフサイクル API: `services/terminal/app/api/v1/terminal.py` (open / sign-in / sign-out / close)
- 設定値 (有効期限など): `services/commons/src/kugel_common/config/settings_auth.py` の `TERMINAL_TOKEN_EXPIRE_HOURS`
