# 実装計画: ターミナルAPIキーのライフサイクル対応JWT認証

**ブランチ**: `feature/67-terminal-jwt-auth` | **日付**: 2026-03-23 | **仕様書**: [spec.md](spec.md)
**入力**: `/specs/67-terminal-jwt-auth/spec.md` の機能仕様書

## サマリー

リクエスト毎のAPIキー検証（ターミナルサービスへのHTTP呼び出し）を、ライフサイクル対応JWTトークン認証に置き換える。ターミナルの状態変更時（open、sign-in、sign-out、close）にJWTを再発行し、各サービスでサービス間呼び出しなしにローカル検証を実現する。移行期間中は既存のAPIキー認証との後方互換性を維持する。

## 技術コンテキスト

**言語/バージョン**: Python 3.12+
**主要依存関係**: FastAPI, python-jose (JWT), Motor (MongoDB async), Dapr
**ストレージ**: MongoDB（Motor非同期ドライバー）
**テスト**: pytest, pytest-asyncio
**ターゲットプラットフォーム**: Linux サーバー (Docker/Azure Container Apps)
**プロジェクトタイプ**: マイクロサービス（7サービス + 共通ライブラリ）
**パフォーマンス目標**: JWT検証によるサービス間HTTP呼び出しの排除
**制約**: 既存APIキー認証との後方互換性維持
**規模**: 7サービス、共通ライブラリ1つ

## Constitution チェック

*GATE: Phase 0リサーチ前に通過必須。Phase 1設計後に再チェック。*

| ルール | 状態 | 備考 |
|--------|------|------|
| 成果物は日本語 | ✅ 通過 | 仕様書・計画書・タスクは日本語で作成 |
| コード内コメント・ログは英語 | ✅ 通過 | 実装時に遵守 |

## プロジェクト構造

### ドキュメント（この機能）

```text
specs/67-terminal-jwt-auth/
├── spec.md              # 機能仕様書
├── plan.md              # この実装計画書
├── research.md          # Phase 0 リサーチ結果
├── data-model.md        # Phase 1 データモデル
├── quickstart.md        # Phase 1 クイックスタート
├── contracts/           # Phase 1 APIコントラクト
│   └── terminal-auth-api.md
└── tasks.md             # Phase 2 タスク一覧（/speckit.tasks で生成）
```

### ソースコード（変更対象）

```text
services/
├── commons/src/kugel_common/
│   ├── config/
│   │   └── settings_auth.py          # TERMINAL_TOKEN_EXPIRE_HOURS 追加
│   ├── security.py                    # terminal JWT検証、クレーム→TerminalInfo変換
│   └── utils/
│       └── terminal_auth.py           # 【新規】terminal JWT生成ユーティリティ
├── terminal/app/
│   ├── api/v1/
│   │   ├── auth.py                    # 【新規】POST /auth/token エンドポイント
│   │   └── terminal.py                # ライフサイクルAPIにX-New-Tokenヘッダー追加
│   ├── dependencies/
│   │   └── get_terminal_service.py    # auth依存関係ラッパー追加
│   └── main.py                        # authルーター登録
├── cart/app/
│   ├── dependencies/
│   │   └── terminal_cache_dependency.py  # JWT対応: クレームからTerminalInfo構築
│   └── api/v1/
│       └── tran.py                    # JWT転送対応
├── master-data/app/                   # 変更なし（既存のtoken認証パスで動作）
├── report/app/
│   └── dependencies/
│       └── get_staff_info.py          # JWTクレームからstaff_id取得対応
├── journal/app/                       # 変更なし（既存のtoken認証パスで動作）
└── stock/app/                         # 変更なし（既存のtoken認証パスで動作）
```

**構造の決定**: 既存のマイクロサービス構造をそのまま活用。新規ファイルは `terminal_auth.py`（共通ユーティリティ）と `auth.py`（ターミナルサービスのエンドポイント）の2つのみ。主要な変更は `security.py` と `terminal_cache_dependency.py` への機能追加。

## 実装アプローチ

### フェーズ1: 共通基盤（kugel_common）

**1.1 settings_auth.py に設定追加**
- `TERMINAL_TOKEN_EXPIRE_HOURS: int = 24`

**1.2 terminal_auth.py（新規）: JWT生成ユーティリティ**
```python
def create_terminal_token(terminal_info: TerminalInfoDocument, expires_delta: timedelta = None) -> str
```
- TerminalInfoDocumentからJWTクレームを構築
- token_type="terminal", iss="terminal-service" を固定設定
- SECRET_KEY + HS256 で署名

**1.3 security.py: terminal JWT検証と後方互換**

新規関数:
```python
def verify_terminal_token(token: str) -> dict
    # token_typeが"terminal"であることを検証
    # 署名・有効期限を検証
    # クレームをdictで返す

def terminal_claims_to_terminal_info(claims: dict) -> TerminalInfoDocument
    # JWTクレームからTerminalInfoDocument互換オブジェクトを構築
```

既存関数の修正:
- `__get_tenant_id()`: tokenが提供された場合、まずterminal JWT（token_type="terminal"）を試行し、失敗したらユーザーJWTとして処理
- `get_terminal_info_with_api_key()` の代替: JWTが提供された場合はクレームからTerminalInfoDocumentを構築

### フェーズ2: ターミナルサービス

**2.1 auth.py（新規）: POST /auth/token エンドポイント**
- X-API-KEYヘッダーからAPIキーを取得
- DBでターミナル情報をルックアップ（api_keyで検索）
- TerminalInfoDocumentからJWT生成
- `{"access_token": token, "token_type": "bearer", "expires_in": seconds}` を返却

**2.2 terminal.py: ライフサイクルAPIの修正**
- open, sign-in, sign-out, close の各エンドポイント
- 操作成功後、更新された TerminalInfoDocument から新JWT生成
- `X-New-Token` レスポンスヘッダーに設定
- レスポンスボディは変更なし

**2.3 main.py: ルーター登録**
- `auth_router` を `/api/v1` プレフィックスで登録

### フェーズ3: Cartサービス

**3.1 terminal_cache_dependency.py: JWT対応**
- 新しい依存関数: JWTが提供された場合、クレームからTerminalInfoDocumentを構築（HTTP呼び出しなし）
- APIキーが提供された場合、既存のキャッシュ付きフロー（後方互換）
- `get_terminal_info_with_jwt_or_cache()` を追加

**3.2 Webリポジトリ: JWT転送**
- `PaymentMasterWebRepository`, `ItemMasterWebRepository`, `SettingsMasterWebRepository`
- TerminalInfoDocumentに jwt_token フィールドを追加（オプション）
- JWT利用可能時: `Authorization: Bearer <jwt>` ヘッダーで master-data を呼び出し
- JWT未利用時: 既存の `X-API-KEY` ヘッダー（後方互換）

### フェーズ4: Reportサービス

**4.1 get_staff_info.py: JWTクレーム対応**
- `get_requesting_staff_id()` を修正
- tokenがterminal JWT の場合、クレームから直接 staff_id を取得（terminal_info取得不要）

### フェーズ5: テスト

**5.1 共通ライブラリテスト**
- JWT生成・検証のユニットテスト
- クレーム→TerminalInfoDocument変換テスト
- 有効期限切れ、不正署名、token_type不一致のテスト

**5.2 ターミナルサービステスト**
- POST /auth/token の正常系・異常系テスト
- ライフサイクルAPI（open, sign-in, sign-out, close）のX-New-Tokenヘッダーテスト

**5.3 Cartサービステスト**
- JWT提供時のTerminalInfoDocument構築テスト
- JWT転送でのmaster-data呼び出しテスト
- APIキー提供時の既存フロー（後方互換）テスト

**5.4 既存テストの維持**
- 全既存テストがパスすることを確認

## 検証方法

1. **ユニットテスト**: 各サービスの `pipenv run pytest tests/ -v`
2. **統合テスト**: `./scripts/run_all_tests_with_progress.sh`
3. **手動テスト**: quickstart.md の curl コマンドで認証フローを確認
4. **後方互換確認**: 既存のAPIキー認証でのリクエストが動作すること

## Complexity Tracking

Constitution チェックに違反はないため、このセクションは空。
