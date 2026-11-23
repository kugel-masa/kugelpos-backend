---
description: "Task list for 323-staff-pin-verification"
---

# Tasks: 端末サインインでの従業員 PIN の照合

**Input**: `/specs/323-staff-pin-verification/` の spec.md・plan.md・research.md・data-model.md・contracts/・quickstart.md
**Issue**: [#323](https://github.com/kugel-masa/kugelpos-backend/issues/323)

**Tests**: plan.md の「テスト方針」に従い、各ストーリーにテストを含める（unit → integration → e2e）。テストは実装の前に書き、失敗することを確かめてから実装する。

**Organization**: 照合の部品（master-data の照合・commons の呼び出し口）を Phase 2 に置き、端末のサインインをストーリーごとに分ける。US1・US2 が P1、US3・US4 が P2。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並行して進められる（別のファイル・未完了のタスクに依存しない）
- **[Story]**: 対応するユーザーストーリー（US1〜US4）
- パスはリポジトリのルートからの相対パス

## 共通の規約（全タスク）

- コード・コメント・ログは英語。型ヒント必須。DB 操作は async
- 変更したサービスでは `pipenv run ruff check app/` と `pipenv run ruff format app/` を通す（既存の指摘は増やさない）
- 新しいテストは正しい層のディレクトリ（`tests/unit/`・`tests/integration/`・`tests/e2e/`）に置く（conftest が自動で印を付ける）
- PIN の漏れを確かめるテストは、他の値に紛れない一意で長い値（例 `pin-sentinel-7c1e9a`）を使う
- 判断の根拠は research.md の R-番号を参照する

---

## Phase 1: Setup

**Purpose**: master-data のエラーコードと例外（Phase 2 の照合が使う）

- [X] T001 `services/master-data/app/exceptions/master_data_error_codes.py` に `STAFF_VERIFY_STAFF_NOT_FOUND = "405701"`・`STAFF_VERIFY_PIN_REQUIRED = "405702"`・`STAFF_VERIFY_PIN_MISMATCH = "405703"` と日本語・英語のメッセージ（contracts/master-data-staff-verify.md の表）を追加する
- [X] T002 `services/master-data/app/exceptions/master_data_exceptions.py` に `StaffVerifyStaffNotFoundException`（404）・`StaffVerifyPinRequiredException`（401）・`StaffVerifyPinMismatchException`（401）を追加し、`app/exceptions/__init__.py` で公開する。`ServiceException` を継承し、`log_level=logging.WARNING`、メッセージは従業員コードと理由だけ（PIN を入れない）（data-model.md §4）

---

## Phase 2: Foundational（照合の部品）

**Purpose**: master-data の照合と、commons の呼び出し口。US1〜US4 のすべてがこれに依存する

**⚠️ CRITICAL**: このフェーズが終わるまで、端末のサインインの変更（Phase 3 以降）に着手しない

### master-data: 照合

- [X] T003 [P] `services/master-data/tests/unit/test_staff_verify_service.py` を新設し、`StaffMasterService.verify_staff_async` をリポジトリのモックで確かめる（data-model.md §2）
  - 判定表の全行: 従業員なし → 405701、PIN が `None`・`""` の従業員 → PIN の有無・値に関わらず成功、PIN ありで PIN が `None`・`""` → 405702、不一致 → 405703、一致 → 成功
  - 空白だけの登録 PIN（`" "`）は PIN ありとして扱い、`" "` だけが一致する
  - ASCII 以外の PIN（`"１２３４"`・`"pïn"`）で比較が `TypeError` にならない
  - 例外のメッセージにも、caplog のどの記録にも sentinel の PIN が現れない
- [X] T004 [P] `services/master-data/tests/unit/test_api_staff_verify.py` を新設し、`POST /api/v1/internal/tenants/{tenant_id}/staff/{staff_id}/verify` を確かめる（contracts/master-data-staff-verify.md）
  - サービスアカウントのトークン（`create_service_token`）で 200、応答の `data` のキーが `{"id", "name"}` だけ（`pin`・`roles` が無い）
  - 端末の JWT・利用者の JWT で 403、`Authorization` なし（API キーだけ）で 401、テナント不一致で 400
  - 失敗 3 種類の `userError.code` と HTTP（404 / 401 / 401）、`details` が無い
  - PIN を省略・`null`・`""` にした本文は 422 にならず、判定表どおりに扱う（PIN なしの従業員は 200、PIN ありの従業員は 405702）
  - 文字列でない PIN（数値など）だけが 422 になる。その応答に PIN の値が出ないこと
  - 応答の本文と caplog に sentinel の PIN が現れない
- [X] T005 `services/master-data/app/api/v1/schemas.py` に `StaffVerifyRequest`（`pin: Optional[str] = None`）・`StaffVerifyResponse`（`id: str`・`name: Optional[str]`、`pin` を持たない）を追加し、`app/api/v1/schemas_transformer.py` に `transform_staff_verification(staff_doc) -> StaffVerifyResponse` を追加する（id・name だけを射影する）（data-model.md §3・R-12）
- [X] T006 `services/master-data/app/services/staff_master_service.py` に `verify_staff_async(staff_id, pin)` を追加する。判定は data-model.md §2 のとおり、比較は `secrets.compare_digest(stored.encode("utf-8"), given.encode("utf-8"))`。比較はこのメソッドの中だけで行い、docstring に「ハッシュ化・回数制限を足す場所」と書く（R-6・spec FR-009）
- [X] T007 `services/master-data/app/api/v1/internal.py` を新設し（`APIRouter(prefix="/internal")`）、`POST /tenants/{tenant_id}/staff/{staff_id}/verify` を置く。依存は `get_service_account_info`、`verify_tenant_id` でテナントを検査し、受け付けのログにテナント・従業員コード・claim の `service` を出す（PIN は出さない）。`app/main.py` で `/api/v1` の下に登録する（R-1・R-2）
- [X] T008 T003・T004 が通ることを確かめる

### master-data: 登録・更新の PIN を任意に

- [X] T009 [P] `services/master-data/tests/unit/test_api_staff.py` に、PIN を省略した登録・更新が通り、保存された PIN が「PIN なし」（`None` または `""`）になること、PIN を指定した登録・更新はこれまでどおり通ることを追加する
- [X] T010 `services/master-data/app/api/common/schemas.py` の `BaseStaffCreateRequest`・`BaseStaffUpdateRequest` の `pin` を `Optional[str] = None` にし、サービスの登録・更新が `None` を受け付けることを確かめる（R-10・spec FR-020a）
- [X] T011 `services/master-data/tests/integration/test_staff_verify.py` を新設し、実 MongoDB で判定表（PIN あり：一致・不一致・なし、PIN なし：任意、従業員なし、PIN を省略して登録した従業員）を確かめる

### commons: 呼び出し口

- [X] T012 [P] `services/commons/tests/unit/test_staff_verify_web_repository.py` を新設し、`StaffMasterWebRepository.verify_staff_async` を HTTP クライアントのモックで確かめる（R-5・R-11）
  - 呼び出しが `POST /api/v1/internal/tenants/{tenant}/staff/{staff}/verify`、`Authorization` がサービスアカウントのトークン、PIN は本文だけ（クエリに無い）
  - 実際の camelCase の応答本文（`userError.code` が 405701 / 405702 / 405703）で `StaffAuthenticationException` の `reason` がそれぞれ `staff_not_found` / `pin_required` / `pin_mismatch`。`userError` が無く `user_error` だけの本文も同じ
  - 5xx、接続失敗（`status_code=None`）、業務コードの無い 404、想定外の本文は `RepositoryException`
  - `/`・`..`・`?` を含む従業員コードで、呼び出し先のパスが変わらない（符号化される）
  - 成功で `StaffMasterDocument(id, name, tenant_id)` が返り、`pin` が `None`
  - 例外の文字列と caplog に sentinel の PIN が現れない
- [X] T013 `services/commons/src/kugel_common/enums.py` に `StaffAuthenticationFailure`（`staff_not_found` / `pin_required` / `pin_mismatch`）、`services/commons/src/kugel_common/exceptions/` に `StaffAuthenticationException`（`reason` を持つ）を追加して公開する（data-model.md §4）
- [X] T014 `services/commons/src/kugel_common/models/repositories/staff_master_web_repository.py` に `verify_staff_async(staff_id, pin)` を追加する。`create_service_token(self.tenant_id, "terminal")` で呼び、テナントと従業員コードを `urllib.parse.quote(..., safe="")` で符号化する。`HttpClientError` の応答本文の `userError`（無ければ `user_error`）の `code` だけで写像し、それ以外は `RepositoryException`（R-5・R-11）
- [X] T015 T012 が通ることを確かめ、`./scripts/update_common_and_rebuild.sh --increment-version` で commons の版を上げる。7 サービスの `Pipfile`・`Pipfile.lock` は `kugel_common` の項目と `_meta` のハッシュだけが変わったことを確かめる（他の依存が再ロックされていたら戻す）

**Checkpoint**: master-data の照合が単体・統合で通り、commons の新しい版が全サービスに入っている

---

## Phase 3: User Story 1 - PIN を登録した従業員は PIN が一致しないとサインインできない (Priority: P1) 🎯 MVP

**Goal**: 端末のサインインが照合で従業員を得て、PIN を登録した従業員は正しい PIN でだけサインインできる（spec FR-013・FR-014・FR-018・FR-019）

**Independent Test**: PIN を登録した従業員で、正しい PIN・誤った PIN・PIN なし・空の PIN でサインインし、正しい PIN だけが通ることを確かめる（spec US1 のシナリオ 1〜4）

### Tests for User Story 1

- [X] T016 [P] [US1] `services/terminal/tests/unit/test_terminal_sign_in_pin.py` を新設し、照合をモックして `TerminalService.sign_in_terminal_async(staff_id, pin)` を確かめる
  - 成功: 端末の `staff` に照合の応答の `id`・`name` が記録され、`pin` が `None`
  - `StaffAuthenticationException`（`pin_required`・`pin_mismatch`）で `SignInOutException`（406004 / 401）、端末は `replace` されない（状態が変わらない）
  - すでにサインインしていれば照合を呼ばずに `TerminalAlreadySignedInException`
  - `get_staff_by_id_async` を呼ばない（PIN を確かめない経路でサインインさせない）
- [X] T017 [P] [US1] `services/terminal/tests/unit/test_api_terminal_sign_in.py`（無ければ新設）で、`POST /api/v1/terminals/{terminal_id}/sign-in` が本文の `pin` をサービスへ渡すこと、`pin` を省略した本文（`{"staffId": "S001"}`）も受け付けることを確かめる

### Implementation for User Story 1

- [X] T018 [US1] `services/terminal/app/api/common/schemas.py` の `BaseTerminalSignInRequest` に `pin: Optional[str] = None` を追加する（spec FR-013）
- [X] T019 [US1] `services/terminal/app/services/terminal_service.py` の `sign_in_terminal_async(staff_id, pin=None)` を、`staff_master_repo.verify_staff_async(staff_id, pin)` で従業員を得る形に変える。commons が返す、PIN を持たない `StaffMasterDocument`（tenant_id・id・name）をそのまま記録する。`StaffAuthenticationException` は `SignInOutException` に写す（R-4・R-12）
- [X] T020 [US1] `services/terminal/app/api/v1/terminal.py` のサインインのルートで `terminal_signin.pin` をサービスへ渡す
- [X] T021 [US1] T016・T017 が通ることを確かめる

**Checkpoint**: PIN を登録した従業員の照合が端末のサインインで効く

---

## Phase 4: User Story 2 - PIN を登録していない従業員はこれまでどおりサインインできる (Priority: P1)

**Goal**: PIN が空の従業員は従業員コードだけで（PIN を送っても）サインインでき、既存のクライアントとテストが変更なしで動く（spec SC-002）

**Independent Test**: PIN が空の従業員で、PIN なし・任意の PIN の両方でサインインし、どちらも通ることを確かめる（spec US2 のシナリオ 1・2）

### Tests for User Story 2

- [X] T022 [P] [US2] T016 のファイルに、照合が成功を返す PIN なしの従業員について、`pin=None` と任意の `pin` の両方でサインインでき、照合に渡した PIN がそのまま渡ること（端末側で捨てないこと）を追加する

### Implementation for User Story 2

- [X] T023 [US2] e2e の準備データで S001 を PIN なしにする: `services/master-data/tests/e2e/test_setup_data.py`・`services/report/tests/e2e/test_setup_data.py`、ほか `grep -rn '"pin": "1234"' services/*/tests tests/e2e` で見つかる S001 の登録（R-10）
- [X] T024 [US2] PIN 付きの従業員（例 `S-PIN`・PIN は sentinel）を、PIN の e2e（Phase 5・6）が使う準備データに追加する
- [X] T025 [US2] 既存の e2e（従業員コードだけでサインインする約 25 か所）が変更なしで通ることを、Phase 7 の全体実行で確かめる

**Checkpoint**: US1 と US2 が両方満たされる（P1 の範囲が完成）

---

## Phase 5: User Story 3 - 失敗の理由を呼び出し元に区別させず、運用者には分かるようにする (Priority: P2)

**Goal**: 失敗 3 種類で応答の本文が同じ、理由はログにだけ、PIN はどのログにも出ない（spec FR-015・FR-016・FR-019a・SC-003・SC-004）

**Independent Test**: 存在しない従業員・PIN なし・PIN 不一致で失敗させ、応答の本文全体が同じで、ログに理由が残り PIN が残らないことを確かめる（spec US3 のシナリオ 1・2）

### Tests for User Story 3

- [X] T026 [P] [US3] T016 のファイルに、同じ従業員コードで理由だけを変えた 3 種類の失敗について、`SignInOutException` の `message`・`error_code`・`user_message` が完全に一致すること、WARNING のログにテナント・端末・従業員コード・理由（`staff_not_found` / `pin_required` / `pin_mismatch`）が出ることを追加する
- [X] T027 [P] [US3] `services/terminal/tests/unit/test_sign_in_logs_no_pin.py` を新設し、DEBUG を有効にしてサインインのルートを通し（成功・誤った PIN・PIN なしの従業員への任意の PIN）、どのロガーの記録にも sentinel の PIN（正しい・誤った・任意の各値）が現れないことを確かめる。要求のログ（ミドルウェア）も対象にする

### Implementation for User Story 3

- [X] T028 [US3] `services/terminal/app/services/terminal_service.py` で、失敗の `SignInOutException` のメッセージを `Staff authentication failed: staff_id->{staff_id}`（理由を含めない）にし、理由は別の WARNING のログ行に出す（R-7）
- [X] T029 [US3] `services/terminal/app/api/v1/terminal.py` のサインインの DEBUG ログを `mask_loggable(terminal_signin)` にする（R-7・spec FR-019a）
- [X] T030 [US3] T026・T027 が通ることを確かめる

---

## Phase 6: User Story 4 - マスタに届かないときは認証の失敗にしない (Priority: P2)

**Goal**: 照合を判定できないときは 407201 / 502 で断り、端末の状態を変えない（spec FR-017・SC-005）

**Independent Test**: master-data に届かない状態でサインインし、401 / 406004 ではなく 502 / 407201 で返ることを確かめる（spec US4）

### Tests for User Story 4

- [X] T031 [P] [US4] T016 のファイルに、照合が `RepositoryException` または `ServiceUrlNotConfiguredError` を投げたとき `ExternalServiceException`（407201 / 502）になり、端末が `replace` されないこと、ERROR のログに「判定できなかった」ことが出ることを追加する

### Implementation for User Story 4

- [X] T032 [US4] `services/terminal/app/services/terminal_service.py` で、`RepositoryException`・`ServiceUrlNotConfiguredError` を `ExternalServiceException` に写す（`StaffAuthenticationException` より後に捕まえる）（R-5）
- [X] T033 [US4] T031 が通ることを確かめる

---

## Phase 7: e2e・文書・仕上げ

- [X] T034 [P] `services/terminal/tests/e2e/test_sign_in_pin.py` を新設し、実スタックで確かめる（quickstart.md 2〜5）
  - PIN 付きの従業員: 正しい PIN で 200、誤った PIN・PIN なし・空の PIN で 401 / 406004（本文全体が同じ）
  - PIN なしの従業員: PIN なし・任意の PIN で 200
  - 存在しない従業員: 401 / 406004。PIN 付きの従業員の失敗と本文を比べるときは、本文の中の従業員コードを同じ値に置き換えてから比べる（同じ従業員コードでの完全一致は T026 で確かめる）
  - 照合のエンドポイントを端末の API キーで呼ぶと 401、端末の JWT で 403
- [X] T035 [P] `docs/en/master-data/api-specification.md`・`docs/ja/master-data/api-specification.md` に、内部の照合（内部専用であること・判定表・エラーコード）と、登録・更新の `pin` が任意になったことを書く
- [X] T036 [P] `docs/en/terminal/api-specification.md`・`docs/ja/terminal/api-specification.md` のサインインに `pin`（任意）、PIN が入っている従業員は必須、失敗は 406004 / 401、照合を判定できないときは 407201 / 502 を書く
- [X] T037 変更したサービス（commons・master-data・terminal）で ruff を通す
- [X] T038 全サービスのイメージを作り直し、単体・統合・e2e（サービス横断を含む）をすべて通す。既存のサインアウト、サインイン済みの端末、staff の応答に PIN がないことのテストが変更なしで通ること（spec FR-020・FR-021）
- [ ] T039 quickstart.md の手順 6（DEBUG を有効にして sentinel の PIN がログに無い）と 7（master-data を止めて 502）を手で確かめる
- [X] T040 [P] `services/master-data/tests/unit/test_pin_comparison_is_single.py` を新設する。`services/*/app` と `services/commons/src` を走査し、`compare_digest` と、`pin` を `==` / `!=` で比べている箇所が、`StaffMasterService.verify_staff_async` の中にしかないことを検査する。検査の式を緩めて通してはならない（spec SC-006・FR-009）
- [ ] T041 PR の本文の「挙動の変化」に、次の 3 点を書く: PIN ありの従業員は PIN が要る。これまで PIN が必須だったので、ダミーの PIN が入った従業員が多い。PIN なしでサインインさせたい従業員は、PIN を空にする。リリースノートはこの内容をもとに書く

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: エラーコードと例外が照合の前提
- **Phase 2 → Phase 3〜6**: 端末のサインインは commons の新しい版（T015）と master-data の照合（T007）に依存する
- **US1（Phase 3）→ US2・US3・US4**: いずれも T019 の照合の呼び出しを前提に、テストと写像を足す
- **US2・US3・US4** は互いに独立（同じ `terminal_service.py` を触るので、実装は順に進める）
- **Phase 7** は全ストーリーの後

## Parallel Example

```text
# Phase 2 のテストは並行して書ける
T003 test_staff_verify_service.py
T004 test_api_staff_verify.py
T009 test_api_staff.py（PIN を任意に）
T012 test_staff_verify_web_repository.py

# Phase 7 の文書と静的な検査は並行
T035 master-data の API 仕様
T036 terminal の API 仕様
T040 比較が 1 か所だけであることの検査
```

## Implementation Strategy

1. **MVP**: Phase 1・2・3（US1）。PIN を登録した従業員のなりすましが止まる
2. **P1 の完成**: Phase 4（US2）。既存のクライアントとテストが動くことを確かめる。US1 と同時にリリースする（US1 だけではダミーの PIN の従業員が止まる）
3. **P2**: Phase 5（US3）・Phase 6（US4）。列挙の手がかりを消し、障害と認証の失敗を分ける
4. **仕上げ**: Phase 7。リリースノートに挙動の変化（PIN が入っている従業員は PIN が要る、PIN なしにしたい従業員は PIN を空にする）を書く
