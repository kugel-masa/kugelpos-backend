# Contract: 移行の前後で保つ挙動

**Feature**: 301-pymongo-async-migration

この移行に外向けの新しい契約はない。次の挙動を、移行前と同じに保つ。各行に、それを確かめるテストを置く。

| # | 保つ挙動 | 確かめ方 |
|---|---|---|
| C-1 | すべての API の応答（状態コード、本文、エラーコード）が同じ | 既存の unit / integration / e2e、サービス横断の e2e がすべて通る |
| C-2 | 移行前に作られたデータを、そのまま読み書きできる | 既存の integration・e2e（移行前の形のデータを入れて読むテストを含む） |
| C-3 | テナントの作成で作られるコレクションとインデックスが同じ | 既存のテナントのセットアップのテスト、インデックスの整備のテスト |
| C-4 | `get_all_async` / `get_list_async` の `max=0` は上限なし | commons の integration（実際の MongoDB）。`to_list(0)` が `ValueError` になることも確かめ、0 を渡す経路がないことを固定する |
| C-5 | 集計の結果が同じ | commons の integration（`execute_pipeline`）、report・journal・stock の集計のテスト |
| C-6 | セッションの開始・commit・abort・終了が同じに働く | commons の integration（commit で書き込みが残り、abort で残らない、`async with` を抜けるとセッションが終わる）。cart（明示の commit）、journal・terminal（`async with`）のセッションを使う処理を、実際の MongoDB で通す |
| C-7 | 接続の終了が、作ったループの中で完了する。二重の終了で落ちない。別のループから呼ばれたら閉じずに警告を残す | commons の integration（同じループで閉じる、二重に閉じる、別のループから呼ぶ）。統合テストの出力にその警告が出ない。e2e のスタックの停止のログに閉じ忘れや例外がない |
| C-8 | 1つの接続が、作ったループからだけ使われる | 統合テスト（テストごとのループ）がすべて通る。commons の integration（ループが変わると作り直す）。stock のスケジューラーのテスト |
| C-9 | stock の全テナントの一覧が、呼ばれるたびに接続を作らない | stock の unit（`get_client_async` を差し替え、それが使われること） |
| C-10 | cart の DUAL と REQUIRED の両方で e2e が通る | DUAL で96件。REQUIRED は再起動し `docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE` で確かめてから、`-m "not dual_only"` で48件が通り48件が除外 |
| C-11 | `await` の付け忘れがない | unit / integration を `-W error::RuntimeWarning` で通す。`aggregate` / `list_indexes` / `close` / `start_transaction` の呼び出しを検索して確かめる（R-10） |
