# データモデル: ターミナルJWT認証

**ブランチ**: `feature/67-terminal-jwt-auth` | **日付**: 2026-03-23

## ターミナルJWTクレーム

JWTペイロードに含まれるクレーム。既存の `TerminalInfoDocument` の主要フィールドをマッピング。

| クレーム | 型 | 必須 | 説明 | TerminalInfoDocumentマッピング |
|---------|-----|------|------|-------------------------------|
| sub | str | YES | ターミナル識別子 (`terminal:{terminal_id}`) | terminal_id |
| tenant_id | str | YES | テナントID | tenant_id |
| store_code | str | YES | 店舗コード | store_code |
| terminal_no | str | YES | ターミナル番号 | terminal_no |
| terminal_id | str | YES | ターミナルID（tenant_id-store_code-terminal_no） | terminal_id |
| staff_id | str | NO | サインイン中のスタッフID（未サインイン時はnull） | staff.id |
| staff_name | str | NO | サインイン中のスタッフ名（未サインイン時はnull） | staff.name |
| business_date | str | NO | 営業日（YYYYMMDD形式、オープン後に設定） | business_date |
| open_counter | int | NO | オープンカウンター（オープン後に設定） | open_counter |
| business_counter | int | NO | 営業カウンター（オープン後に設定） | business_counter |
| status | str | YES | ターミナル状態（Idle, Opened, Closed等） | status |
| iss | str | YES | 発行者（固定値: "terminal-service"） | - |
| token_type | str | YES | トークン種別（固定値: "terminal"） | - |
| iat | int | YES | 発行日時（UNIXタイムスタンプ） | - |
| exp | int | YES | 有効期限（UNIXタイムスタンプ） | - |

## 状態遷移とクレーム更新

```
POST /auth/token (APIキー → JWT)
  → status=現在の状態, staff_id=null(未サインイン時)

POST /terminals/{id}/open
  → status="Opened", business_date=当日, open_counter++, business_counter++

POST /terminals/{id}/sign-in
  → staff_id=スタッフID, staff_name=スタッフ名

POST /terminals/{id}/sign-out
  → staff_id=null, staff_name=null

POST /terminals/{id}/close
  → status="Closed"
```

## 設定項目（settings_auth.py への追加）

| 設定名 | 型 | デフォルト値 | 説明 |
|--------|-----|-------------|------|
| TERMINAL_TOKEN_EXPIRE_HOURS | int | 24 | ターミナルJWTの有効期限（時間） |

## 既存エンティティへの影響

### TerminalInfoDocument
変更なし。既存の構造はそのまま維持。JWTクレームは TerminalInfoDocument のフィールドのサブセット。

### AuthSettings（settings_auth.py）
`TERMINAL_TOKEN_EXPIRE_HOURS` フィールドを追加。
