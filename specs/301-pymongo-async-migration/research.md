# Research: Motor から PyMongo Async API への移行

**Feature**: 301-pymongo-async-migration | **Date**: 2026-11-24

調べた事実は、各サービスのロックにある PyMongo 4.20.0 / 4.20.1（commons の環境）を `inspect` で確かめたもの、コードの検索、公式の移行ガイド（https://www.mongodb.com/docs/languages/python/pymongo-driver/reference/migration/ ）による。

---

## R-1: 出し方 — 1つの PR にまとめる

**Decision**: commons と7サービスを、このブランチの1つの PR で移す。コミットは「commons」「サービスごと」「依存・ドキュメント」に分け、レビューと下流への移植で追いやすくする。

**Rationale**:
- サービスは commons の型（`AbstractRepository` が受け取るデータベース、`get_db_async` が返すもの）をそのまま使う。commons だけ先に PyMongo にすると、Motor のデータベースを PyMongo のコードに渡すことになり、段階の途中で動かない。互換の層を挟めば段階的にも出せるが、捨てるコードが増える
- 全サービスを同じ commons の版でまとめて試せる（unit / integration / e2e、cart の DUAL と REQUIRED）
- 下流のツリーは、1つの PR を手順書と並べて読めばよい

**Alternatives considered**:
- commons を先に出し、サービスを1つずつ移す（issue の案）: 互換の層が要り、段階ごとに全テストを回す手間が7倍になる。不採用
- サービスごとに別の commons を持つ: commons の目的に反する。不採用

---

## R-2: PyMongo の最低バージョン — `pymongo>=4.13`

**Decision**: commons の `pyproject.toml` と各 Pipfile で、`motor` を外して `pymongo>=4.13` を宣言する。ロックは今の 4.20.x のまま（Motor の依存として既に入っている）。

**Rationale**: 非同期 API（`pymongo.AsyncMongoClient`）は 4.10 で入り、4.13 で GA（ベータを外れた）。公式の移行ガイドも GA の版からの移行を前提にしている。ロックが 4.20 なので、実際に動くのは 4.20。

**Alternatives considered**: `pymongo>=4.10`（ベータの版を許す）: 不採用。版の指定なし（`*`）: 非同期 API の無い古い版が入りうるので不採用。

---

## R-3: 書き方が変わる呼び出し（PyMongo 4.20 で確かめた）

| 呼び出し | Motor | PyMongo Async | このコードベースで当たる箇所 |
|---|---|---|---|
| `client.start_session()` | `await` が要る | **`await` しない**（`AsyncClientSession` を返す） | commons `AbstractRepository.start_transaction` |
| `session.start_transaction()` | 同期 | **`await` が要る** | 同上 |
| `session.commit_transaction()` / `abort_transaction()` / `end_session()` | `await` | `await`（変わらない） | commons |
| `collection.aggregate(...)` | カーソルを返す（同期） | **`await` が要る**（カーソルを返すコルーチン） | commons `AbstractRepository.execute_pipeline`、`database.find_blocking_duplicates` 系の補助 |
| `collection.list_indexes()` | カーソルを返す（同期） | **`await` が要る** | stock `stock_snapshot_repository.py:113` |
| `client.close()` | 同期 | **`await` が要る** | commons `close_client_async` / `reset_client_async`、テストの後始末 |
| `cursor.to_list(0)` | 空のリストを返す | **`ValueError`** | 今のコードは、リポジトリの「0 = 上限なし」を、カーソルに渡す前に `None`（上限なしの取得）に振り替えている（R-5） |
| `collection.find(...)` | 同期でカーソル | 同期でカーソル（変わらない） | 多数 |
| `find_one` / `insert_*` / `update_*` / `delete_*` / `count_documents` / `distinct` / `create_index` / `index_information` / `list_collection_names` / `command` / `drop_database` / `server_info` | `await` | `await`（変わらない） | 多数 |
| `async for doc in cursor` | 可 | 可（変わらない） | 多数 |
| 例外 | `pymongo.errors.*` | `pymongo.errors.*`（同じ） | 変更なし |

**Rationale**: 機械的な名前の置き換え（R-4）で済まないのはこの表の太字の行だけ。数が少ない（セッション1か所、集計2か所、`list_indexes` 1か所、`close` 2か所＋テスト）ので、1つずつ直してテストを付ける。

**`await` の付け忘れの壊れ方**（R-10 で検出する）:
- `client.close()` の付け忘れ: `RuntimeWarning: coroutine ... was never awaited` が出るだけで、接続は閉じない
- `aggregate()` の付け忘れ: `async for` で `TypeError`、`.to_list()` をつなぐと `AttributeError` になるが、呼び出し元の広い `except` に飲まれて「空の結果」に化ける
- `session.start_transaction()` の付け忘れ: トランザクションが始まらず、書き込みがトランザクションの外で確定する。commit は `No transaction started` で失敗するが、書き込みは残る。`in_transaction` を見てから abort する経路は黙って通る（PR #339 のレビューで実際の MongoDB で確かめた）

**セッションの使い方は2通り**（どちらも commons を直せばそのまま動くが、両方を実際の MongoDB で通す）:
- cart `tran_service.py:334,779,1077`: `start_transaction()` で受け取ったセッションを明示的に commit / abort する
- journal `log_service.py:148,221,273`、terminal `terminal_service.py:465,703,870`: `async with await repo.start_transaction() as session:` の中で使い、抜けるときにセッションを終える

---

## R-4: 名前の置き換え（機械的にできるもの）

| Motor | PyMongo Async |
|---|---|
| `from motor.motor_asyncio import AsyncIOMotorClient` | `from pymongo import AsyncMongoClient` |
| `AsyncIOMotorDatabase` | `pymongo.asynchronous.database.AsyncDatabase` |
| `AsyncIOMotorCollection` | `pymongo.asynchronous.collection.AsyncCollection` |
| `AsyncIOMotorClientSession` | `pymongo.asynchronous.client_session.AsyncClientSession` |
| `AsyncIOMotorCursor` | `pymongo.asynchronous.cursor.AsyncCursor` |
| テストの `patch("motor.motor_asyncio.AsyncIOMotorClient")` | 差し替える対象を、コードが実際に読み込む名前（例: `app.services.multi_tenant_snapshot_scheduler.AsyncMongoClient`）にする |

数（2026-11-24 時点、`.venv` を除き `grep -rli motor --include=*.py` で数える）: Motor を読み込むファイルはアプリ側 42、テスト側は数え方で 21〜30（`import motor` / `from motor` だけなら 21、`motor` の文字を含むもの全体なら 30）、性能テスト 1。型の参照は `AsyncIOMotorDatabase` 110、`AsyncIOMotorClient` 34、`AsyncIOMotorCollection` 4、`AsyncIOMotorClientSession` 5。実装の前に同じコマンドで数え直し、tasks の完了条件は「0 件」で判定する（件数そのものは目安）。

**注意**: `patch("motor....")` を名前だけ置き換えると、差し替え先がコードの読み込む名前とずれて、テストが本物の接続を作りにいくか、何も確かめないテストになる。テストの差し替えは1つずつ、差し替えた値が実際に使われることを確かめる（FR-013）。

**差し替え（モック）の一覧**（1つずつ直す）:

| 箇所 | 今 | 直し方 |
|---|---|---|
| commons `tests/unit/test_repository_update_masking.py:45,191` | 同期の偽の `aggregate`（カーソルを直接返す） | `async def` の偽にする（`await` すると偽のカーソルを返す）。直さないと `await` で `TypeError` になり、それが広い `except` に飲まれて、テストが何も確かめずに通る |
| commons `tests/unit/test_database_uri_redaction.py:53` | `monkeypatch.setattr(database, "AsyncIOMotorClient", …)` | `database.AsyncMongoClient` を差し替える。差し替えた偽が呼ばれたことを assert する |
| stock `tests/.../test_snapshot_scheduler.py:145`、`test_snapshot_scheduler_unit.py:312,321` | `patch("motor.motor_asyncio.AsyncIOMotorClient")` | スケジューラーが共有の接続を使うようになる（R-6）ので、`app.services.multi_tenant_snapshot_scheduler.get_client_async` を差し替える |
| その他の `AsyncMock(spec=AsyncIOMotorDatabase)` など | Motor の型を spec にする | PyMongo の型に替える。`aggregate` / `list_indexes` / `close` を `MagicMock` で返していた箇所は `AsyncMock` にする |

実装の前に `grep -rn -i "motor\|aggregate\|list_indexes\|\.close()" services/*/tests services/commons/tests` で、差し替えと偽の実装を洗い直す。

---

## R-5: 件数 0 の取得

**Decision**: `to_list` に渡す値がすべて 0 にならないことを確かめ、0 になりうる箇所には「0 → None」の振り替えを置く。今のコードは次のとおりで、追加の変更は要らない:

- commons `get_all_async` / `get_list_async`: `max == 0` の分岐で上限なしの取得をし、それ以外で `to_list(max)`
- `to_list(None if limit == 0 else limit)` / `to_list(length=limit if limit > 0 else None)`: 振り替え済み
- `database.py:346` `to_list(length=limit)`: `limit` は呼び出し元の固定値（> 0）
- cart `to_list(2)`、stock `to_list(length=1)`: 定数

0 を渡すと `ValueError` になる挙動を、実際の MongoDB で確かめるテストを commons に置き、`max=0` が上限なしで返ることを固定する（FR-004、FR-014）。

---

## R-6: 1つのイベントループに1つの接続

**Decision**: 接続の作り方は今と同じ「プロセスで1つ」を保つ。PyMongo の `AsyncMongoClient` は作ったループからしか使えないので、ループが変わる箇所を次のとおり扱う。

| 箇所 | 今の扱い | 移行後 |
|---|---|---|
| uvicorn のワーカー | ワーカーごとに別のプロセス → 接続もプロセスごと | 変更なし |
| アプリの起動・停止 | 起動でつなぎ、停止で `close_client_async` | `close` を `await` する |
| stock の APScheduler（`AsyncIOScheduler`） | アプリと同じループで動く | 変更なし（同じループ）。テストで確かめる |
| cart / terminal の未配信ログの再送 | アプリと同じループのバックグラウンドのタスク | 変更なし |
| stock `_get_all_tenant_ids` | 呼ばれるたびに `AsyncIOMotorClient` を作り、閉じない | **共有の接続（`get_client_async`）を使う**（FR-009） |
| 統合テスト | テストごとに新しいループ。conftest が各テストの前に共有の接続を捨てる（`reset_client_async`） | **各テストの終わりに、同じループの中で `await close_client_async()` する**（fixture の後始末）。次のテストの最初に前のループの接続を捨てる形はやめる |
| テストが直接作る接続 | 後始末で同期の `client.close()`、または閉じない | 作ったテストの中で `await client.close()` する（下の一覧） |
| commons `_client_lock`（`asyncio.Lock`） | モジュールで1つ | **ループごとに持つ**（接続と同じく、作ったループを覚えておき、ループが変わったら作り直す） |

**別のループから閉じたとき**: PyMongo では、接続を作ったループと違うループで `await client.close()` すると `RuntimeError` になる（Motor では起きなかった）。失敗を握りつぶして参照だけ捨てると、何も閉じられず、接続のプールと監視のタスクが前のループに残る。また `close_client_async` は例外を `DatabaseException` に包むので、そのままでは約25か所のテストの後始末と7サービスの停止処理がエラーになる。そこで:

- `get_client_async` は、接続を作ったループ（`asyncio.get_running_loop()`）を接続と一緒に覚える
- `close_client_async` / `reset_client_async` は、今のループが作ったループと同じなら `await client.close()` する
- 違うループから呼ばれたとき（作ったループがすでに閉じている場合を含む）は、閉じられないことを警告のログに残して参照を捨てる。これは「後始末の順番が間違っている」印なので、テストでこの警告が出ないことを確かめる（R-10）
- `get_client_async` が、覚えたループと違うループから呼ばれたときは、前の接続を上と同じ扱いで捨てて作り直す（今の conftest の `reset_client_async` が担っていたこと）

**後始末を直すテスト**（同期の `close()`、または閉じていない）:
- `stock/tests/conftest.py:224`
- terminal integration `test_create_collection_concurrently.py:49`、`test_delivery_status_acks.py:43`、`test_republish_undelivered_terminallogs.py:33`
- cart integration `test_terminal_counter_rollover.py:23`、`test_republish_undelivered_tranlogs.py:33`
- `cart/performance_tests/cleanup_test_data.py:77`
- 閉じていない: `journal/tests/e2e/test_tenant_setup_report.py:38`、`terminal/tests/e2e/test_terminal_jwt_auth.py:279`

**アプリの起動・停止は統合テストを通らない**（統合テストは lifespan を通らない）。停止の順番は、e2e のスタックを止めたときのログで確かめる（R-10）。

**Rationale**: Motor もループに縛られていたので（テストの conftest がすでにループごとに接続を作り直している）、考え方は変わらない。違いは `close` が `await` になる点と、別のループから閉じると失敗する点。閉じる場所を「作ったループの中」に揃えれば、別のループから閉じる経路は残らない。

---

## R-7: 性能の比べ方

**Decision**: 標準の性能テスト（`/perf-test`、cart の `performance_tests`）を、移行前の main と移行後のブランチで、同じ条件（同じユーザー数・時間・データ）で走らせ、主要な指標（応答時間の中央値・p95、スループット、失敗率）を PR に表で載せる。移行前の数字は、移行に手を付ける前に取る。

**Rationale**: 公式の移行ガイドは、Motor のスレッドの実行器から asyncio のタスクに変わるため遅くなる場合があると注意している。SC-004 の 10% を目安に、超えたら原因を調べる。

---

## R-8: 移植の手順書の置き場所と形

**Decision**: `docs/en/general/pymongo-async-migration.md` と `docs/ja/general/pymongo-async-migration.md` に置く。中身は、R-3 の表、R-4 の対応表、検索のコマンド（書き方が変わる箇所の見つけ方）、進める順番、各段階の確かめ方、依存とロックの更新の仕方。下流のツリーの名前は書かない。

**検索して個別に判断する項目**（このツリーでは使っていないが、下流のツリーにはありうる）: `aggregate(`、`list_indexes(`、`.close()`、`start_session`、`start_transaction`、`to_list(`、`AsyncIOMotor`、`motor_asyncio`、`io_loop`、`get_io_loop`、`.each(`、`stream_to_handler`、`.watch(`（change stream）、GridFS（`AsyncIOMotorGridFSBucket`、`motor_gridfs`）、`delegate`（Motor の内部の同期オブジェクトへの参照）。検索は大文字・小文字を区別しない（`grep -rn -i`）。

**Rationale**: docs は英語が主（CLAUDE.md）で、日本語版もある。手順書は、この移行のあとも残る文書なので、specs ではなく docs に置く。

---

## R-9: ロックの更新

**Decision**: 7サービスと commons の8つの Pipfile から `motor` を消し、`pymongo = ">=4.13"` を足す。ロックは `pipenv lock` を全体でやり直さず、`motor` の項目を消し、`pymongo` の項目（今の 4.20.x のまま）を `default` に残し、`_meta` のハッシュを pipenv の `pipfile.calculate_hash()` で計算し直す。`pipenv verify` で確かめる。commons の wheel の版を上げ（0.1.122）、7サービスの参照も合わせる。

**Rationale**: これまでの commons の更新と同じやり方で、ほかの依存を動かさない。`pipenv lock` を全体でやり直すと、無関係な依存の版まで動いて、差分の確かめ方が難しくなる。

**確かめた事実**: 8つのロック（7サービスと commons）はすべて、すでに `pymongo`（4.20.x、ハッシュ 71 件、`markers: python_version >= '3.11'`）と `dnspython`（2.9.2）を `default` に持っている。`motor` の項目を消しても、`pymongo` の項目を書き足す必要はない。`pipenv lock` で作り直した場合と違うのは、直接の依存になった `pymongo` に `"index": "pypi"` が付くかどうかだけで、インストールの結果は変わらない（揃えるために手で `"index": "pypi"` を足す）。

**確かめ方**（`pipenv verify` は `_meta` のハッシュを比べるだけなので、それだけでは足りない）:
1. `pipenv verify`（Pipfile とロックの対応）
2. 空の環境での `pipenv install --deploy`（例: `PIPENV_VENV_IN_PROJECT=0 WORKON_HOME=$(mktemp -d) pipenv install --deploy`）。ロックに書かれたものだけで入ることを確かめる
3. その環境で `pipenv run pip check`（依存の食い違いがない）と `python -c "import pymongo; from pymongo import AsyncMongoClient"`、`python -c "import motor"` が失敗すること
4. 7サービスのイメージを作り直す（`./scripts/build.sh`）。Dockerfile も `pipenv install --deploy` で入れる

---

## R-10: `await` の付け忘れと終了の順番を、警告で終わらせない

**Decision**:
- 7サービスと commons の unit / integration を、移行後に一度 `-W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning` を付けて走らせる。`coroutine ... was never awaited` は後始末の中で出るため、pytest は `PytestUnraisableExceptionWarning` として扱う。`RuntimeWarning` だけでは失敗にならない
- 付け忘れを検索する: `grep -rn -E "\.(aggregate|list_indexes|close|start_transaction)\(" services/*/app services/*/tests services/commons/src services/commons/tests` の結果を1行ずつ見て、PyMongo の接続・コレクション・セッションに対する呼び出しに `await` があることを確かめる
- R-6 の「別のループから閉じようとした」警告のログが、統合テストの出力に出ないことを確かめる
- e2e のスタックを止めたとき（`./scripts/stop.sh`）の各サービスのログに、閉じ忘れの警告（`Unclosed AsyncMongoClient` など）、`RuntimeError`、`DatabaseException` が出ないことを確かめる。lifespan の停止の順番は、統合テストでは通らない

**Rationale**: R-3 の3つの壊れ方は、どれも「テストは通るが壊れている」形になりうる。警告を失敗にし、検索で目で確かめ、停止のログを見れば、付け忘れと順番の誤りを拾える。

---

## R-11: commons の統合テストの置き場所と走らせ方

**Decision**: `services/commons/tests/integration/` を新しく作り、実際の MongoDB に対するテスト（R-3 の書き方が変わる箇所: 集計、セッションの commit / abort / `async with`、接続の終了とループ、件数 0）を置く。`scripts/run_integration_tests.sh` の `ALL_SERVICES` に `commons` を足し、ほかのサービスと同じように回るようにする（スクリプトは `pytest -m integration` を走らせるので、conftest で marker を自動で付ける）。commons の conftest は、サービスの integration の conftest と同じ形（`MONGODB_URI`、テスト用のデータベースを作って最後に消す、テストの終わりに同じループで接続を閉じる）にする。

**Rationale**: 今の commons には `tests/unit` しかなく、統合テストを回すスクリプトは7サービスしか見ない。commons にテストを置いても、どこからも走らなければ FR-014 を満たさない。

**注意**: テスト用のデータベースの名前は、作るときに一度だけ決めて fixture が持ち、後始末ではその名前だけを消す（決まった接頭辞を assert する）。#335 で、後始末のときに名前を計算し直して本物のデータベースを消した失敗があった。
