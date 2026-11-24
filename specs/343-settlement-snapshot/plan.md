# Implementation Plan: 精算を report が確定するスナップショットにする

**Branch**: `343-settlement-snapshot` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/343-settlement-snapshot/spec.md`

## Summary

端末の精算のとき、terminal が report の内部の口に精算の確定を頼む。report は、その時点で届いている取引・入出金を、締めの時刻で絞った同じ集合として読み（R-12）、精算実績を作って営業ごとに1件保存する。精算実績は、その営業の閉設ログが report に届くまで「仮」で、もう一度精算されたら作り直し、閉設ログが届いたら「確定」して変えない（R-2・R-6）。精算実績には、理論在高（売上レポートと共有する1か所の式・R-3）、取引と入出金の未着・重複（R-13）、5種類の確定集計（営業の番号で絞り、件数の区切りなし・別のコレクション・R-4・R-17）を持たせる。集計に1つでも失敗したら保存せずに断る（R-15）。日報（daily）は確定した精算実績の確定集計から返し、店舗・期間は合算する。未精算の営業があれば `412101` で断り、一覧を返す（R-5・R-14・R-16）。terminal は cart への問い合わせをやめ、report で確定できなければ `406016`（503）で断る（R-7）。照会の一覧と、terminal を通した精算前の確認の口を足す（R-8）。

## Technical Context

**Language/Version**: Python 3.12+（全サービス共通）
**Primary Dependencies**: FastAPI、Pydantic v2、PyMongo 非同期 API、commons の `AbstractRepository`・`insert_if_absent`・`get_service_account_info`・`create_service_token`・`get_service_client`。新しい外部依存は無い
**Storage**: テナントごとの MongoDB。report に `settlement_record` と `settlement_daily_report` を新設。`log_tran`・`log_cash_in_out`・`log_open_close` に索引を足す（R-18）。閉設ログに任意の項目を足す。精算の計算は、締めの時刻（届いた時刻 `created_at`）で絞った同じ集合のデータで行う（R-12）
**Testing**: pytest。unit / integration（実際の MongoDB）/ e2e（スタック）、サービス横断の e2e。cart の e2e は DUAL と REQUIRED
**Target Platform**: Linux のコンテナ（docker-compose、Azure Container Apps）
**Project Type**: マイクロサービスのバックエンド
**Performance Goals**: 精算の要求の処理時間に、5種類の日報の集計が1回ずつ加わる。大きな営業（取引 2,000 件・商品 1,000 品目程度）で確定の口が 10 秒以内（terminal のタイムアウト 30 秒より十分短い）。T042a で測る
**Constraints**: 精算実績は作られたら変わらない。report に届かなければ精算しない。既存のクライアント（`seq` を送らない）は今までどおり精算できる
**Scale/Scope**: report・terminal の2サービス。commons は変えない（R-3・R-16）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 項目 | 判定 | 根拠 |
|---|---|---|
| 言語規則（成果物は日本語、コードのコメント・ログは英語） | ✅ | spec〜quickstart は日本語。docs は en/ja |
| リポジトリパターン・DB 操作は async | ✅ | `SettlementRecordRepository` を `AbstractRepository` の上に作る |
| 型ヒント必須 | ✅ | |
| API: `/api/v1/`、Pydantic のスキーマ、Transformer | ✅ | 内部の口は master-data の `internal.py` の形。一覧は既存の照会の形 |
| エラーコード XXYYZZ、サービスの範囲 | ✅ | report は 412/413、terminal は 406（R-9） |
| テストの3段階 | ✅ | 計算は unit、保存・先勝ち・日報は integration、精算の流れは e2e |
| 秘密情報をコミットしない | ✅ | 関係なし |

**Post-design re-check**: ✅

## Project Structure

### Documentation (this feature)

```text
specs/343-settlement-snapshot/
├── spec.md
├── plan.md
├── research.md          # R-1〜R-19
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── report-settlement-api.md
│   └── terminal-close.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
services/report/app/
├── api/v1/settlement_internal.py        # 新規: 確定・確認（サービスアカウント）
├── api/v1/settlement.py                 # 新規: 一覧
├── api/v1/schemas.py, schemas_transformer.py   # 要求・応答
├── main.py                              # ルーターの登録
├── database/database_setup.py           # settlement_record と索引、log_cash_in_out の索引
├── main.py                              # SessionNotSettledException の専用の処理（R-16）
├── models/documents/settlement_record_document.py     # 新規（仮・確定）
├── models/documents/settlement_daily_report_document.py # 新規（確定集計、種類ごと）
├── models/repositories/settlement_record_repository.py # 新規（仮の置き換え、確定、照会）
├── services/log_service.py              # 閉設ログで精算実績を確定する
├── services/expected_cash.py            # 新規: 理論在高の式（R-3）
├── services/settlement_counting.py      # 新規: 届いた件数・番号の系列・範囲・未着・重複（R-2・R-13、純粋な関数）
├── services/settlement_service.py       # 新規: 確定・確認・一覧・確定集計
├── services/report_service.py           # daily を確定集計から。未精算の判定。DailyInfo を外す
├── services/plugins/*_report_maker.py   # business_counter の絞り込み、区切りなし、merge / from_saved。sales は expected_cash を使う
├── models/documents/*_report_document.py # missing_count / missing_ranges
├── dependencies/                        # SettlementService の組み立て
└── exceptions/report_error_codes.py, report_exceptions.py   # 412101 の意味、413007

services/terminal/app/
├── models/repositories/settlement_web_repository.py   # 新規: report への確定・確認の依頼（タイムアウト 30 秒、再試行 1 回）
├── api/v1/terminal.py                   # close-preview の口（新規）
├── services/terminal_service.py         # close_terminal_async の順番と条件付きの更新（R-7）。cart への問い合わせを外す。close-preview
├── api/common/schemas.py, api/v1/schemas.py, schemas_transformer.py   # seq、応答の項目
├── services/receipt_data/open_close_receipt_data.py   # 3行
├── models/documents/open_close_log.py（terminal・report・journal の閉設ログの型）
└── exceptions/terminal_error_codes.py, terminal_exceptions.py        # 406016

docs/{en,ja}/general/error_code_spec.md、docs/{en,ja}/report|terminal/api-specification.md（生成）
```

**Structure Decision**: 精算実績は report の中で完結させる。計算（件数・未着）は純粋な関数に分け、unit で網羅する。terminal は report を呼ぶ1つのリポジトリを足すだけにする。

## Implementation Phases（tasks.md の骨組み）

1. **report の土台**: 文書・リポジトリ（仮・確定）・索引・エラーコード・理論在高の式（売上レポートの置き換えを含む）・件数と番号の系列の計算・プラグインの business_counter の絞り込みと区切りなし
2. **精算の確定（US1 の report 側）**: SettlementService の確定（締めの時刻で絞った計算、確定集計の作成と現金の欄の上書き・レシートの作り直し、集計の失敗で断る、大きさの確認）、内部の口、閉設ログでの確定
3. **terminal の精算（US1・US5）**: report への依頼、`seq` と入出金の件数、閉設ログ・レシート・応答、`406016`、条件付きの更新、cart への問い合わせを外す
4. **日報（US2）**: 各プラグインの `merge` / `from_saved`、daily を確定した確定集計から、未精算の判定と一覧（専用の例外の処理）、空の範囲、未着の項目、DailyInfo を外す
5. **確認の口（US3、report の内部の口と terminal の close-preview）と一覧（US4）**
6. **既存のテストの書き直しと、レビューで足したテスト**（R-19）
7. **全体の確かめと文書**: 全テスト（cart は DUAL・REQUIRED）、エラーコードの文書、API の文書の生成、CLAUDE.md

## 利用者に確かめる事項（plan の段）

- **配備より前に精算を終えた営業の日報**: 精算実績が無いので `412101` になる（R-11）。→ **確認済み（2026-11-24）**: 配備の直後に前日分の日報を出す運用は無い。期間の日報を含めて、出せなくてよい
- **確定の境界**（レビューで判明）: 仮の精算実績にする（R-6）— 確認済み
- **集計の失敗**: 精算を断ってやり直す（R-15）— 確認済み
- **閉設済みの端末への再送**: 今どおり `406003`（端末の状態のエラー。既存の挙動）（R-7）— 確認済み

## Complexity Tracking

違反はない。
