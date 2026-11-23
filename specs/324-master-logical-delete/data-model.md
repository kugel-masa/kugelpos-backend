# Data Model: すべてのマスタの論理削除（is_deleted）

**Feature**: 324-master-logical-delete | **Date**: 2026-11-23

---

## 1. 文書（8 種類のマスタ）

各マスタの文書に次の項目を持たせる（商品・プロモーションは既存）。

| 項目 | 型 | 既定 | 意味 |
|---|---|---|---|
| is_deleted | Optional[bool] | False | 論理削除済みの印。項目が無い・`None`・`False` は「削除されていない」 |

| マスタ | コレクション | 一意のキー | 文書クラス |
|---|---|---|---|
| 分類 | master_category | (tenant_id, category_code) | CategoryMasterDocument |
| 商品（共通） | master_item_common | (tenant_id, item_code) | ItemCommonMasterDocument（既存） |
| 店舗別商品 | master_item_store | (tenant_id, store_code, item_code) | ItemStoreMasterDocument |
| 商品ブック | master_item_book | (tenant_id, item_book_id) | ItemBookMasterDocument |
| 支払 | master_payment | (tenant_id, payment_code) | PaymentMasterDocument |
| プロモーション | master_promotion | (tenant_id, promotion_code) | PromotionMasterDocument（既存。`bool` → `Optional[bool]`） |
| 設定 | master_settings | (tenant_id, name) | SettingsMasterDocument |
| 従業員 | master_staff | (tenant_id, id) | StaffMasterDocument |

一意の索引・その他の索引は変えない。

---

## 2. 状態

```text
（なし） --登録--> 有効 --論理削除--> 削除済み --登録（復元）--> 有効
                     |                    |
                     +--物理削除--> （なし） <--物理削除--+
```

| 操作 | 有効 | 削除済み | なし |
|---|---|---|---|
| 登録 | 「すでに存在する」 | 復元（要求の値で置き換え、`is_deleted=False`）→ 201。商品ブックは対象外（いつも新しい ID） | 新規 → 201 |
| 取得（通常） | 返す | 「見つからない」 | 「見つからない」 |
| 取得（`include_deleted=true`） | 返す | 返す（`isDeleted: true`） | 「見つからない」 |
| 一覧・件数（通常） | 含める | 含めない | — |
| 一覧・件数（`include_deleted=true`） | 含める | 含める | — |
| 更新 | 更新 | 「見つからない」 | 「見つからない」 |
| 論理削除（既定） | 削除済みへ | 「見つからない」 | 「見つからない」 |
| 物理削除（`is_logical=false`） | 消す | 消す | 「見つからない」 |

---

## 3. 共通の部品（`app/models/repositories/logical_delete.py`）

| 名前 | 役割 |
|---|---|
| `NOT_DELETED` | `{"is_deleted": {"$ne": True}}` |
| `alive(query_filter, include_deleted)` | `include_deleted` でなければ `NOT_DELETED` を加えた写し |
| `soft_delete_async(repo, key_filter) -> bool` | 有効なものだけを削除済みにする。一致が無ければ False |
| `restore_async(repo, key_filter, document) -> bool` | 削除済みのものだけを `document` で置き換える。一致が無ければ False。`document` には呼び出し側（各 repository の `restore_*_async`）が作成と同じ印（`tenant_id`・`shard_key`、店舗別商品は `store_code`）を付けておく |

---

## 4. API の指定

| 操作 | 指定 | 既定 | 備考 |
|---|---|---|---|
| DELETE（8 種類） | `is_logical: bool` | `true` | 商品は既定が `false` → `true` に変わる |
| GET 単体・一覧（8 種類） | `include_deleted: bool` | `false` | 新規 |
| GET 商品（共通）単体 | `is_logical_deleted: bool` | `false` | 非推奨の別名。`include_deleted` と OR |

応答: 各マスタの応答に `isDeleted`（`is_deleted`）を加える。応答のスキーマですでに持つのは商品（`BaseItemResponse`・`BaseItemStoreDetailResponse`）だけ。プロモーションは文書だけが持ち、応答には新しく加える。

---

## 5. 他のサービス

| サービス | 変更 |
|---|---|
| cart | なし（通常の取得が削除済みを返さない） |
| report | なし（名前の解決は #326） |
| terminal | なし（照合の取得が削除済みを返さない → 405701） |
