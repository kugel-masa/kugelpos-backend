# 移植の手順書: Motor から PyMongo の非同期 API へ

Motor は 2026-05-14 に非推奨になり、重大な不具合の修正も **2027-05-14** で終わります。Kugelpos は issue #301 で、すべてのサービスと `kugel_common` を PyMongo の非同期 API（`pymongo.AsyncMongoClient`）に移しました。この手順書は、同じコードベースを共有するツリーが同じ移行をするためのものです。何を、どの順で変え、各段階が終わったことをどう確かめるかを書きます。

移行で挙動は変わりません。API の応答、保存されるデータ（BSON は同じ）、インデックスは同じです。データの移行は要りません。

## 1. 何が変わるか

### 1.1 機械的に置き換えられる名前

| Motor | PyMongo の非同期 API |
|---|---|
| `from motor.motor_asyncio import AsyncIOMotorClient` | `from pymongo import AsyncMongoClient` |
| `AsyncIOMotorDatabase` | `pymongo.asynchronous.database.AsyncDatabase` |
| `AsyncIOMotorCollection` | `pymongo.asynchronous.collection.AsyncCollection` |
| `AsyncIOMotorClientSession` | `pymongo.asynchronous.client_session.AsyncClientSession` |
| `AsyncIOMotorCursor` | `pymongo.asynchronous.cursor.AsyncCursor` |

例外は `pymongo.errors` のままです。`find()` は今までどおり `await` せずにカーソルを返します。`find_one`、`insert_*`、`update_*`、`delete_*`、`count_documents`、`distinct`、`create_index`、`index_information`、`list_collection_names`、`command`、`drop_database`、`server_info` は今までどおり `await` し、`async for doc in cursor` も使えます。

### 1.2 書き方が変わる呼び出し（1つずつ人が判断する）

| 呼び出し | Motor | PyMongo の非同期 API |
|---|---|---|
| `client.start_session()` | `await` する | **`await` しない**（セッションを返す） |
| `session.start_transaction()` | 同期 | **`await` する** |
| `collection.aggregate(...)` | カーソルを返す | **`await` して**カーソルを受け取る |
| `collection.list_indexes()` | カーソルを返す | **`await` して**カーソルを受け取る |
| `client.close()` | 同期 | **`await` する** |
| `cursor.to_list(0)` | 0 は「上限なし」 | **`ValueError`**。`None` を渡す |

これらの `await` を付け忘れても、いつも分かりやすく失敗するとは限りません。

- `client.close()` の付け忘れ: 警告（`coroutine ... was never awaited`）が出るだけで、接続は閉じません。
- `aggregate()` の付け忘れ: 結果を回すときに `TypeError` になります。呼び出しを広い `except` で包んでいるコードでは、「空の結果」に化けます。
- `session.start_transaction()` の付け忘れ: トランザクションが始まりません。書き込みは1つずつその場で確定し、abort しても残ります。「commit で書き込みが残る」だけを見るテストでは気づかないので、「abort で何も残らない」ことを確かめてください。

`session.commit_transaction()`、`abort_transaction()`、`end_session()` は、どちらのドライバでも `await` します。`async with session:` もどちらでも使えます。

### 1.3 1つの接続は1つのイベントループに属する

PyMongo の非同期の接続は、作ったイベントループの中でしか使えず、閉じることもできません。別のループから `close()` を `await` すると `RuntimeError` になります（Motor では起きませんでした）。ループが変わる場所では、次のことに気をつけます。

- **テストごとに新しいループを使うテスト**: 共有の接続は、各テストの終わりに、そのテストのループの中で閉じます（function スコープの fixture の後始末）。次のテストに捨てさせてはいけません。
- **接続の作成を守るモジュールの `asyncio.Lock`**: ロックは最初に待ったループに縛られるので、モジュールで1つのロックは、2つ目以降のループで使えなくなります。ロックはループごとに持ちます。
- **自分で接続を作るコード**（定期ジョブ、スクリプト）: 同じループの中で `finally` で閉じるか、共有の接続を使います。

このツリーの `kugel_common.database.database` は、接続と一緒に、それを作ったループを覚えています。`close_client_async()` と `reset_client_async()` は、そのループから呼ばれたら接続を閉じます。別のループから呼ばれたら、閉じると例外になるので、警告（`created on another event loop`）を残して参照だけを捨てます。`get_client_async()` が別のループから呼ばれたときも、同じように前の接続を捨てて作り直します。この警告は「接続が、作ったループより長く生き残った」印なので、テストの実行で出てはいけません。

uvicorn のワーカーは別のプロセスで、APScheduler の `AsyncIOScheduler` はアプリと同じループで動くので、どちらも新しい対応は要りません。

## 2. 変える箇所の見つけ方

大文字・小文字を区別せずに検索し、結果を1つずつ人が見ます。

```bash
# 読み込みと型
grep -rn -i "motor" --include=*.py . | grep -v "/.venv/"

# 書き方が変わる呼び出し
grep -rn -E "\.(aggregate|list_indexes|close|start_session|start_transaction)\(" --include=*.py . | grep -v "/.venv/"
grep -rn -E "to_list\(" --include=*.py . | grep -v "/.venv/"     # 0 になりうる値はないか

# Motor にしかない API（このツリーでは使っていないが、自分のツリーでは確かめる）
grep -rn -i -E "io_loop|get_io_loop|\.each\(|stream_to_handler|\.watch\(|GridFS|motor_gridfs|delegate" --include=*.py . | grep -v "/.venv/"

# 共有の補助を通さずに作る接続（誰が、どのループで閉じるか）
grep -rn "AsyncIOMotorClient(\|AsyncMongoClient(" --include=*.py . | grep -v "/.venv/"
```

最後の2つの検索の結果は、1つずつ「`await` が要るか」「`finally: await client.close()` が要るか」「共有の接続にすべきか」を判断します。`.watch()`（change stream）と GridFS には PyMongo の非同期 API での書き方があるので、[公式の移行ガイド](https://www.mongodb.com/docs/languages/python/pymongo-driver/reference/migration/)を読んでください。

### テストの差し替え（モック）

Motor を差し替えているテストは、Motor が無くなっても落ちません。何も確かめないテストになるだけです。1つずつ直します。

- `patch("motor.motor_asyncio.AsyncIOMotorClient")` は Motor のモジュールを差し替えていました。テストするコードが実際に読む名前（例: `app.services.some_module.get_client_async`）を差し替え、差し替えたものが使われたことを assert します。
- `monkeypatch.setattr(database, "AsyncIOMotorClient", Fake)` は `AsyncMongoClient` にします。偽物には `async def close()` を持たせます。
- `aggregate` / `list_indexes` がただの関数になっている偽のコレクションは、`async def` にします。そうしないと `await` で `TypeError` になり、広い `except` に飲まれて、テストは何も確かめずに通ります。
- `client.close` の `MagicMock` は `AsyncMock` にします。

## 3. 進める順番

1. **先に計る**: 何も変える前に、標準の性能テスト（`/perf-test`）を2回走らせます。1回ごとの平均はおよそ 15〜19% ぶれるので、10% の差を見分けるには2回の平均が要ります。
2. **基準を残す**: サービスと段階ごとのテストの件数、cart の e2e の両方のスナップショットのモードでの件数、テナントのデータベースごとのコレクションと `index_information()`。それから、移行前のイメージでテナントを作って販売と入金を1件ずつ行い、その API の応答を記録します。MongoDB のボリュームは残しておきます。
3. **共通ライブラリ**: 接続の作成と終了、セッションの開始、集計の呼び出し、型を直します。実際の MongoDB（レプリカセット）に対する統合テストを足します。対象は、集計の結果、セッションの commit / abort / `async with`、同じループ・二重・別のループからの終了、`get_client_async` の同時呼び出し、`max=0` が「上限なし」であること、です。wheel の版を上げます。
4. **サービス**: 名前の置き換え、書き方が変わる呼び出し（§1.2）、補助を通さずに作る接続、テストの差し替え（§2）を直します。サービスごとに unit と統合テストを通しながら進めます。
5. **依存**（§5）
6. **全体の確かめ**（§4）
7. **もう一度計り**、同じ条件で比べます。
8. **ドキュメント**: プロジェクトのドキュメントとエージェント向けの指示にある「Motor」を直します。

1つの変更として出します。サービスは共通ライブラリのデータベースとセッションの型をそのまま使うので、互換の層を挟まない限り、「共通ライブラリだけ PyMongo、サービスは Motor」（またはその逆）の途中の状態では動きません。

## 4. 各段階の確かめ方

| 確かめること | やり方 |
|---|---|
| Motor が残っていない | コード、Pipfile、ロック、`pyproject.toml` を `grep -rn -i motor` して何も出ない |
| テスト | unit / 統合 / e2e の件数が基準と同じ（足したテストの分だけ多い）で、失敗が無い。このツリーでは cart の e2e を `DUAL` と `REQUIRED` で走らせる。モードを設定したら再起動し、`docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE` で確かめる |
| `await` の付け忘れ | unit と統合テストを `-W error::RuntimeWarning` で走らせる。書き方が変わる呼び出しの検索結果を全部読む |
| セッション | 実際の MongoDB で、トランザクションを開く各経路が `start_transaction()` の直後にトランザクションの中にいる（`session.in_transaction`）。abort すると書き込みが残らない |
| 移行前のデータ | 新しいイメージで、古いボリュームのまま、段階 2 のテナントが同じ応答を返す（速報のレポートの作成時刻のように、リクエストのたびに作るものだけが違う）。古い販売の取消、新しい販売、締めができる |
| インデックス | サービスのデータベースごとのコレクションと `index_information()` が基準と同じ |
| 停止 | スタックを止めて各サービスのログを読む。`Database connection closed` が1回、`RuntimeError` も閉じ忘れの警告も無い。統合テストは lifespan を通らないので、停止の順番はこの確かめでしか分からない |
| 性能 | 中央値、p95、p99、スループットが基準の 10% 以内。超えたら説明を付ける |

## 5. 依存とロックの更新

- 共通ライブラリの `pyproject.toml`: `motor` を `pymongo>=4.13` に替えます（4.13 は非同期 API がベータを外れた版です）。
- 各 Pipfile: `motor = "*"` を `pymongo = ">=4.13"` に替えます。
- 各 Pipfile.lock: PyMongo は Motor の依存として、ハッシュも含めてすでにロックされています。`motor` の項目を消すだけで足ります。`pymongo` の項目に `"index": "pypi"` を足すと、`pipenv lock` が直接の依存を書くときと同じ形になります。`_meta.hash.sha256` は pipenv 自身の計算（`Project().pipfile.calculate_hash()`）で計算し直します。共通ライブラリを wheel で同梱しているなら、そのファイル名とハッシュも更新します。この直し方なら、ほかの依存の版は動かず、差分にはこの変更だけが出ます。
- `pipenv verify` は Pipfile のハッシュを比べるだけです。空の環境にロックから入れて確かめます。

  ```bash
  export WORKON_HOME=$(mktemp -d) PIPENV_VENV_IN_PROJECT=0 PIPENV_IGNORE_VIRTUALENVS=1
  pipenv install --deploy && pipenv run pip check
  pipenv run python -c "from pymongo import AsyncMongoClient"
  pipenv run python -c "import motor"      # 失敗しなければならない
  pipenv --rm
  ```

- イメージを作り直し、その中で、共通ライブラリが新しい版であること、`motor` が無いことを確かめます。
- 既存の開発環境には Motor が残っています。`pipenv run pip uninstall -y motor` で外し、読み込みが残っていたら CI だけでなく手元でも失敗するようにします。
