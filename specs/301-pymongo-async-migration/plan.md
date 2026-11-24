# Implementation Plan: Motor から PyMongo Async API への移行

**Branch**: `301-pymongo-async-migration` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/301-pymongo-async-migration/spec.md`

## Summary

7サービスと kugel_common を、Motor から PyMongo の非同期 API（`pymongo.AsyncMongoClient`）に移す。挙動は変えない。

大部分は名前の置き換え（R-4）で済む。書き方が変わるのは、セッションの開始、集計、`list_indexes`、接続の終了の数か所だけ（R-3）で、それぞれに実際の MongoDB でのテストを付ける。stock のスケジューラーが呼ばれるたびに接続を作っている箇所は、共有の接続を使うように直す（R-6）。

出し方は1つの PR（R-1）。移行前後で標準の性能テストを走らせて比べる（R-7）。下流のツリー向けの移植の手順書を docs に置く（R-8）。

## Technical Context

**Language/Version**: Python 3.12+（全サービス共通）
**Primary Dependencies**: FastAPI、Pydantic v2、PyMongo 4.20（非同期 API、宣言は `>=4.13`）。Motor は外す。新しい依存はない（PyMongo は Motor の依存として既に入っている）
**Storage**: テナントごとの MongoDB のデータベース（変更なし）。データの形式とインデックスも変更なし
**Testing**: pytest + pytest-asyncio。unit / integration（実際の MongoDB）/ e2e（docker-compose のスタック）、サービス横断の e2e。cart の e2e は DUAL と REQUIRED の両方
**Target Platform**: Linux のコンテナ（docker-compose、Azure Container Apps）
**Project Type**: マイクロサービスのバックエンド（7サービス＋共通ライブラリ）
**Performance Goals**: 移行前と同等。標準の性能テストの主要な指標の劣化が 10% 以内（超えたら説明か対処）
**Constraints**: 1つの接続は作ったイベントループからだけ使う。データの移行なし。2027-05-14 より十分前に main に入れる
**Scale/Scope**: Motor を読み込むファイルはアプリ側 42、テスト側 21〜30（数え方による、R-4）、性能テスト 1。型の参照は約150か所

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` で定まっている原則は「0. 言語規則」だけ（他は雛形のまま）。CLAUDE.md の規約を合わせて確認する。

| 項目 | 判定 | 根拠 |
|---|---|---|
| 言語規則（成果物は日本語、コードのコメント・ログは英語） | ✅ | spec・plan・research・data-model・contracts・quickstart は日本語。docs の移植の手順書は en/ja の両方（docs は英語が主） |
| リポジトリパターン・DB 操作は async | ✅ | 変更なし。ドライバだけを替える |
| 型ヒント必須 | ✅ | Motor の型を PyMongo の型に置き換える（R-4） |
| API・エラーコード | ✅ | 変更なし（FR-001） |
| テストの3段階（unit / integration / e2e） | ✅ | 書き方が変わる箇所は integration（実際の MongoDB）で確かめる（FR-014） |
| 秘密情報をコミットしない | ✅ | 関係なし |

**Post-design re-check**: ✅（設計で新しい違反は出ていない）

## Project Structure

### Documentation (this feature)

```text
specs/301-pymongo-async-migration/
├── spec.md
├── plan.md              # このファイル
├── research.md          # R-1〜R-11
├── data-model.md        # データの変更なし。接続とセッションの扱い
├── quickstart.md        # 確かめ方
├── contracts/
│   └── driver-behaviour.md   # 移行の前後で保つ挙動
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks で作る
```

### Source Code (repository root)

```text
services/commons/
├── pyproject.toml                         # motor → pymongo>=4.13
├── Pipfile / Pipfile.lock                 # motor を外す、pymongo>=4.13（R-9）
└── src/kugel_common/
    ├── database/database.py               # AsyncMongoClient、作ったループを覚える、ループごとのロック、close を await、集計を await
    ├── database/index_startup.py ほか      # 型の置き換え
    └── models/repositories/abstract_repository.py   # セッション、集計、型
services/commons/tests/
├── unit/                                  # 偽の aggregate を async に、AsyncMongoClient の差し替え（R-4）
└── integration/                           # 新規（R-11）: 集計、セッション、終了とループ、件数 0
scripts/run_integration_tests.sh           # commons を足す（R-11）

services/{account,terminal,master-data,cart,report,journal,stock}/
├── Pipfile / Pipfile.lock                 # motor を外す、pymongo>=4.13、commons 0.1.122
├── app/**                                 # 型の置き換え（約42ファイル）
│   └── (stock) services/multi_tenant_snapshot_scheduler.py   # 共有の接続を使う
│   └── (stock) models/repositories/stock_snapshot_repository.py  # list_indexes を await
└── tests/**                               # クライアントの作成、同じループでの後始末、モックの差し替え（R-4、R-6）

services/cart/performance_tests/cleanup_test_data.py   # 性能テストの補助

docs/{en,ja}/general/pymongo-async-migration.md   # 移植の手順書（新規）
docs/** と CLAUDE.md                               # 「Motor」の記述を更新
```

**Structure Decision**: 新しいモジュールは作らない。既存のファイルの中で、ドライバの名前と、書き方が変わる呼び出しだけを直す。

## Implementation Phases（tasks.md の骨組み）

1. **移行前の計測**: 移行前の main で標準の性能テストを走らせ、数字を残す（R-7）
2. **commons**: 接続の作成・終了（作ったループを覚える、ループごとのロック、R-6）、セッション、集計、型。unit の偽の実装と差し替えを直す（R-4）。`tests/integration` を作り、`run_integration_tests.sh` に commons を足す（R-11）。実際の MongoDB でのテスト（集計、セッションの commit / abort / `async with`、終了とループ、件数 0）。wheel 0.1.122
3. **サービス**: 7サービスの型の置き換え、stock のスケジューラー（共有の接続）と `list_indexes`、テストのクライアント・同じループでの後始末・モック（R-4、R-6 の一覧）。cart・journal・terminal のセッションを実際の MongoDB で通す。サービスごとに unit / integration を通す
4. **依存**: Pipfile・ロック・pyproject から Motor を外す（R-9）。`pipenv verify`、空の環境での `pipenv install --deploy`、`pip check`。`grep -rn -i motor` が 0 件
5. **全体の確かめ**: 全イメージを作り直し、unit / integration（`-W error::RuntimeWarning` でも、R-10）/ e2e、サービス横断の e2e。cart は DUAL（96件）と REQUIRED（再起動して `printenv` でモードを確かめ、48件が通り48件が除外）。スタックを止めたときのログに閉じ忘れや例外がない（R-10）
6. **移行後の計測**: 同じ条件で性能テスト、比べて PR に載せる
7. **ドキュメント**: 移植の手順書（en/ja、検索項目は R-8）、CLAUDE.md と docs の「Motor」

## Complexity Tracking

違反はない。
