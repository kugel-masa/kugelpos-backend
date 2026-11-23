# Implementation Plan: 端末サインインでの従業員 PIN の照合

**Branch**: `323-staff-pin-verification` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/323-staff-pin-verification/spec.md`
**Issue**: [#323](https://github.com/kugel-masa/kugelpos-backend/issues/323)

## Summary

端末のサインインで、PIN を登録した従業員の PIN を照合する。

- **master-data**: 内部専用の `POST /api/v1/internal/tenants/{tenant_id}/staff/{staff_id}/verify` を新設する
  - サービスアカウントの JWT だけを受け付け、テナントの一致を検査する
  - 判定（従業員なし 405701・PIN が要る 405702・不一致 405703・それ以外は成功）と定数時間の比較は、`StaffMasterService.verify_staff_async` の 1 か所だけで行う
  - 応答は `id` と `name` だけで、PIN を型に持たない
  - 従業員の登録・更新で `pin` を省略できるようにする（これまで必須だったため、ダミーの PIN が入った従業員が多い。R-10）
- **commons**: `StaffMasterWebRepository.verify_staff_async(staff_id, pin)` を足す
  - サービスアカウントのトークンで呼び、従業員コードは符号化してパスに埋め込む
  - 業務コード 405701〜405703 だけを `StaffAuthenticationException`（理由付き）にし、それ以外は `RepositoryException` のまま返す
- **terminal**: サインインの要求に任意の `pin` を足し、照合で従業員を得る
  - 失敗 3 種類は既存の `SignInOutException`（406004 / 401）に揃え、応答の本文（最上位の `message` を含む）を同じにする。理由はログにだけ残す
  - サインインの要求を記録する DEBUG ログで `pin` を伏せる（今は要求をそのまま出している）
  - 照合を判定できないときは `ExternalServiceException`（407201 / 502）にする

保存する文書の形は変えない。PIN は平文のまま（ハッシュ化・回数制限は別の Issue で、照合の 1 か所へ足す）。

## Technical Context

**Language/Version**: Python 3.12+（他のサービスと同じ）
**Primary Dependencies**: FastAPI、Pydantic v2、Motor（MongoDB 非同期）、`HttpClientHelper`（`get_service_client`）、PyJWT（既存のサービスアカウントのトークン）。新しい外部依存なし（比較は標準の `secrets`）
**Storage**: テナントごとの MongoDB。`master_staff`・`info_terminal` の形は変えない
**Testing**: pytest（unit / integration / e2e の 3 層）、pytest-asyncio
**Target Platform**: Linux コンテナ（Docker Compose・Azure Container Apps）
**Project Type**: マイクロサービス（`services/<service>/app`）
**Performance Goals**: サインイン 1 回につき master-data への呼び出しが 1 回（今の取得と同じ回数）。比較は定数時間で数マイクロ秒
**Constraints**:
- PIN を省略した既存の要求はそのまま受け付ける（spec FR-013）
- PIN は保存しない・応答に出さない・ログに出さない（DEBUG を含む）。端末から送る先はマスタの照合だけ
- 存在しない従業員の応答（406004 / 401）は変えない
**Scale/Scope**: サインインの頻度（端末ごとに 1 日数回〜数十回）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` で定まっている原則は「0. 言語規則」だけ（他は雛形のまま）。CLAUDE.md の規約を合わせて確認する。

| 項目 | 判定 | 根拠 |
|---|---|---|
| 言語規則（成果物は日本語、コードのコメント・ログは英語） | ✅ | spec・plan・research・data-model・contracts・quickstart は日本語。コードは英語で書く |
| API は `/api/v1/` で版付け、Pydantic のスキーマ、Transformer で変換 | ✅ | 内部用も `/api/v1/internal/...`。要求・応答のスキーマと Transformer を足す |
| API 命名規約（複数形・snake_case のパス引数・アクションは POST） | ✅ | `POST .../staff/{staff_id}/verify`。`staff` は集合名詞のまま |
| リポジトリパターン・DB 操作は async | ✅ | 既存の `get_staff_by_id_async` を使う。新しい DB 操作なし |
| エラーコード XXYYZZ・サービスの範囲 | ✅ | master-data は 405 帯（405701〜405703、未使用）。terminal は既存の 406004・407201 |
| セキュリティ（秘密をコミットしない・資格情報をログに出さない） | ✅ | PIN は応答の型に無く、ログは既存の伏せ処理（#211・#316・#318）を通る |
| テストの 3 層 | ✅ | unit（判定・写像）、integration（実 MongoDB の master-data）、e2e（サインインの通し） |
| コメントアウトしたコードを残さない・型ヒント | ✅ | 実装時に守る |

**Phase 1 後の再確認**: 設計（data-model・contracts）は上の項目に反しない。違反なし。Complexity Tracking は不要。

## Project Structure

### Documentation (this feature)

```text
specs/323-staff-pin-verification/
├── spec.md
├── plan.md              # このファイル
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── master-data-staff-verify.md
│   └── terminal-sign-in.md
├── checklists/requirements.md
└── tasks.md             # Phase 2（/speckit.tasks が作る）
```

### Source Code (repository root)

```text
services/master-data/app/
├── api/v1/internal.py                         # 新規: POST /internal/tenants/{tenant_id}/staff/{staff_id}/verify
├── api/common/schemas.py                      # BaseStaffCreateRequest / BaseStaffUpdateRequest の pin を任意に
├── api/v1/schemas.py                          # StaffVerifyRequest・StaffVerifyResponse
├── api/v1/schemas_transformer.py              # transform_staff_verification（PIN を射影しない）
├── services/staff_master_service.py           # verify_staff_async（判定と比較の唯一の場所）
├── exceptions/master_data_error_codes.py      # 405701〜405703（日英）
├── exceptions/master_data_exceptions.py       # StaffVerify*Exception 3 種
├── exceptions/__init__.py                     # 公開
└── main.py                                    # internal ルーターの登録

services/commons/src/kugel_common/
├── enums.py                                   # StaffAuthenticationFailure
├── exceptions/…                               # StaffAuthenticationException
└── models/repositories/staff_master_web_repository.py  # verify_staff_async（パスの符号化）

services/terminal/app/
├── api/common/schemas.py                      # BaseTerminalSignInRequest.pin（任意）
├── api/v1/terminal.py                         # sign_in_terminal_async に pin を渡す・DEBUG ログで pin を伏せる
└── services/terminal_service.py               # 照合で従業員を得る・失敗の写像とログ

services/*/Pipfile, Pipfile.lock               # commons の版上げ（kugel_common の項目だけ）
services/{master-data,report}/tests/e2e/test_setup_data.py  # S001 を PIN なしに。PIN 付きの従業員を追加
docs/{en,ja}/master-data, docs/{en,ja}/terminal # API 仕様の更新
```

**Structure Decision**: 既存のマイクロサービス構成のまま。master-data に内部用ルーターを 1 つ足す以外、新しい構造は作らない。

## Phase 0: Research

[research.md](research.md) に記録した。要点:

- R-1: サービスアカウントの JWT（`create_service_token` / `get_service_account_info` / `verify_tenant_id`）を使う
- R-2: `app/api/v1/internal.py`、パスは `.../verify`（PIN だけの照合ではないため）
- R-3: 従業員は物理削除。「従業員なし」は `None` の 1 通り
- R-4: 端末の失敗は既存の 406004 / 401 に揃える（存在しない従業員の応答を変えない）
- R-5: 業務コードだけで判定し、それ以外は障害（407201 / 502）
- R-6: `secrets.compare_digest` を bytes で
- R-7: 応答の型に PIN を持たせない・失敗は `details` なし
- R-9: `get_staff_by_id_async` は commons に残す。サインインからは使わない
- R-10: 登録・更新の `pin` を任意にし、e2e の S001 を PIN なしにする（ダミーの PIN 問題）
- R-11: 従業員コードを符号化して内部の URL に埋め込む
- R-12: 成功の応答は `id` と `name` だけ
- R-13: すでにサインインしている端末には遡らない
- R-14: 列挙で防げるのは PIN の有無と一致度だけ（存在と名前は防げない）と明記

未解決の項目はない。

## Phase 1: Design

- [data-model.md](data-model.md): 判定、スキーマ、例外とコード
- [contracts/master-data-staff-verify.md](contracts/master-data-staff-verify.md): 内部の照合
- [contracts/terminal-sign-in.md](contracts/terminal-sign-in.md): サインインの変更
- [quickstart.md](quickstart.md): 起動したスタックでの確認手順

## テスト方針

| 層 | 対象 |
|---|---|
| unit（master-data） | 判定表の全行、空文字・空白だけ・ASCII 以外の PIN、応答に PIN の項目が無いこと、ログに PIN が出ないこと、登録・更新で PIN を省略できること |
| unit（master-data API） | サービスアカウントで 200、端末の JWT で 403、API キーだけで 401、テナント不一致で 400 |
| unit（commons） | 405701〜405703 の写像（実際の camelCase の応答本文 `userError` で）、5xx・接続失敗・コードの無い 404 は `RepositoryException` のまま、要求本文に PIN が載りクエリに載らないこと、`/` や `..` を含む従業員コードでパスが変わらないこと、例外の文字列に PIN が出ないこと |
| unit（terminal） | PIN あり／なしの従業員 × PIN あり／なし、失敗 3 種類で応答の本文全体が同じ、障害（`RepositoryException`・URL 未設定）は 407201、失敗で端末の状態が変わらない、すでにサインイン済みなら照合を呼ばない、DEBUG を有効にして一意で長い PIN がどのログにも出ないこと |
| integration（master-data） | 実 MongoDB で判定表 |
| e2e（terminal・横断） | 実スタックでのサインイン（PIN あり：正・誤・なし、PIN なし：なし・任意）、照合を端末の資格情報で直接呼べないこと。準備データの S001 は PIN なしにし、既存のサインインのテストはそのまま通ること |

## リリース

- commons の版を上げ、7 サービスの Pipfile・lock は `kugel_common` の項目だけを変える
- リリースノートに挙動の変化を書く: PIN が入っている従業員は PIN が要る。これまで PIN が必須だったためダミーの PIN が入った従業員が多いので、PIN なしでサインインさせたい従業員は PIN を空にする

## Complexity Tracking

違反なし。記載不要。
