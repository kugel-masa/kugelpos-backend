# Research: すべてのマスタの論理削除（is_deleted）

**Feature**: 324-master-logical-delete | **Date**: 2026-11-23

コードを読んで確かめた事実と、それに基づく決定を記録する。

---

## R-1 今の削除と取得

**事実**

| マスタ | 削除（repository） | 取得の絞り込み | `is_deleted` の項目 |
|---|---|---|---|
| 分類 `master_category` | `delete_async`（物理） | なし | なし |
| 商品（共通）`master_item_common` | 既定は物理、`is_logical=True` で `update_one_async({..."is_deleted": {"$ne": True}}, {"is_deleted": True})` | 単体は `"is_deleted": is_logical_deleted`（一致）、一覧は絞り込みなし | あり（`Optional[bool] = False`） |
| 店舗別商品 `master_item_store` | 物理 | なし | なし |
| 商品ブック `master_item_book` | 物理 | なし | なし |
| 支払 `master_payment` | 物理 | なし | なし |
| プロモーション `master_promotion` | 常に論理（`update_one_async`） | `"is_deleted": False`（一致） | あり（`bool = False`） |
| 設定 `master_settings` | 物理 | なし | なし |
| 従業員 `master_staff` | 物理 | なし | なし |
| 税 | 削除の API なし | — | — |

- `"is_deleted": False` は項目が無い文書に一致しない。商品の単体の取得とプロモーションの取得は、項目の無い古い文書を見落とす
- 商品の一覧の取得は削除済みを絞っていないので、論理削除した商品が一覧に出る（既存の不具合）
- 一覧の件数は各 repository の `count_documents({})` や `get_*_count_async()` で、絞り込みを持たない

- プロモーションの `__make_query_filter` は `is_deleted: False` をキーの条件に埋め込んでいる（他の 7 種類はキーだけ）

**決定**: 絞り込みは全マスタで `{"is_deleted": {"$ne": True}}`（項目の無い文書も「削除されていない」）。プロモーションの `__make_query_filter` はキーだけにし、有効なものの絞り込みは `alive` で加える（物理削除・復元はキーだけで探す）。単体・一覧・件数・サービス内部の参照のすべてに掛ける（spec FR-005・FR-008）。

---

## R-2 共通の部品

**事実**: 8 つの repository は commons の `AbstractRepository` を継承し、`get_one_async`・`get_list_async_with_sort_and_paging`・`get_paginated_list_async`・`update_one_async`・`replace_one_async`・`delete_async` を使う。それぞれ独自の `__make_query_filter` を持つ。

**決定**: master-data に小さな共通の部品 `app/models/repositories/logical_delete.py` を作る。

- `NOT_DELETED = {"is_deleted": {"$ne": True}}`
- `alive(query_filter, include_deleted)`: `include_deleted` でなければ `NOT_DELETED` を加えた写しを返す
- `soft_delete_async(repo, key_filter)`: `update_one_async(key_filter + NOT_DELETED, {"is_deleted": True})`。一致が無ければ False（「見つからない」）
- `restore_async(repo, key_filter, document)`: `replace_one_async(key_filter + {"is_deleted": True}, document)`。一致が無ければ False（同時に別の要求が復元した）
- **復元する文書には、作成と同じ印を付けてから渡す**: `tenant_id`・`shard_key`（店舗別商品は `store_code` も）と `created_at`（今の時刻。置き換えは `updated_at` しか付けず、`created_at` が null だと応答の検証が壊れる）は各 repository の `create_*_async` の中でだけ付けていて、`replace_one_async` は `updated_at` しか付けない。そのまま置き換えると、テナントの絞り込みのある取得から消える。各 repository に `restore_*_async(document)` を足し、作成と同じ付け方をしてから `restore_async` を呼ぶ

各 repository は読み取りのメソッドに `include_deleted: bool = False` を足し、`alive` を通す。削除は `delete_*_async(code, is_logical=True)` に揃える。

**代替案**: commons の `AbstractRepository` に組み込む → 却下。commons は全サービスの repository の基底で、論理削除はマスタだけの関心事。master-data の中に閉じる。

---

## R-3 削除

**決定**
- 論理削除: `soft_delete_async`。存在しない・論理削除済みは「見つからない」（既存の `CannotDeleteException` 系を、#312 と同じく 404 で返す）
- 物理削除: `delete_async(key_filter)`（論理削除済みも対象）。存在しなければ 404
- 削除のたびに `updated_at` を更新する（`update_one_async` が付ける）

---

## R-4 削除済みのコードでの登録（復元）

**事実**: 各サービスの登録は「`get_*`（削除済みを見ない）で存在を確かめ、無ければ `create_async`」。論理削除済みのコードでは存在確認を通り抜け、挿入で一意索引にぶつかる（商品・プロモーションで今起きている。`DuplicateKeyException`、400）。

**決定**
1. `get_*(include_deleted=True)` で探す
2. 無ければ新規に挿入（今と同じ）
3. 削除されていなければ「すでに存在する」（今と同じ）
4. 論理削除済みなら、要求の値で新しい文書を作り（`is_deleted=False`、`created_at` は今の時刻）、repository の `restore_*_async` で置き換える。一致しなかった（同時の復元に負けた、または同時に物理削除された）ら「すでに存在する」（後者の 400 は既知の小さな食い違いとして残す）
- `_id` は文書の型が持たないので、置き換えでも保たれる
- **商品ブックは対象外**: ID はサーバーが採番し（`__generate_item_book_id`）、登録の要求に ID が無い。採番の存在確認は削除済みも含めて行う（`include_deleted=True`）。そうしないと、削除済みの ID を空きとみなし、挿入が一意索引にぶつかり続ける
- 置き換えなので、前の値のうち要求に無いものは残らない（spec FR-009）
- 応答は新規の登録と同じ（201）

**同時の登録**: 2 つの新規の登録の競合は、今と同じく一方が一意索引で失敗する（`DuplicateKeyException`、400）。500 にはならない（spec FR-012）。2 つの復元の競合は、一方が置き換え、もう一方は一致が無く「すでに存在する」（既存の `DocumentAlreadyExistsException`、400）。

---

## R-5 更新

**事実**: 各 repository の `update_*_async` は、`update_one_async` が False を返すと素の `Exception` を投げる（例: `category_master_repository.py`）。

**決定**: 更新の存在確認（`get_*`）は削除済みを見ないので、論理削除済みの更新は「見つからない」になる。更新の書き込みの絞り込みにも `NOT_DELETED` を加え、確認と書き込みの間に削除されたものを書き換えない。その場合（書き込みが一致しない）は `DocumentNotFoundException`（404）にし、素の `Exception`（500）にしない。

---

## R-6 取得の指定

**決定**
- 全マスタの単体・一覧の取得に `include_deleted: bool = Query(False)` を足す
- 商品（共通）の単体の取得の `is_logical_deleted` は、非推奨の別名として残す（どちらかが true なら含める）
- 応答に `is_deleted`（`isDeleted`）を加える。応答のスキーマで持っているのは商品だけ（`BaseItemResponse`・`BaseItemStoreDetailResponse`）。プロモーションは文書だけが持ち、`BasePromotionResponse` には無いので加える
- `is_logical_deleted` は今、完全一致の条件（`true` なら削除済みの商品だけ、有効な商品は 404）。別名にすると「削除済みも含める」に意味が変わる（spec の挙動の変化）
- `is_logical_deleted=False` を名前付きで渡している呼び出し元がある（`item_store_master_service.py`・`item_book_master_service.py`）。引数の名前を変えるときに合わせて直す
- 店舗別の詳細（`/stores/{store_code}/items/{item_code}/details`）は、商品（共通）が削除済みなら「見つからない」。店舗別商品だけが削除済みなら、店舗別の上書きが無いときと同じ扱い（共通の値）
- プロモーションの有効なものの取得（`/promotions/active`）は、すでに削除済みを除いている（`"is_deleted": False` を `NOT_DELETED` に直す）
- 設定の値の取得（`/settings/{name}/value`）は、削除済みなら「見つからない」（cart は既定値を使う）

---

## R-7 商品ブックの中の要素

**事実**: 分類・タブ・ボタンの削除は、1 つの文書の中の配列の要素を `$pull` で消す。

**事実**: 中の要素の書き込み（`__apply_nested_update_async`・`__empty_null_list_async`・`add_*`・`set_*`・`delete_*`）は、商品ブックの ID だけの絞り込みで直接書く。

**決定**: 物理削除のまま（spec FR-017）。商品ブックそのものが論理削除済みなら、中の要素の操作は「見つからない」。サービスの存在確認に加え、**書き込みの絞り込みにも `NOT_DELETED` を加え**、確認と書き込みの間に削除された商品ブックを書き換えない。

---

## R-8 支払方法のサブコード（#311）

**事実**: サブコードの追加・変更（`add_variant_async`・`update_variant_async`）は、事前の存在確認なしに先に `update_one` で書き込み、支払方法の取得はその後（`payment_master_service.py`）。

**決定**: サブコードは支払マスタの文書に内包されるので、支払方法の論理削除とともに見えなくなる。**追加・変更の書き込みの絞り込みに `NOT_DELETED` を加え**、削除済みの支払方法には書き込まない（一致しなければ「見つからない」）。復元の登録では、サブコードは要求の値（省略なら無し）。

---

## R-9 cart

**事実**: cart は master-data の通常の取得（商品の店舗別の詳細、支払の単体、プロモーションの有効なもの、設定の値）を使い、Dapr の状態ストア（`masterstore`、既定 600 秒）にキャッシュする。master-data から cart へ変更を知らせる仕組みは無く、更新もキャッシュの有効期間か明示の無効化（`DELETE /api/v1/cache/master-data`）で反映される。

**決定**: cart のコードは変えない。master-data の通常の取得が削除済みを返さないので、キャッシュが切れたあとは「存在しない」になる（spec FR-013・Assumptions）。e2e ではキャッシュを無効にしてから確かめる。

---

## R-10 report（本フィーチャーでは変えない）

**事実**
- report の `CategoryMasterWebRepository` は `GET /tenants/{tenant_id}/categories` を、`ItemMasterWebRepository` は `GET /tenants/{tenant_id}/items` を呼び、コードから名前を引く
- `item_codes` を付けているが、master-data の商品の一覧はこの指定を受け付けていない（既存の挙動。全件の 1 ページ目が返る）
- どちらもページングを辿らない（既定 100 件。既存の挙動）

- 商品名は応答の `itemName` を読むが、応答の項目は `description`。今も商品名は常に商品コードで出る（既存の不具合）
- 支払レポートも支払一覧から支払方法の名前を引く（#313 で全ページ）。無い支払方法は `Payment {code}`

**決定**: report は変えない。本フィーチャーだけでも、削除したマスタはレポートでコードで出る（今の物理削除と同じ）ので、悪くはならない。名前の解決（商品・支払は取引ログの販売時の名前、分類は全ページ＋`include_deleted=true`）は #326 で扱う。

---

## R-11 terminal（#323）

**事実**: 照合は `StaffMasterService.verify_staff_async` → `get_staff_by_id_async`。

**決定**: `get_staff_by_id_async` の既定（削除済みを見ない）で、削除済みの従業員は `None` → 405701 になる。照合のコードは変えず、テストで固定する（spec FR-015）。

---

## R-12 既存の文書の移行

**決定**: 移行しない。`NOT_DELETED` は項目の無い文書を「削除されていない」として扱う（spec FR-008）。文書の型の `is_deleted` は `Optional[bool] = False` に揃える。

---

## R-13 索引

**事実**: 各コレクションの一意索引は `(tenant_id, コード)`。

**決定**: 変えない。削除済みもコードを占めるので、登録は復元になる（R-4）。`is_deleted` での絞り込みは、一意索引で 1 件に絞った後の条件なので、索引は足さない。

---

## R-14 テナントのセットアップの初期データ

**事実**: `database_setup.py` は初期の設定（`RECEIPT_NO_*` など）を、repository の既定の取得で存在を確かめてから作る。

**決定**: 存在確認を `include_deleted=True` にする。論理削除された初期の設定を作り直そうとして、セットアップのたびに重複になるのを防ぐ（spec FR-012b）。戻したいときは登録で復元する。
