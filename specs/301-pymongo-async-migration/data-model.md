# Data Model: Motor から PyMongo Async API への移行

**Feature**: 301-pymongo-async-migration | **Date**: 2026-11-24

## 保存するデータ

**変更なし**。コレクション、文書の形、インデックス、データベースの名前は、移行の前後で同じ（FR-002、FR-003）。ドライバはデータの形式を変えない（BSON は同じ）。データの移行は要らない。

## 実行時のもの

### データベースへの接続（`AsyncMongoClient`）

| 項目 | 内容 |
|---|---|
| 作る場所 | commons `database.get_client_async()`（プロセスで1つ）。stock の全テナントの一覧も、これを使うように変える（R-6） |
| 属するもの | 作ったイベントループ。別のループからは使えない |
| 閉じる | 作ったループの中で `await close_client_async()`（アプリの停止、各テストの終わり）。別のループから呼ばれたときは `close()` せず、警告のログを残して参照を捨てる（R-6）。この警告が出ないことをテストで確かめる |
| 作ったループ | 接続と一緒に覚える。`get_client_async` が別のループから呼ばれたら、前の接続を捨てて作り直す |
| ロック | `_client_lock` もループごとに持つ |
| 設定 | 接続のプールとタイムアウトの設定（`DB_MAX_POOL_SIZE` ほか）は、同じ名前の引数で渡す |

### セッション（`AsyncClientSession`）

| 項目 | 内容 |
|---|---|
| 開始 | `client.start_session()`（`await` しない）→ `await session.start_transaction()` |
| 終了 | `await session.commit_transaction()` / `await session.abort_transaction()` → `await session.end_session()` |
| 使い方 | 今と同じ。`AbstractRepository.start_transaction()` が返すセッションを、cart は明示の commit / abort で、journal と terminal は `async with` で使う |
| 付け忘れ | `await session.start_transaction()` を忘れると、書き込みがトランザクションの外で確定する。テストは「abort で残らない」も確かめる |

### カーソル（`AsyncCursor` / 集計のカーソル）

| 項目 | 内容 |
|---|---|
| `find` | 同期でカーソルを返す（変わらない） |
| `aggregate` | `await` してカーソルを受け取る（変わる） |
| `to_list(n)` | `n` は `None` か 1 以上。0 は使わない（R-5） |
