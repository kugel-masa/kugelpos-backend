---
description: "Task list for 324-master-logical-delete"
---

# Tasks: すべてのマスタの論理削除（is_deleted）

**Input**: `/specs/324-master-logical-delete/` の spec.md・plan.md・research.md・data-model.md・contracts/・quickstart.md
**Issue**: [#324](https://github.com/kugel-masa/kugelpos-backend/issues/324)

**Tests**: plan.md の「テスト方針」に従い、各ストーリーにテストを含める（unit → integration → e2e）。テストは実装の前に書き、失敗することを確かめてから実装する。

**Organization**: 共通の部品と文書・応答の項目を Phase 1・2 に置く。US1（論理削除と取得）・US2（復元）・US3（物理削除）はマスタごとに同じファイルを触るので、マスタごとのタスクを [P] で並べる（別のマスタは別のファイル）。US1・US2 が P1、US3・US4 が P2。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並行して進められる（別のファイル・未完了のタスクに依存しない）
- **[Story]**: 対応するユーザーストーリー（US1〜US4）
- パスはリポジトリのルートからの相対パス。`MD` = `services/master-data`

## 共通の規約（全タスク）

- コード・コメント・ログは英語。型ヒント必須。DB 操作は async
- 変更したファイルで ruff の指摘を増やさない
- 新しいテストは正しい層のディレクトリに置く
- 判断の根拠は research.md の R-番号を参照する
- 8 種類のマスタ: 分類（category）・商品（共通）（item_common）・店舗別商品（item_store）・商品ブック（item_book）・支払（payment）・プロモーション（promotion）・設定（settings）・従業員（staff）

---

## Phase 1: Setup（共通の部品）

- [X] T001 `MD/tests/unit/test_logical_delete.py` を新設し、`alive`（`include_deleted=False` で `NOT_DELETED` を加えた写しを返し、元の辞書を変えない／`True` でそのまま）、`soft_delete_async`（`update_one_async` に `key + NOT_DELETED` と `{"is_deleted": True}` を渡し、戻り値をそのまま返す）、`restore_async`（`replace_one_async` に `key + {"is_deleted": True}` と文書を渡す）をモックの repository で確かめる
- [X] T002 `MD/app/models/repositories/logical_delete.py` を新設し、`NOT_DELETED`・`alive`・`soft_delete_async`・`restore_async` を実装する（data-model §3・R-2）。T001 を通す

---

## Phase 2: Foundational（文書・応答の項目）

**⚠️ CRITICAL**: 以降のストーリーはこの項目に依存する

- [X] T003 [P] 6 種類の文書（`category_master_document.py`・`item_store_master_document.py`・`item_book_master_document.py`・`payment_master_document.py`・`settings_master_document.py`・`staff_master_document.py`）に `is_deleted: Optional[bool] = False` を足し、`promotion_master_document.py` の `is_deleted` を `Optional[bool] = False` に揃える（data-model §1・R-12）
- [X] T004 `MD/api/common/schemas.py` の 8 種類の応答（`BaseCategoryMasterResponse`・`BaseItemStoreResponse`・`BaseItemBookResponse`・`BasePaymentResponse`・`BasePromotionResponse`・`BaseSettingsMasterResponse`・`BaseStaffResponse`、商品は既存）に `is_deleted: bool = False` を足し、`MD/app/api/common/schemas_transformer.py`（と、それを継承する `MD/app/api/v1/schemas_transformer.py`）で文書の値（`None` は `False`）を写す（R-6）
- [X] T005 `MD/tests/unit/test_logical_delete_response_field.py` を新設し、8 種類の transformer が `is_deleted` を `isDeleted` として写すこと、文書に項目が無い・`None` なら `false` になることを確かめる

**Checkpoint**: 項目が揃い、既存の単体テストが通る

---

## Phase 3: User Story 1 - 削除してもマスタの記録が残る (Priority: P1) 🎯 MVP

**Goal**: 8 種類のマスタで、指定なしの削除が論理削除になり、通常の取得・一覧・件数から消え、`include_deleted=true` で見える。削除済みの更新・中の要素の操作は 404（spec FR-001・FR-003・FR-005〜FR-008・FR-011）

**Independent Test**: 各マスタで 1 件登録して削除し、通常の取得で 404・一覧と件数に出ない・`include_deleted=true` で `isDeleted: true` で見える・更新と再度の論理削除が 404、を確かめる（spec US1 のシナリオ 1〜6）

### Tests for User Story 1

- [X] T006 [P] [US1] `MD/tests/integration/test_logical_delete_masters.py` を新設し、8 種類のマスタをパラメータ化して実 MongoDB で確かめる: 論理削除（指定なし）→ 通常の単体で 404・一覧と `metadata.total` に含まれない・`include_deleted=true` の単体と一覧で `isDeleted: true`・更新で 404・再度の論理削除で 404。`is_deleted` の項目を持たない文書を直接挿入し、単体・一覧・件数に出ることも確かめる（data-model §2）
- [X] T007 [P] [US1] `MD/tests/integration/test_logical_delete_nested.py` を新設し、削除済みの親への中の要素の操作が 404 で文書が変わらないことを確かめる: 支払のサブコードの追加・変更、商品ブックの分類・タブ・ボタンの追加・変更・削除、商品ブックの詳細の取得（R-7・R-8）。有効な商品ブックの中の要素の削除は物理削除のまま（削除した要素は `include_deleted=true` の取得でも出ない。spec FR-017）
- [X] T008 [P] [US1] `MD/tests/integration/test_logical_delete_quasi_reads.py` を新設し、準ずる取得を確かめる: 店舗別の詳細（商品（共通）が削除済みなら 404、店舗別商品だけが削除済みなら共通の値）、有効なプロモーション（指定なし・店舗指定・分類指定・店舗＋分類指定の各経路で削除済みが出ず、項目の無い文書は出る）、設定の値（削除済みなら 404）（R-6）。cart の gRPC の商品取得（`MD/app/grpc/item_service_impl.py`）も同じ `get_item_store_detail_by_code_async` を通るので、`MD/tests/unit/test_grpc_item_service_auth.py` と同じ形で、商品（共通）が削除済みなら gRPC も「見つからない」になる単体テストを 1 件足す
- [X] T009 [P] [US1] `MD/tests/integration/test_logical_delete_update_race.py` を新設し、通常の更新・支払のサブコード・商品ブックの中の要素で、存在確認のあとに論理削除を挟む（サービスの存在確認をパッチして削除してから書き込ませる）と 404 になり、削除済みの文書が変わらないことを確かめる（R-5）
- [X] T010 [P] [US1] 8 種類の `MD/tests/unit/test_api_*.py`（無いものは新設）に、DELETE が `is_logical` の既定 `true` でサービスへ渡ること、GET の単体・一覧が `include_deleted` を渡すこと、商品の単体の `is_logical_deleted=true` が `include_deleted` と同じに扱われることを足す

### Implementation for User Story 1（マスタごと。別のファイルなので並行できる）

各マスタで次を行う（R-1〜R-3・R-5〜R-8）:
- repository: 読み取り（単体・一覧・ページング・件数）に `include_deleted: bool = False` を足して `alive` を通す。`delete_*_async(code, is_logical=True)`（論理は `soft_delete_async`、物理は `delete_async`）。更新の書き込みの絞り込みに `NOT_DELETED` を加え、一致しなければ `False` を返す（素の `Exception` を投げない）
- service: 取得・一覧に `include_deleted` を通す。削除は `is_logical` を受け、一致しなければ `DocumentNotFoundException`。更新は書き込みが一致しなければ `DocumentNotFoundException`
- API: DELETE に `is_logical: bool = Query(True)`、GET の単体・一覧に `include_deleted: bool = Query(False)`

- [X] T011 [P] [US1] 分類: `MD/app/models/repositories/category_master_repository.py`・`MD/app/services/category_master_service.py`・`MD/app/api/v1/category_master.py`
- [X] T012 [P] [US1] 商品（共通）: `item_common_master_repository.py`・`item_common_master_service.py`・`item_common_master.py`。単体の取得の完全一致の条件（`"is_deleted": is_logical_deleted`）を `alive` に置き換え、`is_logical_deleted` を `include_deleted` の非推奨の別名にする。DELETE の `is_logical` の既定を `true` にする。`is_logical_deleted=False` を名前で渡している `item_store_master_service.py`・`item_book_master_service.py` を直す（R-6）
- [X] T013 [P] [US1] 店舗別商品（T012 の後。T012 で変える `is_logical_deleted` の呼び出しを含むため）: `item_store_master_repository.py`・`item_store_master_service.py`・`item_store_master.py`。店舗別の詳細は商品（共通）が削除済みなら 404、店舗別商品だけが削除済みなら上書き無しとして扱う
- [X] T014 [P] [US1] 商品ブック（T012 の後。同上）: `item_book_master_repository.py`・`item_book_master_service.py`・`item_book_master.py`。中の要素の書き込み（`__apply_nested_update_async`・`__empty_null_list_async`・`add_*`・`set_*`・`delete_*`）の絞り込みに `NOT_DELETED` を加える（R-7）
- [X] T015 [P] [US1] 支払: `payment_master_repository.py`・`payment_master_service.py`・`payment_master.py`。`add_variant_async`・`update_variant_async` の絞り込みに `NOT_DELETED` を加え、一致しなければ 404（R-8）
- [X] T016 [P] [US1] プロモーション: `promotion_master_repository.py`・`promotion_master_service.py`・`promotion_master.py`。`__make_query_filter` をキーだけにし、有効なものの絞り込みを `alive` で加える。`"is_deleted": False` の 5 か所（一覧・有効なもの 3 経路）を `NOT_DELETED` に置き換える。DELETE に `is_logical`（既定 true）を足す（R-1・R-6）
- [X] T017 [P] [US1] 設定: `settings_master_repository.py`・`settings_master_service.py`・`settings_master.py`。設定の値の取得は削除済みを見ない
- [X] T018 [P] [US1] 従業員: `staff_master_repository.py`・`staff_master_service.py`・`staff_master.py`
- [X] T019 [US1] T006〜T010 が通ることを確かめる

**Checkpoint**: 8 種類で論理削除と取得が揃う

---

## Phase 4: User Story 2 - 削除したコードをもう一度登録すると復元される (Priority: P1)

**Goal**: 商品ブックを除く 7 種類で、削除済みのコードの登録が復元になる。商品ブックは新しい ID で作る（spec FR-009・FR-010・FR-012・FR-012a）

**Independent Test**: 7 種類で登録→削除→別の値で登録し、201 で新しい値・`isDeleted: false`・前の値が残らない・テナントの印と `entryDatetime` が付く、を確かめる。商品ブックは削除後の登録が別の ID になる（spec US2 のシナリオ 1〜5）

### Tests for User Story 2

- [X] T020 [P] [US2] `MD/tests/integration/test_logical_delete_restore.py` を新設し、7 種類をパラメータ化して実 MongoDB で確かめる: 復元の 201・新しい値・`isDeleted: false`・前の値のうち要求に無いものが残らない・復元後に通常の取得と一覧に出る（`tenant_id`・`shard_key`・店舗別商品の `store_code` が付いている）・`entryDatetime` が今の時刻で null でない。削除されていないコードの登録は 400「すでに存在する」のまま
- [X] T021 [P] [US2] 同じファイルに、同じ削除済みのコードへの同時の登録（`asyncio.gather`）で一方が 201・他方が 400、存在しないコードへの同時の新規登録で一方が 201・他方が 400、いずれも 500 にならないことを足す（R-4・spec FR-012）
- [X] T022 [P] [US2] 同じファイルに、商品ブックを登録して論理削除し、もう一度登録すると別の ID になり、削除済みの ID は `include_deleted=true` で削除済みのまま見えることを足す（R-4）
- [X] T023 [P] [US2] 8 種類の `MD/tests/unit/test_*_master_service.py` に、登録の分岐（なし→新規、有効→すでに存在する、削除済み→`restore_*_async`、`restore_*_async` が False→すでに存在する）をモックで足す

### Implementation for User Story 2

各マスタ（商品ブックを除く）で次を行う（R-4）:
- repository: `restore_*_async(document)` を足す。作成と同じく `tenant_id`・`shard_key`（店舗別商品は `store_code`）を付け、`created_at` を今の時刻にし、`is_deleted=False` にして `restore_async(self, key_filter, document)` を呼ぶ
- service: 登録の存在確認を `include_deleted=True` にし、削除済みなら要求の値で文書を作って `restore_*_async`。False なら `DocumentAlreadyExistsException`

- [X] T024 [P] [US2] 分類（`category_master_repository.py`・`category_master_service.py`）
- [X] T025 [P] [US2] 商品（共通）（`item_common_master_repository.py`・`item_common_master_service.py`）
- [X] T026 [P] [US2] 店舗別商品（`item_store_master_repository.py`・`item_store_master_service.py`）
- [X] T027 [P] [US2] 支払（`payment_master_repository.py`・`payment_master_service.py`）。復元ではサブコードは要求の値（省略なら無し）
- [X] T028 [P] [US2] プロモーション（`promotion_master_repository.py`・`promotion_master_service.py`）。復元はキーだけの絞り込みで探す
- [X] T029 [P] [US2] 設定（`settings_master_repository.py`・`settings_master_service.py`）
- [X] T030 [P] [US2] 従業員（`staff_master_repository.py`・`staff_master_service.py`）
- [X] T031 [US2] 商品ブック: `item_book_master_service.py` の `__generate_item_book_id` の存在確認を `include_deleted=True` にする（削除済みの ID を使用中として扱う）
- [X] T032 [US2] T020〜T023 が通ることを確かめる

**Checkpoint**: P1（US1・US2）が完成

---

## Phase 5: User Story 3 - 物理削除は明示したときだけ (Priority: P2)

**Goal**: `is_logical=false` で有効なもの・論理削除済みのものが消え、存在しないコードは 404（spec FR-002・FR-004）

### Tests for User Story 3

- [X] T033 [P] [US3] T006 のファイルに、8 種類で `is_logical=false` の物理削除（有効なもの・論理削除済みのもの）のあと `include_deleted=true` でも 404、存在しないコードは論理・物理とも 404 を足す

### Implementation for User Story 3

- [X] T034 [US3] T011〜T018 で入れた物理削除の分岐（キーだけの絞り込みで `delete_async`）が、論理削除済みのものも消すことを確かめ、足りなければ直す（プロモーションはキーだけの絞り込みを使う）。T033 を通す

---

## Phase 6: User Story 4 - 他のサービスが削除済みのマスタを正しく扱う (Priority: P2)

**Goal**: cart は削除済みの商品・支払・プロモーション・設定を使わず、terminal は削除済みの従業員をサインインさせない。テナントのセットアップは削除済みの初期データを作り直さない（spec FR-012b・FR-013・FR-015）

### Tests for User Story 4

- [X] T035 [P] [US4] `MD/tests/integration/test_staff_verify.py` に、論理削除した従業員の照合が 404 / 405701 になることを足す（R-11）
- [X] T036 [P] [US4] `MD/tests/integration/test_settings_seed.py`に、初期の設定を論理削除してからテナントのセットアップをやり直しても、重複にならず作り直さないことを足す（R-14）
- [X] T037 [P] [US4] `services/cart/tests/e2e/test_deleted_masters.py` を新設し、商品・支払・プロモーション・設定を論理削除してから cart のキャッシュを無効にすると、商品は販売できず、支払方法は使えず、プロモーションの割引は付かず、設定は既定値になることを確かめる。スナップショットを持ち回る形で書き、`dual_only` を付けない（`services/cart/tests/e2e/test_payment_master_settings.py` に倣う）
- [X] T038 [P] [US4] `services/terminal/tests/e2e/test_sign_in_pin.py` に、論理削除した従業員でのサインインが 401 / 406004（存在しない従業員と同じ本文）になることを足す

### Implementation for User Story 4

- [X] T039 [US4] `MD/app/database/database_setup.py` の初期データの存在確認を `include_deleted=True` にする（R-14）
- [X] T040 [US4] T035〜T038 が通ることを確かめる（cart・terminal のコードは変えない。R-9・R-11）

---

## Phase 7: 文書・仕上げ

- [X] T041 [P] `docs/en/master-data/api-specification.md`・`docs/ja/master-data/api-specification.md` に、8 種類の DELETE の `is_logical`（既定 true）、GET の `include_deleted`、商品の `is_logical_deleted` が非推奨の別名になったこと、登録が削除済みを復元すること（商品ブックを除く）、応答の `isDeleted` を書く
- [X] T042 変更したファイルで ruff の指摘が増えていないことを確かめる
- [X] T043 全サービスのイメージを作り直し、単体・統合・e2e（サービス横断を含む）をすべて通す。既存の e2e で、マスタを削除してから同じコードで作り直す、または削除後に一覧の件数を見るテストが、論理削除の既定で失敗しないかを確かめ、失敗したら意図を確かめて直す。既存の応答のテストが変更なしで通ること（応答の形は `isDeleted` と、分類・プロモーションの `metadata.filter` 以外は変わらない。spec FR-016）
- [ ] T044 quickstart.md の手順 1〜5 を、起動したスタックで確かめる
- [ ] T045 PR の本文の「挙動の変化」に spec の Behaviour Change の全項目を書く（リリースノートの下書き）

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2 → Phase 3〜6**
- **US1（Phase 3）→ US2・US3**: 復元・物理削除は US1 の repository の読み取りと削除の分岐を前提にする
- **US4** は US1 の後（削除済みが通常の取得から消えることに依る）。US2・US3 とは独立
- 各フェーズの中で、マスタごとのタスク（[P]）は別のファイルなので並行できる。ただし T012（商品の引数の名前）と T013・T014（呼び出し元）は同じ変更を共有するので、T012 を先に終える
- **Phase 7** は全ストーリーの後

## Parallel Example

```text
# US1 の実装はマスタごとに並行
T011 分類   T013 店舗別商品   T015 支払   T017 設定
T012 商品   T014 商品ブック   T016 プロモーション   T018 従業員

# US1 のテストは並行
T006 状態の表   T007 中の要素   T008 準ずる取得   T009 更新の競合   T010 API
```

## Implementation Strategy

1. **MVP**: Phase 1・2・3（US1）。削除しても記録が残り、通常の取得から消える
2. **P1 の完成**: Phase 4（US2）。論理削除にすると削除済みがコードを占めるので、US1 と同時にリリースする（US1 だけでは削除したコードを二度と使えない）
3. **P2**: Phase 5（US3）・Phase 6（US4）
4. **仕上げ**: Phase 7。リリースノートに挙動の変化を書く
