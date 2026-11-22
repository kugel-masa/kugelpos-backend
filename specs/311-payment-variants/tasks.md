---
description: "Task list for 311-payment-variants"
---

# Tasks: 支払マスタのサブコード（派生）による支払の分類

**Input**: `/specs/311-payment-variants/` の spec.md・plan.md・research.md・data-model.md・contracts/・quickstart.md
**Issue**: [#311](https://github.com/kugel-masa/kugelpos-backend/issues/311)

**Tests**: plan.md の「テストの方針」に従い、各ストーリーにテストを含める（unit → integration → e2e）。テストは実装の前に書き、失敗することを確かめてから実装する。

**Organization**: ユーザーストーリーごとにフェーズを分ける。US1・US2 が P1、US3・US4 が P2。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並行して進められる（別のファイル・未完了のタスクに依存しない）
- **[Story]**: 対応するユーザーストーリー（US1〜US4）
- パスはリポジトリのルートからの相対パス

## 共通の規約（全タスク）

- コード・コメント・ログは英語。型ヒント必須。DB 操作は async
- 変更したサービスでは `pipenv run ruff check app/` と `pipenv run ruff format app/` を通す
- 新しいテストは正しい層のディレクトリ（`tests/unit/`・`tests/integration/`・`tests/e2e/`）に置く（conftest が自動で印を付ける）
- cart の新しい e2e はスナップショットを持ち回る形で書き、`dual_only` を付けない（`services/cart/tests/e2e/test_payment_master_settings.py` に倣う）
- 判断の根拠は research.md の R-番号を参照する

---

## Phase 1: Setup（共通の基盤）

**Purpose**: 取引の支払行の項目追加（commons）。cart・report・journal がこの版に依存する

- [X] T001 `services/commons/src/kugel_common/models/documents/base_tranlog.py` の `BaseTransaction.Payment` に `variant_code: Optional[str] = None` と `builtin_description: Optional[str] = None` を追加する。各項目に英語のコメント（`variant_code`: the payment variant the line was recorded with; `builtin_description`: the payment method's name at the time of the sale, since `description` holds the variant's name）を付ける（data-model.md「kugel_common」・research R-9）
- [X] T002 `services/commons/tests/unit/test_base_tranlog_payment_variant.py` を新設し、(a) 2 項目を持たない取引ログの辞書から `BaseTransaction` を作ると両方 `None` になる、(b) 2 項目を持つ辞書は値を保つ、(c) `model_dump()` に 2 項目が出る、を確かめる
- [X] T003 `./scripts/update_common_and_rebuild.sh --increment-version` で commons の版を上げて各サービスへ配り、各サービスの `Pipfile`・`Pipfile.lock` の `kugel_common` の wheel の版が上がったことを確かめる（cart・report・journal・master-data ほか、スクリプトが更新する全サービス）

**Checkpoint**: 全サービスが新しい commons で `pipenv run pytest -m unit` を通る

---

## Phase 2: Foundational

本フィーチャーには、全ストーリーを止める共通の前提は Phase 1 以外に無い。US1（master-data）と US2 以降（cart・report）は次の依存だけを持つ:

- US2・US3 の **e2e** は US1 の API（サブコードの登録）を使う
- US2・US3・US4 の **unit・integration** は US1 に依存しない（支払マスタの文書を直接組み立てる）

---

## Phase 3: User Story 1 - 支払方法の下にサブコードを登録・管理する (Priority: P1) 🎯 MVP

**Goal**: master-data で支払方法ごとにサブコードを登録・一覧・取得・変更でき、支払マスタの取得の応答にサブコードが入る（spec FR-001〜FR-010）

**Independent Test**: 支払方法を 1 つ作り、サブコードの登録・重複の拒否・別の支払方法への同じコードの登録・一覧・取得・名前の変更・停止・再開・支払方法の更新でサブコードが残る・支払方法の削除で消える、を API で確かめる（spec US1 のシナリオ 1〜8）

### Tests for User Story 1

- [X] T004 [P] [US1] `services/master-data/tests/unit/test_payment_variant_schemas.py` を新設し、要求スキーマの検証を確かめる: `variant_code` が `^[A-Za-z0-9_-]{1,20}$` に合わない（空・21 文字・`/`・空白・日本語）と検証エラー、`name` が空・空白だけだと検証エラー、`is_active` の既定が `True`、変更の要求スキーマは `variant_code` を含むと検証エラー（`extra="forbid"`）（contracts/master-data-payment-variants.md）
- [X] T005 [P] [US1] `services/master-data/tests/unit/test_payment_variant_service.py` を新設し、`PaymentMasterService` のサブコードの操作をリポジトリのモックで確かめる: 登録で支払方法が無ければ `DocumentNotFoundException`、重複なら `DocumentAlreadyExistsException`、一覧・取得で支払方法が無い・サブコードが無ければ `DocumentNotFoundException`、変更で同様、一覧は `variant_code` の昇順
- [X] T006 [P] [US1] `services/master-data/tests/integration/test_payment_variants_repository.py` を新設し、実 MongoDB で `PaymentMasterRepository` を確かめる: (a) 条件付き `$push` で登録できる、(b) 同じコードの 2 回目は 0 件一致で拒否される、(c) `asyncio.gather` で同じコードを同時に 2 件登録しても 1 件しか入らない、(d) 位置指定の `$set` で `name`・`is_active` と `variants.$.updated_at`・文書の `updated_at` が更新される、(e) `update_payment_async`（既存の支払マスタの更新）の後もサブコードが残る、(f) `delete_payment_async` で文書ごと消える、(g) 別の支払方法に同じコードを登録できる（research R-2）
- [X] T007 [P] [US1] `services/master-data/tests/unit/test_api_payment.py` に、サブコードの 4 端点の単体テストを追加する（既存のテストの依存の差し替え方に倣う）: `POST` が 201 と登録したサブコードを返す、`GET` 一覧・取得、`PUT` で名前と有効フラグが変わる、`DELETE` が 405、端末の資格での `POST`・`PUT` は既存の支払マスタの書き込みと同じく拒否、`GET /payments/{payment_code}` の応答に `variants` が入る
- [X] T008 [P] [US1] `services/master-data/tests/e2e/test_payment_variants.py` を新設し、spec US1 のシナリオ 1〜8 を起動中のサービスに対して確かめる（`tests/e2e/test_crud_smoke.py` の認証とテナントの準備に倣う）。サブコードは削除できず e2e のテナントは実行をまたいで残るので、コードには実行ごとの一意な接尾辞を付け、後片付けで登録したサブコードをすべて停止する。重複の登録は HTTP 400（`DocumentAlreadyExistsException`）を期待する

### Implementation for User Story 1

- [X] T009 [US1] `services/master-data/app/models/documents/payment_master_document.py` に `PaymentVariant(BaseDocumentModel)`（`variant_code: Optional[str]`・`name: Optional[str]`・`is_active: Optional[bool] = True`・`created_at: Optional[datetime]`・`updated_at: Optional[datetime]`）を新設し、`PaymentMasterDocument` に `variants: list[PaymentVariant] = Field(default_factory=list)` を追加する（data-model.md「master-data」）
- [X] T010 [US1] `services/master-data/app/models/repositories/payment_master_repository.py` に次を追加する（research R-2）:
  - `add_variant_async(payment_code, variant: PaymentVariant) -> bool`: `created_at` を `get_app_time()` で付け、フィルタ `{tenant_id, payment_code, "variants.variant_code": {"$ne": code}}` に `{"$push": {"variants": ...}, "$set": {"updated_at": now}}`。一致 1 件で `True`、0 件で `False`
  - `update_variant_async(payment_code, variant_code, name, is_active) -> bool`: フィルタ `{tenant_id, payment_code, "variants.variant_code": variant_code}` に `{"$set": {"variants.$.name", "variants.$.is_active", "variants.$.updated_at", "updated_at"}}`。一致 1 件で `True`
  - DB 操作は `self.dbcollection`（未初期化なら `await self.initialize()`）と `session=self.session` を使い、例外は既存のリポジトリと同じく `RepositoryException` で包む
- [X] T011 [US1] `services/master-data/app/services/payment_master_service.py` に `add_variant_async`・`get_variants_async`・`get_variant_async`・`update_variant_async` を追加する。登録はリポジトリが `False` を返したら支払方法を引き直し、無ければ `DocumentNotFoundException`、あれば `DocumentAlreadyExistsException`。一覧は `variant_code` の昇順で返す。変更も `False` なら支払方法の有無で `DocumentNotFoundException` のメッセージを分ける（spec FR-003〜FR-005・FR-018）
- [X] T012 [US1] `services/master-data/app/api/common/schemas.py` に `BasePaymentVariantCreateRequest`（`variant_code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")`・`name: str`（空・空白だけを拒否する validator）・`is_active: bool = True`）、`BasePaymentVariantUpdateRequest`（`name`・`is_active`。`model_config` に `extra="forbid"` を足す）、`BasePaymentVariantResponse`（`variant_code`・`name`・`is_active`・`entry_datetime`・`last_update_datetime: Optional[str]`）を追加し、`BasePaymentResponse` に `variants: list[BasePaymentVariantResponse] = Field(default_factory=list)` を追加する。`services/master-data/app/api/v1/schemas.py` に対応する v1 の型を既存の `PaymentResponse` 等と同じ形で追加する
- [X] T013 [US1] `services/master-data/app/api/common/schemas_transformer.py` と `services/master-data/app/api/v1/schemas_transformer.py` に、`PaymentVariant` → 応答の変換（`created_at`・`updated_at` を `"%Y-%m-%d %H:%M:%S"` で文字列化、既存の `transform_payment` と同じ書式）を追加し、`transform_payment` が `variants` を `variant_code` の昇順で詰めるようにする
- [X] T014 [US1] `services/master-data/app/api/v1/payment_master.py` にサブコードの 4 端点を追加する（contracts/master-data-payment-variants.md・research R-4）: `POST /tenants/{tenant_id}/payments/{payment_code}/variants`（201・`get_tenant_id_refusing_terminal`）、`GET .../variants`・`GET .../variants/{variant_code}`（`get_tenant_id_with_security_by_query_optional`）、`PUT .../variants/{variant_code}`（`get_tenant_id_refusing_terminal`）。パスのテナントとトークンのテナントの照合・`ApiResponse` での包み方・`responses` の宣言・docstring は既存の支払マスタの端点に倣う。`DELETE` は定義しない
- [X] T015 [US1] T004〜T008 が通ることを確かめる（`cd services/master-data && pipenv run pytest tests/unit tests/integration -k "variant or payment"`、e2e は全体の起動後に `pipenv run pytest tests/e2e -k variant`）

**Checkpoint**: master-data 単体でサブコードの管理ができる。**この時点ではサブコードを本番で登録しない**（cart が読まないため。research R-14）

---

## Phase 4: User Story 2 - 支払をサブコードで記録する (Priority: P1)

**Goal**: cart の支払の登録で任意の `variant_code` を受け、規則に従ってサブコードを決め、支払行に `variant_code`・サブコードの名前・`builtin_description` を記録する（spec FR-011〜FR-015・FR-017）

**Independent Test**: サブコードを 2 件持つ支払方法で、指定ありの記帳・指定なしの拒否・存在しない・別の支払方法の・停止中のサブコードの拒否・1 件だけのときの自動選択・サブコードの無い支払方法の現行どおりの記帳・2 件の支払の要求で 2 件目が拒否されたらカートが変わらないこと、を確かめる（spec US2 のシナリオ 1〜8）

### Tests for User Story 2

- [X] T016 [P] [US2] `services/cart/tests/unit/test_payment_variant_logic.py` を新設し、`resolve_sale_variant(pay_doc, requested_code)` を research R-6 の表の全行で確かめる: 有効 0 件・1 件・2 件以上 × 指定あり（有効・存在しない・停止中）/なし。戻り値の `variant_code`・`name`・`builtin_description` と、拒否の例外の型（403018・403019・403020）を確かめる。別の支払方法にだけあるコードは「存在しない」になること、停止中だけのとき指定なしはサブコードなしになることを含める
- [X] T017 [P] [US2] `services/cart/tests/unit/test_payment_strategies.py` に、`settle_payment_async(..., variant_code=..., variant_name=..., builtin_description=...)` が支払行に 3 項目を書くこと、指定が無ければ `description` は支払方法の名前・`variant_code` は `None`・`builtin_description` は支払方法の名前になること、現金・キャッシュレス・その他の 3 プラグインが `pay(..., variant_code=...)` で受けた値を `settle_payment_async` へ渡すこと、を追加する
- [X] T018 [P] [US2] `services/cart/tests/unit/test_cart_service.py` に次を追加する: (a) `add_payment_to_cart_async` が全要素のサブコードをプラグインを呼ぶ前に決めること（2 件目が 403018 ならプラグインの `pay` は 1 回も呼ばれず、カートは保存されない）、(b) プラグインが `variant_code` を捨てて支払行にサブコードが無いと `ServiceException` になること（`variant_code` を無視する偽のプラグインで）、(c) サブコードの無い支払方法では従来どおり記帳されること
- [X] T019 [P] [US2] `services/cart/tests/unit/test_cart_exceptions.py` に 403018・403019・403020 の例外がコードと HTTP 400 を持つことを追加する（既存の 403017 のテストに倣う）
- [X] T020 [P] [US2] `services/cart/tests/unit/test_api_cart.py` に、支払の要求で `variantCode` を受けること、応答の支払行に `variantCode`・`builtinPaymentName` が出ることを追加する
- [X] T021 [US2] `services/cart/tests/e2e/test_payment_variants.py` を新設し、spec US2 のシナリオ 1〜8、「2 件の支払の要求で 2 件目が 403018 のときカートが変わらない」、spec FR-017（記帳 → サブコードを停止・改名 → キャッシュの無効化 → 確定できる・支払行は記帳時のコードと名前のまま）を確かめる。スナップショットを持ち回り、`dual_only` を付けない。e2e のテナントは他の cart e2e と共有で、サブコードは削除できないので、次を守る:
  - サブコードのコードに実行ごとの一意な接尾辞を付ける（前回の実行の残りと重複させない）
  - master-data でサブコードを登録・変更するたびに、cart の `DELETE /api/v1/cache/master-data?namespace=payment_master`（特権の利用者かサービスアカウントの資格）を呼んでから cart を操作する（支払マスタのキャッシュの TTL は 600 秒）
  - 後片付け（fixture の teardown、テストの失敗時も）で、登録したサブコードをすべて停止し、もう一度キャッシュを無効化する。`11` に有効なサブコードを 2 件残すと、後に走る既存の cart e2e がサブコードなしの `11` で 403020 になる

### Implementation for User Story 2

- [X] T022 [P] [US2] `services/cart/app/models/documents/payment_master_document.py` に `PaymentVariant`（`variant_code`・`name`・`is_active`。既存と同じく camelCase の別名を持つ `model_config`）を新設し、`PaymentMasterDocument` に `variants: list[PaymentVariant] = Field(default_factory=list)` を追加する（research R-10。キャッシュの鍵の指紋は型から自動で変わる）
- [X] T023 [P] [US2] `services/cart/app/exceptions/cart_error_codes.py` に `PAYMENT_VARIANT_NOT_FOUND = "403018"`・`PAYMENT_VARIANT_INACTIVE = "403019"`・`PAYMENT_VARIANT_REQUIRED = "403020"` と、`CartErrorMessage` の日英のメッセージを追加し、`services/cart/app/exceptions/cart_exceptions.py` に `PaymentVariantNotFoundException`・`PaymentVariantInactiveException`・`PaymentVariantRequiredException`（`ServiceException` を継承、`status_code=status.HTTP_400_BAD_REQUEST`、`PaymentLimitExceededException` に倣う）を追加して `services/cart/app/exceptions/__init__.py` から公開する（research R-12）
- [X] T024 [US2] `services/cart/app/services/logics/payment_variant_logic.py` を新設し、`VariantDecision`（frozen dataclass: `variant_code: Optional[str]`・`name: Optional[str]`・`builtin_description: Optional[str]`）と純関数 `resolve_sale_variant(pay_doc: PaymentMasterDocument, requested_code: Optional[str]) -> VariantDecision` を実装する。規則は research R-6 の表。`name` はサブコードで決めたときサブコードの名前、それ以外は `None`。`builtin_description` は常に `pay_doc.description`。モジュールの docstring に規則を英語で書く
- [X] T025 [US2] `services/cart/app/api/common/schemas.py` の `BasePaymentRequest` に `variant_code: Optional[str] = None`、`BaseTranPayment` に `variant_code: Optional[str] = None`・`builtin_payment_name: Optional[str] = None` を追加し、`services/cart/app/api/common/schemas_transformer.py` の `transform_payments` で支払行の `variant_code`・`builtin_description` を詰める（contracts/cart-payments.md「支払行の応答」）。v1 側（`services/cart/app/api/v1/schemas.py` の `PaymentRequest`・`TranPayment`、`schemas_transformer.py` の `transform_payments`）は基底を継承・委譲しているだけなので変更不要
- [X] T026 [US2] `services/cart/app/services/strategies/payments/abstract_payment.py` の `settle_payment_async` と `_build_cart_payment` に、キーワード引数 `variant_code: Optional[str] = None`・`variant_name: Optional[str] = None`・`builtin_description: Optional[str] = None` を追加し、支払行の `variant_code`、`description`（`variant_name` があればそれ、無ければ `pay_doc.description`）、`builtin_description`（引数が無ければ `pay_doc.description`）を書く。`pay()` の docstring に、呼び出し側が `variant_code`・`variant_name`・`builtin_description` を渡すことと、実装はそれを `settle_payment_async` へ渡すか、扱えなければ支払を拒否することを追記する（#308 の契約）
- [X] T027 [US2] `services/cart/app/services/strategies/payments/cash.py`・`cashless.py`・`others.py` の `pay()` が `kwargs` の `variant_code`・`variant_name`・`builtin_description` を `settle_payment_async` へ渡すようにする（docstring の「this strategy uses none」を直す）
- [X] T028 [US2] `services/cart/app/services/cart_service.py` の `add_payment_to_cart_async` を直す（research R-6）: (1) ループの前に、全要素について `self.payment_master_repo.get_payment_by_code_async(payment_code)` で支払マスタを読み `resolve_sale_variant` で決め終える（拒否はここで投げ、プラグインを 1 回も呼ばない）、(2) 各要素のプラグインの `pay()` に `variant_code`・`variant_name`・`builtin_description` をキーワード引数で渡す、(3) `pay()` の後、今回追加された支払行（呼び出し前の `len(cart_doc.payments)` 以降）がすべて決めた `variant_code` を持つことを確かめ、違えば `ServiceException`、(4) 新しい 3 つの例外を既存の業務の例外と同じく `except` でそのまま投げ直す。支払マスタのリポジトリの参照の仕方は既存のコード（プラグインへ `set_payment_master_repository` で渡しているもの）に合わせる
- [X] T029 [US2] T016〜T021 が通ることを確かめる（`cd services/cart && pipenv run pytest tests/unit -k "variant or payment"`、e2e は全体の起動後）

**Checkpoint**: commons・master-data・cart を配備すれば、サブコードで記帳できる（report の内訳は US4）

---

## Phase 5: User Story 3 - 取消・返品を売上時の支払種別で行う (Priority: P2)

**Goal**: 取消は売上時の「支払方法＋サブコード」と金額で照合し、返品は売上時の支払種別（売上時の金額まで）か現金 `01` に限る（spec FR-016〜FR-016e）

**Independent Test**: サブコードで支払った取引を確定し、spec US3 のシナリオ 1〜10 を確かめる

### Tests for User Story 3

- [X] T030 [P] [US3] `services/cart/tests/unit/test_payment_variant_logic.py` に `match_void_payments` のテストを追加する: 鍵が売上時に無い（サブコードの省略で売上時の行にサブコードがある場合を含む）・鍵ごとの金額の不一致は `BadRequestBodyException`、一致すれば各要求の `ReturnLineDecision` が売上時のその鍵の最初の行の `description`・`builtin_description` を持つ、サブコードの無い取引は従来の要求で通る、本フィーチャーの前の行（`builtin_description` が `None`）を扱える
- [X] T031 [P] [US3] 同じファイルに `match_return_payments` のテストを追加する: 売上時の鍵（停止中のサブコードを含む）は受け付けて名前は売上時の行から、売上時に無い `01` は `from_original=False`、それ以外（`11/JCB`・`12`）は 403021、現金以外の鍵ごとの返金額の合計が売上時の合計を超えると 403022（同じ鍵を 2 行に分けた場合を含む）、現金は上限なし、売上時の行に `01` がある場合は売上時の鍵として扱う
- [X] T032 [P] [US3] `services/cart/tests/unit/test_tran_service.py` に、`void_async` が要求の `variant_code` と売上時の名前で支払行を作ること、`return_async` が売上時の鍵の行に売上時の名前を、売上時に無い現金の行に `resolve_sale_variant` の結果と現在のマスタの名前を書くこと、403021・403022 が投げられること、`can_refund=false`（403014）の確認が従来どおり効くこと、を追加する
- [X] T033 [P] [US3] `services/cart/tests/unit/test_cart_exceptions.py` に 403021・403022 を追加する
- [X] T034 [US3] `services/cart/tests/e2e/test_payment_variants.py` に spec US3 のシナリオ 1〜10 を追加する（取消・返品の端点。スナップショット・確定の文脈の持ち回りは `services/cart/tests/e2e/test_void_return.py` に倣う）。T021 の規則（一意なコード・変更ごとのキャッシュの無効化・後片付けでの停止）に従う。シナリオ 9 は、販売の後にサブコードを停止・改名し、**キャッシュを無効化してから**取消・返品する（無効化しないと cart が停止を知らず、検証にならない）
- [X] T035 [US3] 既存の返品の e2e・unit（`services/cart/tests/e2e/test_void_return.py`・`test_void_return_scope.py`・`services/cart/tests/unit/test_tran_service*.py`）で、売上時と違う支払方法（現金以外）で返品しているテストを探し、仕様の変更（403021）に合わせて直す。直した箇所と理由を PR の説明に書く

### Implementation for User Story 3

- [X] T036 [P] [US3] `services/cart/app/exceptions/cart_error_codes.py`・`cart_exceptions.py`・`__init__.py` に `RETURN_TENDER_NOT_ALLOWED = "403021"`・`RETURN_AMOUNT_EXCEEDS_ORIGINAL = "403022"` と `ReturnTenderNotAllowedException`・`ReturnAmountExceedsOriginalException`（HTTP 400）を追加する
- [X] T037 [US3] `services/cart/app/services/logics/payment_variant_logic.py` に `ReturnLineDecision`（`payment_code`・`variant_code`・`name: Optional[str]`・`builtin_description: Optional[str]`・`from_original: bool`）と、純関数 `match_void_payments(original_lines, requested) -> list[ReturnLineDecision]`（research R-7。不一致は `BadRequestBodyException`）・`match_return_payments(original_lines, requested, cash_code: str = "01") -> list[ReturnLineDecision]`（research R-8。403021・403022）を実装する。鍵は `(payment_code, variant_code)`、要求の `variant_code` の省略は `None`
- [X] T038 [US3] `services/cart/app/services/tran_service.py` の `void_async` を直す: 既存の支払コードごとの照合（`payment_code not in ...`・支払コードごとの合計）を `match_void_payments` に置き換え、支払行の作成で `variant_code` に要求の値、`description`・`builtin_description` に決定の値（`None` なら支払マスタの `description`）を書く。`deposit_amount` の規則・支払マスタの読み取り・合計の確認は現行どおり
- [X] T039 [US3] `services/cart/app/services/tran_service.py` の `return_async` を直す: 支払行を作る前に `match_return_payments` を呼び、`from_original=False`（売上時に無い現金）の行は支払マスタを読んで `resolve_sale_variant` で決める。支払行に `variant_code`・`description`（決定の名前、無ければサブコードの名前、それも無ければ支払マスタの `description`）・`builtin_description` を書く。`_check_refund_allowed`・合計の確認は現行どおり
- [X] T040 [US3] T030〜T035 が通ることを確かめる

**Checkpoint**: 取消・返品の規則が spec どおり。返品の制限は既存の動作を変えるので、リリースノートの下書き（T052）に入れる

---

## Phase 6: User Story 4 - サブコード別に売上を集計する (Priority: P2)

**Goal**: 売上レポート・支払レポートの支払を支払方法単位で集計し、サブコード別の内訳を加える（spec FR-019〜FR-022）

**Independent Test**: 同じ支払方法の異なるサブコードで支払った取引（取消を含む）を投入し、spec US4 のシナリオ 1〜5 と contracts/tranlog-and-reports.md の件数の例を確かめる

### Tests for User Story 4

- [X] T041 [P] [US4] `services/report/tests/unit/test_sales_report_maker.py` に、後段の合算（`_summarize_sales_report` 相当の Python の処理と支払の行を作る処理）のテストを追加する: 取引種別の符号が内訳にも掛かる、内訳は `variant_code` の昇順で `None` が末尾、行の名前は `builtin_name`、本フィーチャーの前の行（`variant_code`・`builtin_description` が無い）は「サブコードなし」の内訳と支払行の名前の行になる、内訳の金額・件数の合計が行と一致する
- [X] T042 [P] [US4] `services/report/tests/unit/` に `test_payment_report_maker_variants.py` を新設し、`_summarize_payment_report` の内訳の合算（符号・取引数・並び・名前をマスタから、無ければ支払行の名前）と、`_fetch_payment_master` が 100 件を超える支払方法を全ページ読むこと（HTTP クライアントのモックで 2 ページを返す）を確かめる
- [X] T043 [P] [US4] `services/report/tests/integration/test_payment_variant_aggregation.py` を新設し、実 MongoDB に取引ログを入れて売上レポートと支払レポートを作り、contracts/tranlog-and-reports.md の件数の例（T1・T2・T3）の期待値、期間中に改名したサブコードの名前が最も新しい販売時点のものになること、`11` の行が 1 行であることを確かめる（既存の `tests/integration/test_split_payment_bug.py` の取引ログの作り方に倣う）

### Implementation for User Story 4

- [X] T044 [P] [US4] `services/report/app/models/documents/sales_report_document.py` に `PaymentVariantReport`（`variant_code: Optional[str]`・`variant_name: str`・`amount: float`・`count: int`）を新設し、`PaymentReportTemplate` に `payment_code: Optional[str] = None`・`variants: list[PaymentVariantReport] = Field(default_factory=list)` を追加する。`services/report/app/models/documents/payment_report_document.py` の `PaymentSummaryItem` に `variants: list[PaymentVariantReport] = Field(default_factory=list)` を追加する（同じ型を import して共用）
- [X] T045 [P] [US4] `services/report/app/api/common/schemas.py`（と v1 の `schemas.py`）の売上レポートの支払の型に `payment_code: Optional[str] = None`・`variants`（camelCase で `variantCode`・`variantName`・`amount`・`count`）を追加し、`services/report/app/api/common/schemas_transformer.py`（と v1）で詰める
- [X] T046 [US4] `services/report/app/services/plugins/sales_report_maker.py` を直す（research R-11）: (1) 取引の支払の写し（`$map` の `in`）に `variant_code`・`builtin_description` を足す、(2) 支払の分組の前に `generate_date_time` の降順の `$sort` を入れ、分組の鍵を `(… , payment_code, variant_code)` にし、`variant_name: {$first: description}`・`builtin_name: {$first: {$ifNull: [builtin_description, description]}}` を取る、(3) 最後の分組の `$push` に `variant_code`・`variant_name`・`builtin_name` を足す、(4) Python の後段の支払の合算を `payment_code` ごとの行と `variant_code` ごとの内訳に分け、行の `description` を `builtin_name` にする、(5) 支払の行を作る処理で `payment_code`・`variants`（並べ替え済み）を出す。並べ替えの関数は 1 か所に置く。`/db-review` の観点（Cartesian product を作らない）で分組の前後の `$unwind` を確かめる
- [X] T047 [US4] `services/report/app/services/plugins/payment_report_maker.py` を直す（research R-11）: (1) `_fetch_payment_master` を全ページ読むようにし（応答の `metadata`（master-data の `PaginationMetadata` を `model_dump()` したもの）の `has_next` が偽になるまで、または `total_pages` まで `page` を進める）、戻り値を「支払コード → 名前」と「(支払コード, サブコード) → サブコードの名前」の 2 つにする、(2) 内訳のパイプライン（`(payment_code, variant_code, transaction_type)` で分組し、件数は取引の一意な集合の大きさ、名前は `generate_date_time` の降順の `$first description`）を追加する、(3) `_summarize_payment_report` で各行に `variants` を付ける（符号付き、`variant_code` の昇順・`None` は末尾、名前はマスタ→支払行の名前）。`ratio` は行にだけ付ける
- [X] T048 [US4] T041〜T043 が通ることを確かめる（`cd services/report && pipenv run pytest tests/unit tests/integration -k "variant or payment or sales_report"`）。既存の report の integration（`test_split_payment_bug.py`・`test_payment_sum_invariant.py` ほか）が通ることも確かめる

**Checkpoint**: 全ストーリーが動く

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T049 [P] `docs/en/master-data/api-specification.md`・`docs/ja/master-data/api-specification.md` にサブコードの 4 端点と支払マスタの応答の `variants` を、`docs/en/master-data/model-specification.md`・`docs/ja/master-data/model-specification.md` に `PaymentVariant`、配備の順序（research R-14）、サブコードの変更をすぐに cart へ効かせる方法（cart の `DELETE /api/v1/cache/master-data?namespace=payment_master`）を追記する
- [ ] T050 [P] `docs/en/cart/api-specification.md`・`docs/ja/cart/api-specification.md` に支払の要求の `variantCode`、サブコードの決定の規則、取消・返品の規則、支払行の応答の 2 項目を、`docs/en/cart/model-specification.md`・`docs/ja/cart/model-specification.md` に支払行の 2 項目を追記する
- [ ] T051 [P] `docs/en/report/api-specification.md`・`docs/ja/report/api-specification.md`・`model-specification.md`（en・ja）に、売上レポート・支払レポートの `variants` と件数の数え方の違いを追記する。`docs/en/general/error_code_spec.md`・`docs/ja/general/error_code_spec.md` に 403018〜403022 を追記する
- [ ] T052 リリースノートの下書きを PR の説明に書く: (1) 返品の返金手段が売上時の支払種別と現金に限られる（既存の動作の変更・403021）、(2) 返品の売上時の金額の上限（403022）、(3) サブコードの登録は commons・cart・report の配備後に行うこと（research R-14）、(4) 支払レポートが支払マスタを全ページ読むようになったこと
- [ ] T053 `./scripts/run_unit_tests.sh`・`./scripts/run_integration_tests.sh`・`./scripts/run_e2e_tests.sh` を通す（cart の e2e は既定の `CART_REQUEST_SNAPSHOT_MODE=DUAL`）。通らないものは結果を記録して原因を直す。あわせて、e2e で記帳した取引が journal に保存された取引ログで `variant_code`・`builtin_description` を保っていることを確かめる（spec「影響するサービス」の journal の確認）
- [ ] T054 quickstart.md の手順を起動中の環境で一通り実行し、記述と動作が合わなければ quickstart.md を直す
- [ ] T055 Issue #311 の本文を、取消・返品の規則（売上時の支払種別・現金・上限）と配備の順序に合わせて更新する（利用者の確認を取ってから）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（commons）**: 最初に行う。T003 の配布の後でないと cart・report のテストが新しい項目を使えない
- **US1（Phase 3）**: Phase 1 に依存しない（master-data は支払行の項目を使わない）が、commons の版の配布は全サービスに及ぶので T003 の後に始めるのが安全
- **US2（Phase 4）**: Phase 1 の後。unit・integration は US1 に依存しない。e2e（T021）は US1 の API に依存
- **US3（Phase 5）**: US2 の `payment_variant_logic.py`（T024）・例外（T023）・支払行の書き込み（T026）に依存
- **US4（Phase 6）**: Phase 1 の後。cart（US2）に依存しない（取引ログを直接作ってテストする）
- **Polish（Phase 7）**: 全ストーリーの後

### Within Each User Story

- テストを先に書き、失敗することを確かめてから実装する
- 文書・型 → リポジトリ → サービス → API の順

### Parallel Opportunities

- T004〜T008（US1 のテスト）は互いに並行できる
- US1（master-data）と US4（report）は Phase 1 の後に並行できる
- T016〜T020（US2 の unit）は並行できる。T022・T023 は並行できる
- T030〜T033（US3 のテスト）は並行できる
- T041〜T043（US4 のテスト）、T044・T045 は並行できる
- T049〜T051（docs）は並行できる

---

## Parallel Example: User Story 2

```bash
# US2 の unit テストを並行して書く
Task: "T016 resolve_sale_variant のテスト in services/cart/tests/unit/test_payment_variant_logic.py"
Task: "T017 settle_payment_async の variant 引数のテスト in services/cart/tests/unit/test_payment_strategies.py"
Task: "T019 403018–403020 の例外のテスト in services/cart/tests/unit/test_cart_exceptions.py"

# 型と例外を並行して足す
Task: "T022 cart の PaymentMasterDocument.variants in services/cart/app/models/documents/payment_master_document.py"
Task: "T023 403018–403020 in services/cart/app/exceptions/"
```

---

## Implementation Strategy

### MVP（US1 + US2）

1. Phase 1（commons）
2. US1（master-data のサブコードの管理）
3. US2（cart のサブコードでの記帳）
4. **止めて確かめる**: サブコードを登録し、記帳した取引ログに `variant_code` が入ることを確かめる。この時点で配備するなら、返品・取消（US3）は現行の規則のまま、report の内訳（US4）は無い

### Incremental Delivery

1. Phase 1 + US1 + US2 → MVP（サブコードの記録）
2. US3 → 取消・返品の規則（返品の制限は既存の動作の変更なのでリリースノートと一緒に）
3. US4 → 集計の内訳
4. Phase 7 → docs・全テスト・quickstart

1 つの PR にまとめる場合も、コミットはこの単位で分ける。

---

## Notes

- [P] は別のファイルで、未完了のタスクに依存しないもの
- 各タスクまたは論理的なまとまりごとにコミットする
- Checkpoint でストーリー単体の動作を確かめる
- サブコードの登録は commons・cart・report の配備後（research R-14）
