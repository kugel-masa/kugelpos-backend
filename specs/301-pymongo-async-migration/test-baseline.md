# 移行前の基準: テストの件数と Motor の参照

**Feature**: 301-pymongo-async-migration
**計測した版**: main 33186ed7（2026-11-24）

## Motor の参照（T003）

`services/` の下の Python ファイル（`.venv` を除く）で数えた。

| 対象 | コマンド（`services/` で） | 件数 |
|---|---|---|
| Motor を読み込むアプリ側のファイル（`tests/` の外。`cart/performance_tests` を含む） | `grep -rlE "^\s*(from\|import) motor" --include=*.py . --exclude-dir=.venv \| grep -v /tests/` | 43 |
| Motor を読み込むテストのファイル | 同じコマンドで `\| grep /tests/` | 15 |
| motor の文字を含むテストのファイル（大文字・小文字を区別しない。読み込み、`patch("motor...")`、コメント） | `grep -rli motor --include=*.py . --exclude-dir=.venv \| grep /tests/` | 29 |
| motor の文字を含むファイル全体 | `grep -rli motor --include=*.py . --exclude-dir=.venv` | 73 |
| リポジトリ直下のサービス横断の e2e（`tests/`） | `grep -rli motor --include=*.py ../tests` | 0 |

| 型の参照 | 件数 |
|---|---|
| `AsyncIOMotorDatabase` | 110 |
| `AsyncIOMotorClient` | 34 |
| `AsyncIOMotorCollection` | 4 |
| `AsyncIOMotorClientSession` | 5 |
| `AsyncIOMotorCursor` | 0 |

完了の条件は、上のすべての行が 0 件になること（SC-002）。件数そのものは目安。

## テストの件数（T002）

`./scripts/run_unit_tests.sh`、`./scripts/run_integration_tests.sh`、`./scripts/run_e2e_tests.sh`（`./scripts/build.sh` で作り直したスタック、cart は DUAL）。すべて失敗 0 件。

| サービス | unit | integration | e2e |
|---|---|---|---|
| commons | 995 | （無し） | — |
| account | 61 | 13 | 6 |
| terminal | 471 | 53 | 18 |
| master-data | 576 | 193 | 27 |
| cart | 1003 | 115 | 117（DUAL） |
| journal | 212 | 36 | 6 |
| report | 368 | 85 | 36 |
| stock | 246 | 37 | 15 |
| サービス横断（`tests/e2e`） | — | — | 100 |

cart の e2e を REQUIRED で（`services/cart/.env` に `CART_REQUEST_SNAPSHOT_MODE=REQUIRED` → 再起動 → `docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE` が `REQUIRED` → `pytest tests/e2e -m "not dual_only"`）: **66 passed, 51 deselected**。終わったあと `.env` を消して再起動し、DUAL に戻したことを確かめた。

CLAUDE.md と `/test-guide` にある件数（DUAL 96、REQUIRED 48 / 48）は古く、今は DUAL 117、REQUIRED 66 / 51。移行後はここで記録した件数と比べる。

インデックス（FR-003）: e2e のあと、このリポジトリのサービスのデータベースのコレクションと `index_information()` を、作業用のディレクトリの `indexes-before.json` に書き出した（`db_account` 2、`db_cart` 7、`db_common` 1、`db_journal` 5、`db_master` 10、`db_report` 5、`db_stock` 5、`db_terminal` 6 コレクション）。手元の MongoDB にはほかのプロジェクトのデータベースもあるので、ファイルはコミットしない。

互換確認用のテナント（T003a）: 移行前のスタックでテナント `CMP6EDB3F32` を作り、開設 → 販売 1 件 → 入金を行い、API の応答（取引、ジャーナル、在庫、在庫の履歴、速報のレポート、端末、商品、担当者）を作業用のディレクトリの `compat_state.json` に残した。MongoDB のボリュームは移行後まで消さない。

## 移行後（T027〜T033）

commons 0.1.122、各サービスの venv から motor を外し、`./scripts/build.sh` で作り直したスタックで計測した。

| サービス | unit | integration | e2e |
|---|---|---|---|
| commons | 995 | 24（新規） | — |
| account | 61 | 13 | 6 |
| terminal | 471 | 53 | 18 |
| master-data | 576 | 193 | 27 |
| cart | 1003 | 115 | 117（DUAL） |
| journal | 212 | 36 | 6 |
| report | 368 | 85 | 36 |
| stock | 246 | 37 | 15 |
| サービス横断（`tests/e2e`） | — | — | 100 |

すべて失敗 0 件で、件数は移行前と同じ（commons の integration の 24 件が増えた分だけ多い）。cart の REQUIRED は移行前と同じ手順で **66 passed, 51 deselected**（移行前と同じ）。

| 確かめたこと | 結果 |
|---|---|
| Motor の参照（T027） | `.py` ファイル、Pipfile、ロック、commons の pyproject のどれも 0 件 |
| 依存（T028） | 8 つのロックで `pipenv verify` が通る。空の環境での `pipenv install --deploy` → `pip check` で問題なし、pymongo 4.20.x が入り、`import motor` は失敗する。イメージの中も commons 0.1.122、pymongo 4.20.0、motor なし |
| `await` の付け忘れ（T029） | 8 つの unit / integration を `-W error::RuntimeWarning` で通した。`aggregate` / `list_indexes` / `start_session` / `start_transaction` の呼び出し（アプリ側 13 か所）をすべて目で確かめた。unit に残る `coroutine ... was never awaited` は、同期のメソッド（`set_session`）を `AsyncMock` で差し替えているテストのもので、移行前からある |
| セッション（T026） | 統合テストで実際の MongoDB に対して、cart（`create_tranlog_async` 23 回、`void_async`、`return_async`）、journal（commit 16 回、abort 7 回）、terminal（開設 12 回、締め 4 回、入出金 2 回）のトランザクションが開き、どれも開始の直後に `in_transaction` だった |
| 移行前のデータ（T032a） | 移行前に作ったテナント `CMP6EDB3F32` を移行後に読み直し、取引・ジャーナル・在庫・在庫の履歴・端末・商品・担当者は一致。違いは速報のレポートの作成時刻だけ（リクエストのたびに作るもの）。続けて、移行前の販売の取消、新しい販売、締めができた（取引 3 件、在庫 −3） |
| インデックス（T032b） | このリポジトリのサービスのデータベースのコレクションとインデックス 134 件が、移行の前後で一致（差分 0） |
| 停止の順番（T032） | 7 サービスを止めたとき、どれも `Database connection closed` が 1 回出て、`RuntimeError`、`DatabaseException`、閉じ忘れの警告は無い。統合テストの出力に「別のループから閉じようとした」警告は無い |
