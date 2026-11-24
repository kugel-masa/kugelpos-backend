---
description: "Task list for 301-pymongo-async-migration"
---

# Tasks: Motor から PyMongo Async API への移行

**Input**: `/specs/301-pymongo-async-migration/` の plan.md、spec.md、research.md（R-1〜R-11）、data-model.md、contracts/driver-behaviour.md（C-1〜C-11）、quickstart.md
**Tests**: 必要（FR-013、FR-014）。書き方が変わる箇所は、直す前に実際の MongoDB でのテストを書く

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並べて進められる（別のファイル、未完了のタスクに依存しない）
- **[Story]**: US1（挙動が変わらない）、US2（移植の手順書）、US3（性能）

---

## Phase 1: Setup（移行前の基準を取る）

**Purpose**: 移行前の数字と件数を残す。移行に手を付ける前に終える

- [X] T001 移行前の main（33186ed7）で標準の性能テスト（`/perf-test`）を走らせ、条件（ユーザー数・時間・データ）と主要な指標（中央値・p95・スループット・失敗率）を specs/301-pymongo-async-migration/perf-baseline.md に記録する（R-7）
- [X] T002 T001 のあとで（同じスタックと MongoDB を使うので並べない）、移行前の各サービスの unit / integration / e2e の件数（passed / skipped / deselected）、cart の DUAL（96）と REQUIRED（48/48）、サービス横断の e2e の件数を specs/301-pymongo-async-migration/test-baseline.md に記録する（SC-001 の比較用）。e2e のあと、テナントのデータベースごとのコレクションと `index_information()` を 作業用のディレクトリ（リポジトリの外）の indexes-before.json に書き出す。このリポジトリのサービスのデータベース（`db_account` / `db_terminal` / `db_master` / `db_cart` / `db_report` / `db_journal` / `db_stock` / `db_common`）だけを対象にし、ファイルはコミットしない（FR-003）
- [X] T003a 移行前のイメージのまま、e2e のスタックに互換確認用のテナント（例: `T3010`）を作り、サインイン・開設・商品登録・会計・取消・入出金・締めを1通り行う。MongoDB のボリュームは移行後まで消さない（FR-002、SC-003）
- [X] T003 [P] `grep -rli motor --include=*.py services --exclude-dir=.venv` と型の参照（`grep -rn -i -o "AsyncIOMotor[A-Za-z]*"`）を数え直し、test-baseline.md に残す（R-4）

**Checkpoint**: 基準の数字がそろった

---

## Phase 2: Foundational（commons、0.1.122）

**Purpose**: 7サービスが使う commons を PyMongo に移す。サービスの作業は、これが終わるまで始めない

**⚠️ CRITICAL**: 全サービスがこの wheel に依存する

### commons の統合テストの土台（R-11）

- [X] T004 services/commons/tests/integration/__init__.py と services/commons/tests/integration/conftest.py を作る。`MONGODB_URI` を使い、テスト用のデータベースの名前を fixture が作るときに一度だけ決め（接頭辞 `commons_it_` を assert）、後始末ではその名前だけを消す。各テストの終わりに、同じループで `await close_client_async()` する。pytest の marker の自動付与はサービスの integration の conftest に合わせる
- [X] T005 scripts/run_integration_tests.sh の `ALL_SERVICES` に `commons` を足す。スクリプトは各サービスで `pipenv run pytest -m integration` を走らせるので、T004 の conftest で commons の integration のテストに `integration` の marker が付くことを確かめる

### 書き方が変わる箇所のテスト（先に書き、移行前のコードで落ちることを確かめる）

- [X] T006 [P] services/commons/tests/integration/test_pymongo_aggregate.py: `AbstractRepository.execute_pipeline` と database.py の集計の補助（:341 付近）が、実際の MongoDB で期待の結果を返す（C-5）
- [X] T007 [P] services/commons/tests/integration/test_pymongo_session.py: `start_transaction()` で commit した書き込みは残り、abort した書き込みは残らない。`async with await repo.start_transaction()` を抜けるとセッションが終わる（C-6、R-3 の付け忘れを拾う形）
- [X] T008 [P] services/commons/tests/integration/test_pymongo_client_lifecycle.py: 同じループで閉じる、二重に閉じても落ちない、別のループから `close_client_async` / `reset_client_async` を呼ぶと `close()` せずに警告を残して参照を捨てる、`get_client_async` がループが変わると作り直す、`_client_lock` がループごとに働く（C-7、C-8、R-6）
- [X] T009 [P] services/commons/tests/integration/test_pymongo_limit_zero.py: `get_all_async` / `get_list_async` の `max=0` が上限なしで返る。`cursor.to_list(0)` が `ValueError` になることを固定する（C-4、R-5）

### commons の実装

- [X] T010 services/commons/src/kugel_common/database/database.py: `AsyncMongoClient` に替える。接続と一緒に作ったループを覚え、`_client_lock` をループごとに持つ。`close_client_async` / `reset_client_async` は同じループなら `await client.close()`、違うループなら警告して参照を捨てる。集計を `await` する。型を `AsyncDatabase` / `AsyncCollection` に替える（R-3、R-4、R-6）
- [X] T011 services/commons/src/kugel_common/models/repositories/abstract_repository.py: `start_session()` を `await` せず、`await session.start_transaction()` にする。`execute_pipeline`（:558 付近）の `aggregate` を `await` する。型を替える
- [X] T012 [P] services/commons/src/kugel_common/utils/terminal_api_key.py、utils/health_check.py、models/repositories/request_log_repository.py の Motor の型を替える（R-4。commons で Motor を読み込むのは T010・T011 の2つとこの3つ）
- [X] T013 [P] services/commons/tests/unit/test_repository_update_masking.py（:45、:191）の偽の `aggregate` を `async def` にする。services/commons/tests/unit/test_database_uri_redaction.py（:53）の差し替えを `database.AsyncMongoClient` にし、偽が呼ばれたことを assert する。ほかの unit の Motor の型の spec と、`aggregate` / `close` の `MagicMock` を `AsyncMock` にする（R-4）
- [X] T014 services/commons/pyproject.toml の `motor` を外して `pymongo>=4.13` にする。services/commons/Pipfile（:10 `motor = "*"`）から motor を外して `pymongo = ">=4.13"` を足し、services/commons/Pipfile.lock（:697 の motor の項目）を R-9 のやり方で直して `pipenv verify` を通す。services/commons/src/kugel_common/__about__.py を 0.1.122 にする（R-2、FR-011）
- [X] T015 commons の unit と integration（T006〜T009）を通す。`-W error::RuntimeWarning` でも通す（R-10）
- [X] T016 `./scripts/run_build_common.sh` → `./scripts/run_copy_common.sh` で wheel 0.1.122 を作り、7サービスに配る

**Checkpoint**: commons 0.1.122 の wheel ができ、commons の unit / integration が通る

---

## Phase 3: User Story 1 - 移行しても POS の業務がそのまま動く (Priority: P1) 🎯 MVP

**Goal**: 7サービスを PyMongo に移し、既存のテストが移行前と同じ件数で通る
**Independent Test**: T002 の件数と同じか多い件数で、全サービスの unit / integration / e2e、サービス横断の e2e、cart の DUAL / REQUIRED が通る

### サービスごとの移行（サービス同士は並べて進められる。各タスクは「app の型の置き換え → tests の差し替えと後始末 → Pipfile / ロック（R-9: motor を消し `pymongo = ">=4.13"`、ロックの pymongo に `"index": "pypi"`、kugel-common 0.1.122 のファイル名とハッシュ、`_meta` のハッシュ）→ venv に wheel を入れ直す → unit / integration」）

- [X] T017 [P] [US1] account: services/account/app（1ファイル）、services/account/tests（2ファイル）、services/account/Pipfile、Pipfile.lock
- [X] T018 [P] [US1] master-data: services/master-data/app（9ファイル）、services/master-data/tests（1ファイル）、Pipfile、Pipfile.lock
- [X] T019 [P] [US1] report: services/report/app（4ファイル、集計のコードは commons 経由で `await` 済みか確かめる）、services/report/tests（5ファイル）、Pipfile、Pipfile.lock
- [X] T020 [P] [US1] journal: services/journal/app（4ファイル）、services/journal/tests（3ファイル）、services/journal/tests/e2e/test_tenant_setup_report.py:38 の接続を同じループで閉じる、Pipfile、Pipfile.lock
- [X] T021 [P] [US1] terminal: services/terminal/app（5ファイル）、services/terminal/tests（5ファイル）。integration の test_create_collection_concurrently.py:49、test_delivery_status_acks.py:43、test_republish_undelivered_terminallogs.py:33 の `close()` を `await` に、tests/e2e/test_terminal_jwt_auth.py:279 の接続を閉じる。Pipfile、Pipfile.lock
- [X] T022 [P] [US1] cart: services/cart/app（7ファイル）、services/cart/tests（7ファイル）。integration の test_terminal_counter_rollover.py:23、test_republish_undelivered_tranlogs.py:33 の `close()` を `await` に。services/cart/performance_tests/cleanup_test_data.py:77 も。Pipfile、Pipfile.lock。unit と integration は別のプロセスで走らせる（#153）
- [X] T023 [US1] stock: services/stock/app/services/multi_tenant_snapshot_scheduler.py（:205 付近）の `_get_all_tenant_ids` を共有の `get_client_async()` を使うように直す（FR-009、C-9）
- [X] T024 [US1] stock: services/stock/app/models/repositories/stock_snapshot_repository.py:113 の `list_indexes()` を `await` する。残りの app（計8ファイル）の型を替える
- [X] T025 [US1] stock: services/stock/tests の test_snapshot_scheduler.py:145、test_snapshot_scheduler_unit.py:312,321 の差し替えを `app.services.multi_tenant_snapshot_scheduler.get_client_async` にし、それが使われることを assert する。services/stock/tests/conftest.py:224 の `close()` を `await` に。Pipfile、Pipfile.lock、unit / integration

### セッションを使う処理（C-6）

- [X] T026 [US1] cart（tran_service.py:334,779,1077、明示の commit）、journal（log_service.py:148,221,273、`async with`）、terminal（terminal_service.py:465,703,870、`async with`）のセッションを通る integration のテストが、実際の MongoDB で通ることを確かめる。通る経路のテストがなければ、各サービスの tests/integration に足す

### 依存と全体の確かめ

- [X] T027 [US1] 8つの依存の宣言で Motor が 0 件（`grep -n -i motor services/*/Pipfile services/*/Pipfile.lock services/commons/pyproject.toml`）、コードで 0 件（quickstart §1）。サービス横断の e2e（tests/e2e）も確かめる
- [X] T028 [US1] 7サービスで `pipenv verify`、空の環境での `pipenv install --deploy`、`pip check`、`from pymongo import AsyncMongoClient` が通り `import motor` が失敗する（quickstart §2、R-9）
- [X] T029 [US1] `await` の付け忘れの検索（R-10 の grep）の結果を1行ずつ確かめ、7サービスの unit / integration を `-W error::RuntimeWarning` で通す（C-11）
- [X] T030 [US1] `./scripts/build.sh` で全イメージを作り直し、`./scripts/run_unit_tests.sh`、`./scripts/run_integration_tests.sh`（commons を含む）、`./scripts/run_e2e_tests.sh`（cart は DUAL で96件、サービス横断の e2e も）を通す
- [X] T031 [US1] cart を REQUIRED で: `services/cart/.env` に `CART_REQUEST_SNAPSHOT_MODE=REQUIRED` → 再起動 → `docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE` で REQUIRED を確かめ → `pipenv run pytest tests/e2e -m "not dual_only"` が 48 passed / 48 deselected → 行を消して再起動（C-10）
- [X] T032 [US1] スタックを止める前後の各サービスのログに `unclosed` / `RuntimeError` / `DatabaseException` / `never awaited` が出ないことを確かめる（quickstart §5、R-10）。統合テストの出力に「別のループから閉じようとした」警告が無いことも確かめる
- [X] T032a [US1] 移行後のイメージで、T003a のボリュームをそのまま使ってスタックを起動し、互換確認用のテナントで、移行前に作った取引・ジャーナル・在庫・レポートが読めること、同じテナントで新しい取引を記録して締めまでできることを確かめる（FR-002、SC-003、C-2）
- [X] T032b [US1] テナントのデータベースごとのコレクションと `index_information()` を indexes-after.json に同じやり方で書き出し、T002 の indexes-before.json と差分を取る。差分が 0 であること（FR-003、C-3）
- [X] T033 [US1] 件数を T002 と比べ、同じか多いことを test-baseline.md に追記する（SC-001）

**Checkpoint**: US1 が完了。ここで PR を出せる状態（性能と手順書は残り）

---

## Phase 4: User Story 2 - 下流のツリーが同じ移行を再現できる (Priority: P2)

**Goal**: 手順書だけで同じ移行をたどれる
**Independent Test**: 手順書に、対応表、機械的な置き換えと判断が要るものの区別、検索の方法（R-8 の全項目）、順番、各段階の確かめ方、依存とロックの更新の仕方がそろい、下流のツリーの名前が無い

- [X] T034 [P] [US2] docs/en/general/pymongo-async-migration.md を書く: R-3 の表と3つの壊れ方、R-4 の対応表とモックの注意、R-6 のループと終了の扱い（作ったループを覚える実装の要点）、R-8 の検索項目と `grep -rn -i` のコマンド、進める順番（commons → サービス → 依存 → 全体の確かめ）、各段階の確かめ方（quickstart の要約、R-10）、依存とロックの更新（R-9）
- [X] T035 [P] [US2] docs/ja/general/pymongo-async-migration.md を T034 と同じ中身で書く
- [X] T036 [US2] 2つの手順書に下流のツリーの名前（リポジトリ名・製品名）が無いことを確かめる（FR-016）。docs の目次（あれば docs/en/README.md など）から辿れるようにする

**Checkpoint**: US2 が完了

---

## Phase 5: User Story 3 - 性能が落ちていないことを数字で確かめる (Priority: P3)

**Goal**: 移行前後の性能を同じ条件で比べる
**Independent Test**: 移行前後の表が残り、10% を超える劣化には説明か対処がある

- [X] T037 [US3] 移行後のブランチで、T001 と同じ条件で `/perf-test` を走らせる
- [X] T038 [US3] T001 と T037 を specs/301-pymongo-async-migration/perf-baseline.md に表で並べる。10% を超えて劣化した指標があれば、原因を調べて説明か対処を書く（SC-004）

**Checkpoint**: US3 が完了

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T039 [P] CLAUDE.md の「MongoDB (Motor async driver)」「async operations with Motor」と、Active Technologies の過去の行の「Motor (async MongoDB)」を PyMongo の非同期 API に直す（FR-012）
- [X] T040 [P] docs/ と各サービスの README などで Motor に触れている記述（`grep -rli motor docs` で約20件）を直す（FR-012）
- [X] T041 `grep -rn -i motor` をリポジトリ全体（`.venv`、specs、手順書の対応表を除く）で 0 件にする（SC-002）
- [X] T042 [P] 変更した app のファイルに `pipenv run ruff check app/` を通す（7サービスと commons）
- [ ] T043 PR の本文に、性能の比較表（T038）、件数の比較（T033）、REQUIRED の確かめ（T031）、手順書へのリンクを載せる。コミットは commons / サービスごと / 依存・ドキュメントに分ける（R-1）

---

## Dependencies & Execution Order

- **Phase 1** → すぐ始める。T001 → T002 → T003a は同じスタックを使うので順に走らせる（T003 だけ並べられる）。どれも移行のコードに触れる前に終える
- **Phase 2**（commons）→ Phase 1 のあと。T004 → T005。T006〜T009 は T004 のあと並べて書ける。T010・T011 は T006〜T009 のあと。T014 → T015 → T016
- **Phase 3**（US1）→ T016 のあと。T017〜T022 は並べて進められる。stock は T023 → T024 → T025。T026 は該当サービスのあと。T027〜T033（T032a・T032b を含む）は全サービスのあと、この順
- **Phase 4**（US2）→ T010・T011 の設計が決まれば書き始められる。確かめ方の記述は T033 のあとで仕上げる
- **Phase 5**（US3）→ T030 のあと
- **Phase 6** → 全部のあと（T039・T040 はいつでも）

## Parallel Example

```text
# Phase 2 のテストを並べて書く
T006 test_pymongo_aggregate.py / T007 test_pymongo_session.py / T008 test_pymongo_client_lifecycle.py / T009 test_pymongo_limit_zero.py

# Phase 3 のサービスを並べて移す（Pipfile.lock はサービスごとに別のファイル）
T017 account / T018 master-data / T019 report / T020 journal / T021 terminal / T022 cart
```

## Implementation Strategy

1. Phase 1 で基準を取る（性能は移行前でないと取れない）
2. Phase 2 で commons を移し、書き方が変わる箇所を実際の MongoDB で固める
3. Phase 3 でサービスを移し、全テストを通す → ここが MVP（1つの PR の中身の大部分）
4. Phase 4・5 で手順書と性能の比較を足す
5. Phase 6 でドキュメントを直し、Motor が 0 件であることを確かめて PR を出す
