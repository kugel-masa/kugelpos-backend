# リサーチ結果: ターミナルJWT認証

**ブランチ**: `feature/67-terminal-jwt-auth` | **日付**: 2026-03-23

## 調査1: 現在の認証フロー

### 決定事項
既存の `__get_tenant_id()` 内部関数に terminal JWT 検証パスを追加する方式を採用。

### 根拠
- `__get_tenant_id()` は terminal_id+api_key と token の両方を既に分岐処理している
- ここに terminal JWT（token_type="terminal"）の分岐を追加すれば、既存の依存関数（`get_tenant_id_with_security` 等）がそのまま動作する
- 各サービスの既存コードへの影響を最小限に抑えられる

### 検討した代替案
- 完全に新しい依存関数セットを作成 → 全サービスの全エンドポイントの書き換えが必要で過剰
- ミドルウェアベースの検証 → FastAPIの依存性注入パターンと合わない

## 調査2: サービス別のterminal_info利用状況

### 決定事項
サービスごとに必要な変更レベルが異なる。

| サービス | terminal_info必要? | 使用フィールド | JWT移行の影響度 |
|----------|-------------------|---------------|----------------|
| master-data | NO | tenant_idのみ | 低 - tenant_idをJWTから取得するだけ |
| journal | NO | tenant_idのみ | 低 - tenant_idをJWTから取得するだけ |
| stock | NO | tenant_idのみ | 低 - tenant_idをJWTから取得するだけ |
| report | YES（オプション） | staff.id | 中 - staff_idをJWTクレームから取得可能 |
| cart | YES（必須） | tenant_id, store_code, terminal_no, terminal_id, api_key, staff | 高 - terminal_info取得ロジックの置き換えが必要 |

### 根拠
- master-data、journal、stockは `get_tenant_id_with_security_by_query_optional` で tenant_id のみ抽出
- reportは `get_requesting_staff_id` で staff.id を取得（JWTクレームから直接取得可能）
- cartは `get_terminal_info_with_cache` で完全な TerminalInfoDocument を取得し、api_key を使って master-data を呼び出す

## 調査3: CartからMaster-Dataへの呼び出しパターン

### 決定事項
CartのWebリポジトリ（PaymentMasterWebRepository、ItemMasterWebRepository、SettingsMasterWebRepository）を修正し、JWTが利用可能な場合はAuthorizationヘッダーでJWTを転送する。

### 根拠
- 現在のパターン: `headers = {"X-API-KEY": self.terminal_info.api_key}` + `params = {"terminal_id": self.terminal_info.terminal_id}`
- JWT対応後: `headers = {"Authorization": f"Bearer {jwt_token}"}` でmaster-dataが直接tenant_idを検証
- master-dataの `get_tenant_id_with_security_by_query_optional` は既にtokenパスをサポートしているため、JWT転送で動作する

### 検討した代替案
- CartがJWTクレームからtenant_idを取得し、サービストークンを発行してmaster-dataを呼び出す → 追加のトークン生成が不要なのでJWT転送の方がシンプル

## 調査4: JWT署名・検証方式

### 決定事項
既存の `SECRET_KEY` と `HS256` アルゴリズムを使用。token_type クレームでユーザーJWTと区別。

### 根拠
- `settings_auth.py` の SECRET_KEY は全サービスで既に共有されている
- `service_auth.py` の `create_service_token()` も同じ鍵を使用
- token_type="terminal" クレームで安全に区別可能
- 鍵の分離はセキュリティ上のメリットがあるが、運用の複雑さが増す

### 検討した代替案
- 専用のTERMINAL_JWT_SECRET_KEY → 鍵管理が複雑化、既にユーザーが既存鍵共有を選択済み

## 調査5: TerminalInfoDocumentの構造

### 決定事項
JWTクレームから `TerminalInfoDocument` 互換のオブジェクトを構築する関数を提供。

### 根拠
- cartサービスの `get_cart_service_async` は `TerminalInfoDocument` を受け取る
- JWT移行の後方互換性のため、JWTクレームからTerminalInfoDocumentを構築するアダプターが必要
- ただし `api_key` フィールドはJWTに含まれないため、master-data呼び出し方法の変更が必須

## 調査6: 有効期限とリフレッシュ戦略

### 決定事項
デフォルト24時間。`TERMINAL_TOKEN_EXPIRE_HOURS` 設定を settings_auth.py に追加。

### 根拠
- POSターミナルは通常1営業日単位で運用される
- ライフサイクル操作（open/close）で再発行されるため、実質的に毎日リフレッシュ
- 24時間あれば深夜営業や異常時のバッファとしても十分
