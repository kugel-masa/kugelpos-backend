# クイックスタート: ターミナルJWT認証

**ブランチ**: `feature/67-terminal-jwt-auth` | **日付**: 2026-03-23

## 認証フロー概要

```
1. POS Terminal → POST /api/v1/auth/token (X-API-KEY) → JWT取得
2. POS Terminal → Bearer JWT → 各サービス → ローカル検証（サービス間呼び出しなし）
3. 状態変更時 → X-New-Token ヘッダーで新JWT受領 → 以降のリクエストに使用
```

## 開発・テスト手順

### 1. トークン取得
```bash
# APIキーでJWT取得
curl -X POST http://localhost:8001/api/v1/auth/token \
  -H "X-API-KEY: <your_terminal_api_key>"
```

### 2. JWT使用
```bash
# JWTで各サービスにアクセス
curl http://localhost:8002/api/v1/tenants/T001/stores/001/items \
  -H "Authorization: Bearer <jwt_token>"
```

### 3. ライフサイクル操作（トークン再発行）
```bash
# ターミナルオープン → X-New-Token ヘッダーで新JWTを受領
curl -X POST http://localhost:8001/api/v1/terminals/T001-001-01/open \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"business_date": "20260323"}' \
  -v  # -v で X-New-Token ヘッダーを確認
```

### 4. 旧方式（後方互換）
```bash
# 既存のAPIキー認証も引き続き動作
curl http://localhost:8002/api/v1/tenants/T001/stores/001/items?terminal_id=T001-001-01 \
  -H "X-API-KEY: <api_key>"
```

## 変更対象ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `services/commons/src/kugel_common/config/settings_auth.py` | TERMINAL_TOKEN_EXPIRE_HOURS 追加 |
| `services/commons/src/kugel_common/security.py` | terminal JWT検証、クレーム→TerminalInfoDocument変換 |
| `services/commons/src/kugel_common/utils/terminal_auth.py` | 新規: terminal JWT生成ユーティリティ |
| `services/terminal/app/api/v1/auth.py` | 新規: POST /auth/token エンドポイント |
| `services/terminal/app/api/v1/terminal.py` | ライフサイクルAPIにX-New-Tokenヘッダー追加 |
| `services/terminal/app/main.py` | authルーター登録 |
| `services/cart/app/dependencies/terminal_cache_dependency.py` | JWT対応: JWTクレームからTerminalInfoDocument構築 |
| `services/cart/app/api/v1/tran.py` | JWT転送対応 |

## テスト実行
```bash
# 全サービスのテスト
./scripts/run_all_tests_with_progress.sh

# 個別サービス
cd services/terminal && pipenv run pytest tests/ -v
cd services/cart && pipenv run pytest tests/ -v
cd services/commons && pipenv run pytest tests/ -v
```
