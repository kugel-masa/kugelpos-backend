# Tasks: 処理できなかったイベントを見えるようにし、直したあとに流し直せるようにする

**Input**: `/specs/230-dead-letter-handling/` の設計文書（plan.md、spec.md、research.md、data-model.md、contracts/、quickstart.md）
**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/

**Tests**: plan.md の Testing で求めているので含める（unit・integration・e2e）。テストは実装より先に書き、失敗することを確かめてから実装する。

**Organization**: ユーザーストーリーごとに分ける。共通の部分は commons の `kugel_common.dead_letter` に置き、3 サービス（report・journal・stock）は配線だけにする（plan の Structure Decision）。Dapr のコンポーネントと RabbitMQ の設定は変えない（R-1）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかと並行できる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どのユーザーストーリーのタスクか（US1〜US5）
- パスはリポジトリのルートから

---

## Phase 1: Setup（共通の準備）

**Purpose**: パッケージの骨組みとエラーコード

- [X] T001 `services/commons/src/kugel_common/dead_letter/` を作り、`__init__.py`・`document.py`・`outcome.py`・`repository.py`・`failure.py`・`alerts.py`・`unrecordable.py`・`sweep.py`・`replay.py`・`router.py` の空のモジュールを置く（plan の Source Code）
- [X] T002 [P] report のエラーコード 413009（流し直し・破棄の状態の衝突、409）を `services/report/app/exceptions/report_error_codes.py` と `report_exceptions.py` に足す（R-10）
- [X] T003 [P] journal のエラーコード 411007 を `services/journal/app/exceptions/journal_error_codes.py` と `journal_exceptions.py` に足す（R-10）
- [X] T004 [P] stock のエラーコード 414404 を `services/stock/app/exceptions/stock_error_codes.py` と `stock_exceptions.py` に足す（R-10）

---

## Phase 2: Foundational（すべてのストーリーの前提）

**Purpose**: 記録の文書・本体の結果・リポジトリ・索引、受け手の処理の分割、受け直しの予算

**⚠️ CRITICAL**: これが終わるまで、ユーザーストーリーの作業は始めない

### テスト

- [X] T005 [P] `DeadLetterDocument` の形（`_id` = イベント ID、状態の定数、`episode_failure_count`・`notify_claimed_at`・`notify_attempts`、camelCase の別名）、`HandlerOutcome`（`PROCESSED` / `ALREADY_PROCESSED` / `DROPPED(理由)` / `FAILED(理由)`）、諦める回数 `DEAD_LETTER_GIVE_UP_AFTER_FAILURES`（既定 17、環境変数で変えられる）、`last_error` の作り方（例外の型 + `mask_sensitive_data` を通して 200 文字で切ったメッセージ、R-15）のユニットテストを `services/commons/tests/unit/test_dead_letter_document.py` に書く
- [X] T006 [P] 索引（`(state, last_dead_at desc)`、`(topic, state, last_dead_at desc)`、`(state, last_failed_at)`、`(state, notified_at, last_dead_at)`、`purge_at` の TTL `expireAfterSeconds: 0`）を作ることのユニットテストを `services/commons/tests/unit/test_dead_letter_indexes.py` に書く（data-model の索引）
- [X] T007 [P] 3 サービスの本体が `Request` 無しで呼べ、`HandlerOutcome` を返し、`record_failure` も発行した側への通知も呼ばないこと、購読のルートが結果を SUCCESS / DROP / RETRY に変え、`PROCESSED` / `ALREADY_PROCESSED` のときだけ発行した側に「受け取った」を伝えることのユニットテストを `services/report/tests/unit/test_dead_letter_handler_core.py`、`services/journal/tests/unit/test_dead_letter_handler_core.py`、`services/stock/tests/unit/test_dead_letter_handler_core.py` に書く（R-3）

### 実装

- [X] T008 `services/commons/src/kugel_common/dead_letter/document.py` に `DeadLetterDocument`（data-model の全フィールド）、`DeadLetterAlertDocument`（`topics` のキーは記録の `topic` と同じ）、状態の定数、諦める回数、`summary` を作る関数、`last_error` を作る関数を、`outcome.py` に `HandlerOutcome` を書く
- [X] T009 `services/report/tests/unit/test_pubsub_redelivery_budget.py` に、次の確かめを足す（T008 のあと。諦める回数を `kugel_common.dead_letter` から読む）（R-1、contracts/dead-letter-recording.md）
  - 諦める回数の既定値（17）が、3 つのコンポーネントの `maxRetries` + 1（今は 19）より 2 回以上少ない
  - 待ち時間の最も遅い合計に、1 回の配送の処理の枠 × 配送の回数を足しても `consumer_timeout` より短い
  - 掃除が「失敗中」を取り残しとみなす時間（30 分）が、待ち時間の最も遅い合計より長い
- [X] T010 `services/commons/src/kugel_common/dead_letter/repository.py` に `DeadLetterRepository`（`AbstractRepository` を継承）と索引を作る関数を書く（T008 のあと）
- [X] T011 [P] report の索引の準備に `dead_letter` と `dead_letter_alert` を足す: `services/report/app/database/database_setup.py`（T010 のあと。既存テナントは起動時の索引の準備で作る。#343 と同じ）
- [X] T012 [P] journal の索引の準備に同じものを足す: `services/journal/app/database/database_setup.py`（T010 のあと）
- [X] T013 [P] stock の索引の準備に同じものを足す: `services/stock/app/database/database_setup.py`（T010 のあと）
- [X] T014 [P] report の `handle_log` を、本体（CloudEvent の dict とトピックを受け、`LogService` を本体の中で組み立て、`HandlerOutcome` を返す）と購読の薄いルート（結果を Dapr への応答に変え、`PROCESSED` / `ALREADY_PROCESSED` のときに発行した側に伝える）に分ける。今の依存 `get_log_service_from_request` が組み立てている `LogService` と `receive_method` の渡し方を、本体の中に移す: `services/report/app/api/v1/tran.py`（T008 のあと、R-3）
- [X] T015 [P] journal の `handle_log` を同じく分ける: `services/journal/app/api/v1/tran.py`（T008 のあと）
- [X] T016 [P] stock の `handle_transaction_log` を同じく分ける。中身をマスクせずに出しているログ（失敗の分岐など）を `mask_sensitive_data` を通すように直す: `services/stock/app/api/v1/stock.py`（T008 のあと、R-15）

**Checkpoint**: 記録の入れ物と、流し直しから呼べる受け手の本体ができた

---

## Phase 3: User Story 1 - 処理できなかったイベントに気づける (Priority: P1) 🎯 MVP

**Goal**: 失敗が 17 回続いたイベントを、受け手が諦めて 1 件記録し、「未対応」になったときに通知する。数え損ねたものと送り損ねた通知は掃除が拾う

**Independent Test**: 必ず失敗するイベントを 1 件流し、17 回目の失敗で記録が `pending`（`last_error`・`message` あり）になり、通知が 1 回届き、`dlq-*` には何も入らない

### テスト

- [X] T017 [P] [US1] 失敗の記録のユニットテスト（data-model の状態の表の「処理の失敗」の列のすべてのマス。記録が無い → `failing`・`message` の保存・`purge_at` +1 日、`failing` で 16 回目までは `KEEP_RETRYING`・17 回目で `pending`、`pending` / `replaying` は理由と回数だけで `ALREADY_RECORDED`、`replayed` / `discarded` は `message` の書き直し・`purge_at` を now + 1 日まで延ばす・17 回目で `pending`。`$` で始まる値とキーを持つ中身がそのまま保存される）を `services/commons/tests/unit/test_dead_letter_failure.py` に書く（R-4）
- [X] T018 [P] [US1] `record_failure` のユニットテスト（返り値 `GAVE_UP` / `ALREADY_RECORDED` / `KEEP_RETRYING`、`GAVE_UP` のときだけ通知、重複キーなら 1 回やり直す、5 秒を超えたら書けなかったものとして扱う、書けないときは `notify_unrecordable` を呼んでから例外を上げ直す、失敗の理由が MongoDB の接続の例外なら記録を試さずに知らせる、アプリのログに `message`・`data` の中身を出さない）を `services/commons/tests/unit/test_dead_letter_record_failure.py` に書く（contracts/dead-letter-recording.md）
- [X] T019 [P] [US1] 記録できないときの知らせ（`notify_unrecordable`）のユニットテスト（プロセスの中の 5 分の窓で最初の 1 件だけ送り、残りは数えて次の窓の最初の通知に「ほか N 件」を添える、テナント・イベント ID が無ければ `unknown`、本文に中身を載せない、送信は 5 秒まで、送れなくても例外を出さない）を `services/commons/tests/unit/test_dead_letter_unrecordable.py` に書く（R-5c）
- [X] T020 [P] [US1] 通知の窓のユニットテスト（5 分の窓で 1〜9 件は 1 件ずつ、10 件目でまとめ、11 件目からは送らず `suppressed` を数える、次の窓の最初の通知に `carried_suppressed` を添える）と、本文に中身が載らず、失敗の理由が例外の型だけであることを `services/commons/tests/unit/test_dead_letter_alerts.py` に書く（R-5a、R-15）
- [X] T021 [P] [US1] 掃除のユニットテスト（最後の失敗から 30 分の `failing` は、イベント ID の記録があれば消し、無ければ `pending` に上げて通知する。`notified_at` が空の `pending` は引き受けて送り直し、`notify_attempts` は 5 回まで、引き受けは 10 分で取り直せる、送り直しは窓を進めない、テナントごとに 100 件まで、失敗してもログだけ）を `services/commons/tests/unit/test_dead_letter_sweep.py` に書く（R-14）
- [X] T022 [P] [US1] report・journal の `get_log_service_from_request` で、`tenant_id` が無いときに `notify_unrecordable` が呼ばれ、応答は今までどおり 400 であることのユニットテストを `services/report/tests/unit/test_dead_letter_no_tenant_notice.py` と `services/journal/tests/unit/test_dead_letter_no_tenant_notice.py` に書く（R-6）
- [X] T023 [P] [US1] 実際の MongoDB での統合テスト（パイプラインの更新、17 回目で `pending`、索引が無い DB でも同じイベントの失敗を同時に走らせて記録は 1 件・「未対応になった」と通知は 1 回、`pending` のあとの失敗はすぐ SUCCESS、`dead_count` が正確、窓の同時の更新で数がずれない、掃除の条件付きの更新が 2 つ同時に走っても二重に上げない、TTL の索引）を `services/report/tests/integration/test_dead_letter_failure.py` に書く

### 実装

- [X] T024 [US1] `repository.py` に失敗の記録（1 回のパイプラインの `find_one_and_update`、upsert、変更前を返す、外から来た値は `$literal`、状態ごとの書き分けと 17 回目の `pending` への切り替え）、`notified_at` の書き込み、掃除のための条件付きの更新（`failing` → `pending`、`failing` の削除、通知の引き受け）を書く（R-4、R-14、data-model の表）
- [X] T025 [US1] `services/commons/src/kugel_common/dead_letter/alerts.py` に、通知の窓（`dead_letter_alert` の 1 回のパイプラインの `find_one_and_update`、upsert、変更後を返す）と本文（1 件・まとめ・前の窓の送らなかった数・掃除が上げたとき）を書き、`send_warning_notification` で 5 秒の上限を付けて送る（R-5、R-5a）
- [X] T026 [US1] `services/commons/src/kugel_common/dead_letter/unrecordable.py` に `notify_unrecordable`（プロセスの中の 5 分の窓、本文、送信は 5 秒まで、送れなくても例外を出さない）を書く（R-5c）
- [X] T027 [US1] `services/commons/src/kugel_common/dead_letter/failure.py` に `record_failure`（MongoDB の接続の例外なら知らせだけ → 記録（5 秒まで、重複キーで 1 回やり直し）→ 変更前の文書から判断 → `GAVE_UP` なら窓を進めて通知 → `notified_at`。書けないときは `notify_unrecordable` で知らせてから例外を上げ直す）を書く（T024〜T026 のあと）
- [X] T028 [US1] `services/commons/src/kugel_common/dead_letter/sweep.py` に掃除（DB の名前からテナントを集める、取り残された `failing` と送り損ねた通知、状態ストアでイベント ID を確かめる関数を受け取る、テナントごとに 100 件まで）と、5 分ごとに走らせる仕組みを書く（T024・T025 のあと、R-14）
- [X] T029 [P] [US1] report の T014 の購読のルートで、`FAILED` なら `record_failure` を await で呼び、`GAVE_UP` / `ALREADY_RECORDED` なら SUCCESS、`KEEP_RETRYING` か例外なら RETRY を返す。発行した側への「受け取った」は送らない: `services/report/app/api/v1/tran.py`（T027 のあと）
- [X] T030 [P] [US1] journal の T015 の購読のルートで同じく: `services/journal/app/api/v1/tran.py`（T027 のあと）
- [X] T031 [P] [US1] stock の T016 の購読のルートで同じく: `services/stock/app/api/v1/stock.py`（T027 のあと）
- [X] T032 [US1] report・journal の `get_log_service_from_request` の、`tenant_id` が無くて 400 を返す分岐で `notify_unrecordable`（トピック、イベント ID があれば）を呼ぶ。400 は変えない: `services/report/app/api/v1/tran.py`、`services/journal/app/api/v1/tran.py`（T029・T030 と同じファイルなので、そのあと）
- [X] T033 [P] [US1] 3 サービスの起動で掃除を始め、停止で止める。状態ストアでイベント ID を確かめる関数（購読の重複の確かめと同じもの）を渡す: `services/report/app/main.py`、`services/journal/app/main.py`、`services/stock/app/main.py`（T028 のあと）
- [ ] T034 [P] [US1] journal・stock にも T023 と同じ統合テストを置く: `services/journal/tests/integration/test_dead_letter_failure.py`、`services/stock/tests/integration/test_dead_letter_failure.py`

**Checkpoint**: 失敗し続けたイベントが記録され、通知される。数え損ねと送り損ねも掃除が拾う。ここだけで MVP として届けられる

---

## Phase 4: User Story 2 - 原因を直したあとに流し直せる (Priority: P1)

**Goal**: 未対応の記録を、その受け手にだけ流し直す（1 件は同期、まとめては裏で）

**Independent Test**: 記録のあるイベントの原因を取り除いて流し直し、受け手が処理し（閉設ログなら精算実績が確定になり日報が出る）、記録が `replayed` になる。原因が残っていれば `failed` が返り、記録は `pending` のまま

### テスト

- [X] T035 [P] [US2] `get_user_with_token` のユニットテスト（利用者の JWT は利用者名と `tenant_id` を返す、端末の JWT・サービスアカウントの JWT（`is_service_account`）は 403、JWT 無し（API キーだけを含む）は 401）を `services/commons/tests/unit/test_get_user_with_token.py` に書く（R-9）
- [X] T036 [P] [US2] 流し直しのユニットテスト（引き受けの条件、10 分を過ぎた `replaying` の引き受け直しで新しい `replay_claim_id`、`PROCESSED` / `ALREADY_PROCESSED` → `replayed`・`resolved_*`・`episode_failure_count` 0・`purge_at` +90 日、そのあと時間の上限の外で発行した側に伝える、`DROPPED` → `discarded`・`resolved_by = system`・`resolution_note`、`FAILED`・例外・30 秒の時間切れ → `pending` で理由と回数を流し直しが書き通知しない、`record_failure` と `notify_unrecordable` を呼ばない、結果の書き込みは `state = replaying` と自分の claim id が条件、アプリのログに中身を出さない）を `services/commons/tests/unit/test_dead_letter_replay.py` に書く（R-3、R-7、data-model の流し直しの結果）
- [X] T037 [P] [US2] 流し直しの API のユニットテスト（1 件: 200 の `replayed` / `discarded` / `failed`、`pending` でなければ 409 とサービスのコード、無ければ 404 `100001`。まとめて: 1〜100 件、超えたら 422、重複は 1 件に、202 と `accepted`、裏で 1 件ずつ流れ、`pending` でないものは飛ばす。テナントの違う JWT は 403）を `services/commons/tests/unit/test_dead_letter_replay_api.py` に書く（contracts/dead-letter-api.md）
- [X] T038 [P] [US2] 実際の MongoDB での統合テスト（原因が残ったままの流し直しで `failed`・記録は `pending`・`replayed` にならない、同時の流し直しで処理は 1 回、引き受け直しのあとの遅れた結果は書かれない、流し直し中に購読から同じイベントが届いて失敗したらすぐ SUCCESS で状態は変わらない、まとめての流し直しの途中でタスクを止めても `replaying` は 10 分で取り直せる）を `services/report/tests/integration/test_dead_letter_replay.py` に書く
- [ ] T039 [P] [US2] 流し直しがほかの受け手に届かないこと・受け手が二重に数えないこと、stock で複数の品目の途中で止めたあとの流し直しで在庫が二重に動かないことの統合テストを `services/journal/tests/integration/test_dead_letter_replay.py` と `services/stock/tests/integration/test_dead_letter_replay.py` に書く（FR-009、FR-010、SC-004）

### 実装

- [X] T040 [US2] `services/commons/src/kugel_common/security.py` に `get_user_with_token` を足す（R-9）
- [X] T041 [US2] `repository.py` に、引き受け（`pending`、または 10 分を過ぎた `replaying` → `replaying`、`replay_claim_id`・`replay_claimed_at`）と、claim を条件にした結果の書き込み（失敗のときは理由と回数も）を書く（R-7）
- [X] T042 [US2] `services/commons/src/kugel_common/dead_letter/replay.py` に、流し直し（引き受け → 本体を `asyncio.wait_for` 30 秒で呼ぶ → 結果を書く → 処理できたら時間の上限の外で発行した側に伝える）と、まとめての流し直し（裏の処理で 1 件ずつ順に）を書く（T041 のあと）
- [X] T043 [US2] `router.py` に、流し直し（1 件は同期、まとめては 202 で裏に回す）のルートを作る関数を書く（`get_user_with_token`、パスのテナントと JWT のテナントをルーターで比べて違えば 403、サービスごとの 409 のコードと本体と発行した側への通知を受け取る、`resolved_by` に利用者名）
- [X] T044 [P] [US2] report にルーターを取り付け、T014 の本体・通知と 413009 を渡す: `services/report/app/main.py`（T033 のあと）
- [X] T045 [P] [US2] journal に取り付け、T015 の本体・通知と 411007 を渡す: `services/journal/app/main.py`（T033 のあと）
- [X] T046 [P] [US2] stock に取り付け、T016 の本体・通知と 414404 を渡す: `services/stock/app/main.py`（T033 のあと）
- [ ] T047 [US2] 精算が確定した営業の取引を流し直しても、確定した精算実績と日報が変わらないことの統合テストを `services/report/tests/integration/test_dead_letter_replay_settled_session.py` に書く（US2-6、#343）

**Checkpoint**: 記録から流し直せ、#343 の仮のままの精算実績を直せる

---

## Phase 5: User Story 3 - 流し直さないと決めたものを片付けられる (Priority: P2)

**Goal**: 未対応の記録を理由付きで破棄にする

**Independent Test**: 記録を理由付きで破棄にすると、未対応の一覧から消え、破棄した人・日時・理由が残る

- [X] T048 [P] [US3] 破棄のユニットテスト（`pending` だけ → `discarded`・`purge_at` +90 日・`resolved_by`・`resolution_note`・`episode_failure_count` 0、ほかは 409、`reason` が空なら 422、破棄したあとに同じイベントが 17 回失敗すると `pending` に戻って通知）を `services/commons/tests/unit/test_dead_letter_discard.py` に書く
- [X] T049 [US3] `repository.py` に条件付きの破棄を書く
- [X] T050 [US3] `router.py` に破棄のルート `POST /api/v1/tenants/{tenant_id}/dead-letters/{id}/discard` を足す（3 サービスは T044〜T046 の取り付けでそのまま使える）
- [ ] T051 [US3] 破棄の統合テスト（流し直しと破棄が同時のとき一方だけ通る）を `services/report/tests/integration/test_dead_letter_discard.py` に書く

**Checkpoint**: 対応の要らないものを片付けられる

---

## Phase 6: User Story 4 - 未対応のものを一覧で見られる (Priority: P2)

**Goal**: 状態・トピック・通知の有無・期間で絞った一覧と、1 件の照会

**Independent Test**: 状態の違う記録をいくつか作り、絞り込みと照会が期待どおりの記録だけを返す。別のテナントの記録は返らない。照会の中身の秘密は伏せられている

- [X] T052 [P] [US4] 一覧と照会のユニットテスト（既定 `state=pending`、`failing` は出さない、`all`、`topic`、`notified=false`、`dead_from` / `dead_to`（「未対応」になった日時）、`limit` 1〜200・`page`、`lastDeadAt` の新しい順、`metadata.total`、`id` はイベント ID、一覧に `message` を含めない、照会は `mask_loggable` を通した `message` を含める（開設精算のログの端末の `api_key` が伏せられる）、無ければ 404 `100001`、別のテナントは 403）を `services/commons/tests/unit/test_dead_letter_list_api.py` に書く（contracts/dead-letter-api.md、R-15）
- [X] T053 [US4] `repository.py` に一覧（索引に沿った絞り込みと並び、件数）と照会を書く
- [X] T054 [US4] `router.py` に一覧 `GET /api/v1/tenants/{tenant_id}/dead-letters` と照会 `GET .../dead-letters/{id}` を足し、応答のスキーマ（camelCase、`ApiResponse`、照会の `message` はマスク）を書く
- [ ] T055 [US4] 一覧の統合テスト（索引が使われる絞り込み、テナントの分離）を `services/report/tests/integration/test_dead_letter_list.py` に書く

**Checkpoint**: たまっているものを見て、流し直しと破棄の対象を選べる

---

## Phase 7: User Story 5 - 受け直しのたびの通知をやめる (Priority: P2)

**Goal**: report・journal の受け直しのたびの重大エラーの通知をやめる（失敗はログに残る）

**Independent Test**: 必ず失敗するイベントを流し、諦めるまでに届く通知が、記録が「未対応」になったときの 1 回だけ

**Depends on**: US1（代わりの通知）

- [X] T056 [P] [US5] report の購読の処理が失敗しても `send_fatal_error_notification` を呼ばないことのユニットテストを `services/report/tests/unit/test_dead_letter_no_fatal_per_attempt.py` に書く。既存の `services/report/tests/unit/test_log_service.py` の `send_fatal_error_notification` を当てている 3 か所と、`test_pubsub_notification_is_best_effort.py` の食い違うところを直す
- [X] T057 [P] [US5] journal で同じテストを `services/journal/tests/unit/test_dead_letter_no_fatal_per_attempt.py` に書く。既存の `services/journal/tests/unit/test_log_service.py` の、通知が 1 回送られることを確かめるテスト（`fatal.assert_awaited_once()`）を、送られないことの確かめに直す
- [X] T058 [US5] `services/report/app/services/log_service.py` の `send_fatal_error_notification` の 3 か所を外し、ログに残す（T056 のあと）
- [X] T059 [US5] `services/journal/app/services/log_service.py` の 3 か所を外し、ログに残す（T057 のあと）

**Checkpoint**: 1 件の失敗で届く通知は 1 回

---

## Phase 8: e2e（ストーリー横断）

- [ ] T060 e2e 用の設定の上書きを置く: 諦める回数と受け直しを小さくした resiliency（`maxRetries: 3`、`maxInterval: 1s`）と `DEAD_LETTER_GIVE_UP_AFTER_FAILURES=2`、掃除の間隔と「取り残し」の時間を短くする環境変数。compose の上書きのファイル（`services/docker-compose.e2e-deadletter.yaml`）と、その上書きでスタックを立てて e2e を流す手順を `scripts/run_e2e_tests.sh` か `tests/e2e/README.md` に書く
- [ ] T061 テストから入れて戻せる故障の入れ方を決め、`tests/e2e/test_dead_letter_journey.py` の fixture にする（例: journal の保存先に同じキーで型の違う文書を先に入れて失敗させ、あとで消す。report の精算実績の文書を壊して戻す）
- [ ] T062 T060・T061 の上で、必ず失敗するイベントが記録され（通知 1 回、`dlq-*` は空）、原因を取り除いて流し直すと処理されることの e2e を `tests/e2e/test_dead_letter_journey.py` に書く。次の場面も含める
  - 閉設ログ（#343）: 精算実績が確定になり日報が出る
  - 同じイベントが report と journal の両方で失敗: 記録と通知が受け手ごとに 1 件・1 回ずつ（US1-2）
  - 諦めてから記録と通知までが 1 分以内（SC-001）
  - まとめての流し直しが 202 を返し、結果が一覧に出る
- [ ] T063 MongoDB に書けないときに「記録できない」の知らせが 1 回届き（5 分に 1 回まで）、`dlq-*` に移り、R-13 の手順（shovel で購読のキューへ）で戻すと記録されることの e2e を `tests/e2e/test_dead_letter_journey.py` に足す。サービスを止めて配送を数え損ねさせ、掃除が「未対応」に上げることも確かめる。スタックで止められないものは、quickstart の手順 5 で手で確かめ、結果を PR に書く
- [ ] T064 [P] 権限の境界の e2e（端末の JWT・サービスアカウントの JWT・API キーだけでデッドレターの API が断られる、別のテナントは 403）を `tests/e2e/test_auth_boundary.py` に足す

---

## Phase 9: Polish（文書と仕上げ）

- [X] T065 [P] エラーコード 413009・411007・414404 を `docs/en/general/error_code_spec.md` と `docs/ja/general/error_code_spec.md` に足す（FR-021）
- [X] T066 [P] `docs/en/general/dapr_components.md` と `docs/ja/general/dapr_components.md` に次を書く
  - 受け手が 17 回目の失敗で諦めて記録すること（諦める回数と resiliency の `maxRetries` の関係。Azure では resiliency を環境の側で同じに設定する前提）
  - `dlq-*` は最後の受け皿で期限が無いこと。記録できないときの知らせ（R-5c）と、それが来たときの対応
  - 定期の掃除（R-14）
  - 記録の運用（`notified=false`、確定した日報は流し直しで変わらない）
  - `dlq-*` の見つけ方と、shovel で受け手の購読のキューに戻す手順（R-13）。配備の側で `dlq-*` の長さに警報を付けることを勧める
- [X] T067 [P] 3 サービスの API の文書（`docs/{en,ja}/report/api-specification.md`、`docs/{en,ja}/journal/api-specification.md`、`docs/{en,ja}/stock/api-specification.md`）にデッドレターの API を足す（FR-021）
- [X] T068 `./scripts/build.sh commons` で 3 サービスの Pipfile.lock の commons を更新し、`ruff check` と `ruff format` を commons・report・journal・stock にかける
- [ ] T069 `./scripts/run_unit_tests.sh`、`./scripts/run_integration_tests.sh`、`./scripts/run_e2e_tests.sh` を通す。quickstart.md の手順で手で確かめる

---

## Dependencies & Execution Order

### Phase の依存

- **Setup（Phase 1）**: 依存なし
- **Foundational（Phase 2）**: Setup のあと。すべてのストーリーを止める
- **US1（Phase 3）**: Foundational のあと。MVP
- **US2（Phase 4）**: Foundational のあと。記録が要るので、テストのデータは US1 の失敗の記録で作る（US1 のあとが自然）
- **US3（Phase 5）・US4（Phase 6）**: Foundational のあと。ルーターの取り付けは US2 の T044〜T046 を使う（US2 より先にするなら、取り付けをここで行う）
- **US5（Phase 7）**: US1 のあと（代わりの通知が要る）
- **e2e（Phase 8）**: US1・US2・US5 のあと
- **Polish（Phase 9）**: すべてのあと

### ストーリーの中の順

- テストを書いて失敗を確かめる → repository → failure / alerts / unrecordable / sweep / replay → router → サービスの配線
- `repository.py`・`router.py`・各サービスの `main.py` と `tran.py` は複数のタスクが書き足すので、並行させない（[P] は別のファイルのときだけ）

### Parallel Opportunities

- T002〜T004（エラーコード）は並行
- T011〜T013（索引）、T014〜T016（処理の分割）は並行
- 各ストーリーのテスト（[P] のもの）は並行
- 3 サービスの配線（T029〜T031、T044〜T046）は並行

---

## Parallel Example: User Story 1

```bash
# テストをまとめて書く
Task: "T017 failure-recording tests in services/commons/tests/unit/test_dead_letter_failure.py"
Task: "T018 record_failure tests in services/commons/tests/unit/test_dead_letter_record_failure.py"
Task: "T019 unrecordable notice tests in services/commons/tests/unit/test_dead_letter_unrecordable.py"
Task: "T020 alert window tests in services/commons/tests/unit/test_dead_letter_alerts.py"
Task: "T021 sweep tests in services/commons/tests/unit/test_dead_letter_sweep.py"

# commons ができたら、3 サービスの配線をまとめて
Task: "T029 report route in services/report/app/api/v1/tran.py"
Task: "T030 journal route in services/journal/app/api/v1/tran.py"
Task: "T031 stock route in services/stock/app/api/v1/stock.py"
```

---

## Implementation Strategy

### MVP（US1 だけ）

1. Phase 1・2
2. Phase 3（US1）
3. **止めて確かめる**: 必ず失敗するイベントで、記録 1 件と通知 1 回、`dlq-*` は空
4. この時点で、デッドレターに気づけないという一番の問題は解ける

### 段階的に届ける

1. US1 → 気づける（MVP）
2. US2 → 流し直せる（#343 の止まった日報を直せる）
3. US5 → 受け直しのたびの通知が止まる（US1 があるので外してよい）
4. US3・US4 → 片付けと一覧
5. e2e と文書

### 注意

- 中身（`message`・`data`）をログと通知の本文に出さない。照会の `message` はマスクする（#211、FR-007、R-15）
- 成功の経路に書き込みを足さない（失敗の記録は購読のルートの `FAILED` のときだけ）
- 本体は処理の結果だけを返す。`record_failure` を本体から呼ばない（流し直しの失敗が成功に化ける）
- 外から来た値をパイプラインの更新に入れるときは `$literal` で包む
- 諦める回数と resiliency の `maxRetries` を離さない（T009 の予算のテスト）
- 公開リポジトリなので、コード・文書・コミットに下流の名前を書かない
