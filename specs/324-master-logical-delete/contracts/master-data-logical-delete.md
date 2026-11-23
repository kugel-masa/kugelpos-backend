# Contract: master-data の論理削除

**Feature**: 324-master-logical-delete

対象: 分類 `/categories`、商品（共通）`/items`、店舗別商品 `/stores/{store_code}/items`、商品ブック `/item_books`、支払 `/payments`、プロモーション `/promotions`、設定 `/settings`、従業員 `/staff`（いずれも `/api/v1/tenants/{tenant_id}` の下）。権限は既存の各操作と同じ。

## DELETE `.../{code}`

| クエリ | 型 | 既定 | 意味 |
|---|---|---|---|
| `is_logical` | bool | `true` | `true`: 論理削除。`false`: 物理削除 |

| 状態 | `is_logical=true` | `is_logical=false` |
|---|---|---|
| 有効 | 200（削除済みにする） | 200（消す） |
| 論理削除済み | 404 | 200（消す） |
| なし | 404 | 404 |

応答の形は各マスタの既存の削除の応答のまま。

**挙動の変化**: 商品（共通）の DELETE の既定は `false` から `true` に変わる。他の 6 種類（プロモーションを除く）は、これまで物理削除だけだった。プロモーションは常に論理削除だったが、`is_logical=false` で物理削除できるようになる。

## GET `.../{code}`、GET 一覧

| クエリ | 型 | 既定 | 意味 |
|---|---|---|---|
| `include_deleted` | bool | `false` | `true` なら削除済みも返す |
| `is_logical_deleted`（商品の単体だけ） | bool | `false` | 非推奨。`include_deleted` と同じ意味（どちらかが true なら含める） |

- 通常（`include_deleted=false`）: 削除済みは単体では 404、一覧・件数（`metadata.total`）には含めない
- `include_deleted=true`: 削除済みも返し、件数にも含める
- 応答の各レコードに `isDeleted`（bool）が付く

### 準ずる取得

| 取得 | 削除済みの扱い |
|---|---|
| `GET /stores/{store_code}/items/{item_code}/details` | 商品（共通）が削除済みなら 404。店舗別商品だけが削除済みなら、店舗別の上書きが無いのと同じ |
| `GET /promotions/active` | 含めない |
| `GET /settings/{name}/value` | 404 |
| `GET /payments/{payment_code}/variants...` | 支払方法が削除済みなら 404 |
| 商品ブックの中の分類・タブ・ボタンの操作 | 商品ブックが削除済みなら 404 |

`include_deleted` は単体・一覧の取得にだけ付ける。準ずる取得には付けない（販売などの利用のための取得なので）。

## POST（登録）

| 状態 | 結果 |
|---|---|
| なし | 201（新規） |
| 有効 | 400「すでに存在する」（既存の `DocumentAlreadyExistsException` のまま） |
| 論理削除済み | 201（復元: 要求の値で置き換え、`isDeleted: false`。前の値は残らない） |

商品ブックは対象外: ID はサーバーが採番するので、登録はいつも新しい ID で作る。削除済みの ID は再利用しない。

同時の要求: 2 つの新規の登録は今と同じく一方が重複で失敗する。2 つの復元は一方が成功し、もう一方は 400「すでに存在する」。いずれも 500 にはならない。

## PUT（更新）

論理削除済みは 404（存在しないのと同じ）。更新の途中で削除されたときも 404（500 にしない）。

中の要素の操作（支払のサブコードの追加・変更、商品ブックの中の分類・タブ・ボタン）も、親が論理削除済みなら 404 で、文書は変わらない。

## 変わらないもの

- 税マスタ
- 商品ブックの中の分類・タブ・ボタンの削除（物理削除のまま）
- 応答の形（`isDeleted` を加える以外）
