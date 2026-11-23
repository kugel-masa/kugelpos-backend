# Implementation Plan: すべてのマスタの論理削除（is_deleted）

**Branch**: `324-master-logical-delete` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/324-master-logical-delete/spec.md`
**Issue**: [#324](https://github.com/kugel-masa/kugelpos-backend/issues/324)

## Summary

master-data の 8 種類のマスタ（分類・商品（共通）・店舗別商品・商品ブック・支払・プロモーション・設定・従業員）に、同じやり方で論理削除を持たせる。

- **共通の部品**: master-data に `app/models/repositories/logical_delete.py`（`NOT_DELETED`・`alive`・`soft_delete_async`・`restore_async`）を置く
- **repository**:
  - 読み取りのメソッドに `include_deleted` を足し、`{"is_deleted": {"$ne": True}}` を通す（項目の無い文書も「削除されていない」）
  - 削除は `is_logical=True` が既定
  - 件数も同じ絞り込みにする
- **service**:
  - 登録は「削除済みを含めて探し、削除済みなら要求の値で置き換えて復元」。復元する文書には作成と同じテナントの印を付ける。商品ブックは対象外（ID を採番する。採番は削除済みも使用中として扱う）
  - 更新・削除は削除済みを「見つからない」にする。更新の途中の削除も 404（500 にしない）
  - 中の要素の書き込み（支払のサブコード、商品ブックの中の要素）の絞り込みに `NOT_DELETED` を加える
  - 復元では `created_at` も今の時刻で付ける（置き換えは `updated_at` しか付けず、`created_at` が null だと応答の検証が壊れる）
  - プロモーションの `__make_query_filter` は `is_deleted: False` を埋め込んでいるので、キーだけの絞り込み（物理削除・復元に使う）と、有効なものの絞り込みに分ける
  - テナントのセットアップの初期データは、削除済みも含めて存在を確かめる
- **API**:
  - DELETE に `is_logical`（既定 true）を足す。商品は既定が false から true に変わる
  - GET の単体・一覧に `include_deleted`（既定 false）を足す。商品の `is_logical_deleted` は非推奨の別名として残す
  - 応答に `isDeleted` を加える
- **report**: 変えない（名前の解決は #326）
- **cart・terminal**: コードは変えない（通常の取得が削除済みを返さないことに依る）。テストで固定する

索引・データの移行は無い。

## Technical Context

**Language/Version**: Python 3.12+（他のサービスと同じ）
**Primary Dependencies**: FastAPI、Pydantic v2、Motor（MongoDB 非同期）、commons の `AbstractRepository`。新しい外部依存なし
**Storage**: テナントごとの MongoDB。8 つのコレクションの文書に `is_deleted`（任意）を足す。一意の索引は変えない
**Testing**: pytest（unit / integration / e2e の 3 層）、pytest-asyncio
**Target Platform**: Linux コンテナ（Docker Compose・Azure Container Apps）
**Project Type**: マイクロサービス（`services/<service>/app`）
**Performance Goals**:
- 絞り込みは一意の索引で 1 件に絞ったあとの条件、または一覧の追加の条件
- 一覧は `$ne` の条件が 1 つ増えるだけで、目立つ劣化はない
**Constraints**:
- 項目の無い既存の文書は「削除されていない」
- 応答の形は `isDeleted` を加える以外は変えない
- commons は変えない（論理削除は master-data に閉じる）
**Scale/Scope**: マスタごとに数百〜数万件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` で定まっている原則は「0. 言語規則」だけ（他は雛形のまま）。CLAUDE.md の規約を合わせて確認する。

| 項目 | 判定 | 根拠 |
|---|---|---|
| 言語規則（成果物は日本語、コードのコメント・ログは英語） | ✅ | spec・plan・research・data-model・contracts・quickstart は日本語 |
| API は `/api/v1/` で版付け、Pydantic のスキーマ、Transformer | ✅ | 既存の v1 のルートにクエリと応答の項目を足す |
| API 命名規約（snake_case のクエリ・パス引数） | ✅ | `is_logical`・`include_deleted` |
| リポジトリパターン・DB 操作は async | ✅ | 共通の部品も repository も async |
| エラーコード | ✅ | 新しいコードなし。既存の `DocumentNotFoundException`（404）・`DocumentAlreadyExistsException`（400） |
| テストの 3 層 | ✅ | unit（部品・service・API）、integration（実 MongoDB で 8 種類）、e2e（cart・terminal・report） |
| コメントアウトしたコードを残さない・型ヒント | ✅ | 実装時に守る |

**Phase 1 後の再確認**: 違反なし。Complexity Tracking は不要。

## Project Structure

### Documentation (this feature)

```text
specs/324-master-logical-delete/
├── spec.md
├── plan.md              # このファイル
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── master-data-logical-delete.md
├── checklists/requirements.md
└── tasks.md             # Phase 2（/speckit.tasks が作る）
```

### Source Code (repository root)

```text
services/master-data/app/
├── models/repositories/logical_delete.py        # 新規: 共通の部品
├── models/documents/*_master_document.py         # is_deleted: Optional[bool] = False（6 種類に追加、promotion は型を揃える）
├── models/repositories/*_master_repository.py    # 8 種類: include_deleted・件数・削除・復元
├── services/*_master_service.py                  # 8 種類: 登録の復元・更新・削除・取得の指定
├── api/common/schemas.py                         # 応答に is_deleted
├── api/common/schemas_transformer.py             # is_deleted を写す
├── api/v1/*_master.py                            # 8 種類: is_logical・include_deleted（商品は is_logical_deleted を別名に）
└── database/database_setup.py                     # 初期データの存在確認は削除済みも含める

docs/{en,ja}/master-data/api-specification.md     # 削除・取得の指定、復元、isDeleted
```

**Structure Decision**: 既存の構成のまま。共通の部品を master-data の repository の層に 1 つ足す。

## Phase 0: Research

[research.md](research.md) に記録した。要点:

- R-1: 今の削除と取得。`"is_deleted": False` は項目の無い文書を見落とし、商品の一覧は削除済みを絞っていない
- R-2: 共通の部品を master-data に置く（commons には入れない）
- R-3: 論理削除は有効なものだけ。物理削除は削除済みも対象
- R-4: 登録は「削除済みを含めて探し、削除済みなら置き換えて復元」。同時の復元は一方が「すでに存在する」
- R-5: 更新は削除済みを「見つからない」。書き込みにも絞り込みを掛ける
- R-6: 取得の指定・応答の `isDeleted`・準ずる取得の扱い
- R-7・R-8: 商品ブックの中の要素・支払のサブコード
- R-9〜R-11: cart・report・terminal は変えない（report の名前の解決は #326）
- R-14: テナントのセットアップは削除済みも含めて存在を確かめる
- R-12・R-13: 移行・索引なし

未解決の項目はない。

## Phase 1: Design

- [data-model.md](data-model.md): 項目、状態の遷移と操作の表、共通の部品、API の指定
- [contracts/master-data-logical-delete.md](contracts/master-data-logical-delete.md): DELETE・GET・POST・PUT の契約
- [quickstart.md](quickstart.md): 起動したスタックでの確認手順

## テスト方針

| 層 | 対象 |
|---|---|
| unit（共通の部品） | `alive` の写し（元の辞書を変えない）、`soft_delete_async`・`restore_async` の絞り込み |
| unit（service × 8） | 登録: なし・有効・削除済み（復元・同時の復元に負けた）。更新・削除: 削除済みは「見つからない」、更新の途中の削除は 404。物理削除は削除済みも消す。商品ブックの採番は削除済みの ID を使わない |
| unit（API × 8） | DELETE の `is_logical` の既定、GET の `include_deleted`、商品の `is_logical_deleted`、応答の `isDeleted` |
| integration（master-data、実 MongoDB × 8） | 状態の表（data-model §2）のすべての行。項目の無い既存の文書が取得・一覧・件数に出る。一覧の件数が絞り込みと一致する。復元後の `tenant_id`・`shard_key`・`store_code`。同じ削除済みのコードへの同時の登録（一方が 201・他方が 400、500 なし）と、存在しないコードへの同時の新規登録 |
| integration（準ずる取得・中の要素） | 店舗別の詳細、有効なプロモーション（指定なし・店舗指定・分類指定・店舗＋分類指定の各経路で、削除済みは出ず、項目の無い文書は出る）、設定の値、支払のサブコードの追加・変更（削除済みの支払方法では文書が変わらない）、商品ブックの詳細と中の要素の操作 |
| integration（更新と削除の競合） | 通常の更新・支払のサブコード・商品ブックの中の要素で、存在確認のあとに論理削除を挟むと 404 になり、削除済みの文書は変わらない |
| integration（復元の項目） | 復元の応答の `entryDatetime`（`created_at`）が今の時刻で、null でない |
| integration（照合） | 削除済みの従業員の照合は 404 / 405701 |
| integration（セットアップ） | 初期の設定を論理削除してからテナントのセットアップをやり直しても、重複にならず作り直さない |
| e2e | 商品・支払・プロモーション・設定を論理削除してキャッシュを無効にすると、cart で使われない。従業員を論理削除するとサインインできない（401 / 406004）。cart の新しい e2e はスナップショットを持ち回る形で書く（持ち回らないなら `dual_only` の印を付ける） |

## リリース

- 挙動の変化をリリースノートに書く
  - 全対象マスタの削除が、既定で論理削除になる（商品はこれまで物理削除が既定）
  - 削除したコードの登録が成功する（復元）
  - 削除済みは `include_deleted=true` で取得できる
  - 物理削除は `is_logical=false` で明示する
  - 商品（共通）の取得の `is_logical_deleted=true` が「削除済みだけ」から「削除済みも含める」に変わる
  - 商品（共通）を復元すると、残っていた店舗別商品がまた効く
  - 分類・プロモーションの一覧の応答の `metadata.filter` に削除済みの絞り込みが現れる
- commons は変えない（版は上げない）

## Complexity Tracking

違反なし。記載不要。
