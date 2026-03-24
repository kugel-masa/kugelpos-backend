# Tasks: ターミナルAPIキーのライフサイクル対応JWT認証

**Input**: `/specs/67-terminal-jwt-auth/` の設計ドキュメント群
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/terminal-auth-api.md, research.md, quickstart.md

**Tests**: plan.md Phase 5で明示的にテストが要求されているため、各ストーリーにテストタスクを含む。

**Organization**: ユーザーストーリー単位でタスクをグループ化。各ストーリーは独立して実装・テスト可能。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（異なるファイル、依存関係なし）
- **[Story]**: タスクが属するユーザーストーリー（US1, US2, US3, US4, US5）
- 各タスクにファイルパスを明記

---

## Phase 1: Setup（設定追加）

**Purpose**: 共通設定にターミナルJWT有効期限の設定項目を追加

- [ ] T001 `TERMINAL_TOKEN_EXPIRE_HOURS: int = 24` を `services/commons/src/kugel_common/config/settings_auth.py` に追加

---

## Phase 2: Foundational（JWT基盤 - kugel_common）

**Purpose**: 全ユーザーストーリーが依存するJWT生成・検証の共通基盤を構築

**CRITICAL**: このフェーズが完了するまでユーザーストーリーの実装は開始不可

- [ ] T002 [P] `create_terminal_token()` 関数を新規ファイル `services/commons/src/kugel_common/utils/terminal_auth.py` に実装。TerminalInfoDocumentからJWTクレームを構築し、token_type="terminal", iss="terminal-service" を固定設定、SECRET_KEY + HS256 で署名。data-model.md のクレーム定義に準拠
- [ ] T003 [P] `verify_terminal_token()` と `terminal_claims_to_terminal_info()` 関数を `services/commons/src/kugel_common/security.py` に追加。token_type="terminal" の検証、署名・有効期限チェック、JWTクレームからTerminalInfoDocument互換オブジェクトへの変換
- [ ] T004 JWT生成・検証のユニットテストを `services/commons/tests/` に作成。正常系（クレーム検証）、有効期限切れ、不正署名、token_type不一致のテストケースを含む

**Checkpoint**: JWT生成・検証の基盤が動作。`create_terminal_token()` → JWT → `verify_terminal_token()` → クレーム → `terminal_claims_to_terminal_info()` → TerminalInfoDocument の往復が検証済み

---

## Phase 3: User Story 1 - 初回トークン取得 (Priority: P1)

**Goal**: POSターミナルがAPIキーでPOST /auth/tokenを呼び出し、JWTトークンを受け取る

**Independent Test**: 有効なAPIキーでPOST /api/v1/auth/tokenにリクエストし、正しいクレームを含むJWTが返されることを検証

### Implementation

- [ ] T005 [US1] POST /api/v1/auth/token エンドポイントを新規ファイル `services/terminal/app/api/v1/auth.py` に実装。X-API-KEYヘッダーからAPIキー取得、DBでターミナル情報をルックアップ、`create_terminal_token()` でJWT生成、contracts/terminal-auth-api.md のレスポンス形式 `{"success": true, "data": {"access_token", "token_type", "expires_in"}}` で返却。エラー時は401 + エラーコード "200101"
- [ ] T006 [US1] `auth_router` を `services/terminal/app/main.py` に `/api/v1` プレフィックスで登録
- [ ] T007 [US1] POST /auth/token のテストを `services/terminal/tests/` に作成。正常系（有効APIキー→JWT返却）、異常系（無効APIキー→401）、未オープンターミナル（status反映、スタッフクレームなし）のテストケース

**Checkpoint**: APIキーからJWTトークンを取得するフローが完全に動作

---

## Phase 4: User Story 2 - 各サービスでのローカルJWT検証 (Priority: P1)

**Goal**: 全サービスがサービス間呼び出しなしにターミナルJWTをローカル検証し、クレームからtenant_id等を抽出

**Independent Test**: 有効なターミナルJWTをAuthorizationヘッダーで任意のサービスに送信し、ターミナルサービスへの呼び出しなしに認証が成功することを検証

### Implementation

- [ ] T008 [US2] `services/commons/src/kugel_common/security.py` の `__get_tenant_id()` を修正。Authorizationヘッダーのtokenがある場合、まずterminal JWT（token_type="terminal"）としてデコードを試行し、成功すればクレームからtenant_idを返却。失敗した場合は既存のユーザーJWTパスにフォールバック
- [ ] T009 [P] [US2] `services/report/app/dependencies/get_staff_info.py` の `get_requesting_staff_id()` を修正。tokenがterminal JWTの場合、クレームから直接staff_idを取得（terminal_info取得不要）
- [ ] T010 [US2] `__get_tenant_id()` のterminal JWT対応テストを `services/commons/tests/` に追加。有効JWT→tenant_id抽出、期限切れJWT→401、不正署名→401のテストケース

**Checkpoint**: 全サービス（master-data, journal, stock, report）がターミナルJWTでローカル認証可能。サービス間認証呼び出しが不要

---

## Phase 5: User Story 3 - ライフサイクル状態変更時のトークン再発行 (Priority: P1)

**Goal**: ターミナルのopen/sign-in/sign-out/close操作成功後に、更新された状態を反映した新JWTをX-New-Tokenヘッダーで返す

**Independent Test**: ターミナルオープン操作を実行し、X-New-Tokenヘッダーに更新されたbusiness_date, open_counter, status="Opened" クレームを含む新JWTが返されることを検証

### Implementation

- [ ] T011 [US3] `services/terminal/app/api/v1/terminal.py` のライフサイクルエンドポイント（open, sign-in, sign-out, close）を修正。各操作成功後に更新された TerminalInfoDocument から `create_terminal_token()` でJWTを生成し、`X-New-Token` レスポンスヘッダーに設定。レスポンスボディは変更なし
- [ ] T012 [US3] ライフサイクルAPIのX-New-Tokenヘッダーテストを `services/terminal/tests/` に作成。open→status="Opened"+business_date+カウンター、sign-in→staff_id/staff_name追加、sign-out→staff_id/staff_name除去、close→status="Closed" のクレーム検証

**Checkpoint**: ライフサイクル操作でJWTが自動再発行され、クライアントは常に最新のターミナル状態を反映したトークンを保持

---

## Phase 6: User Story 4 - 移行期間中の後方互換性 (Priority: P2)

**Goal**: 全サービスがJWT認証とX-API-KEY認証の両方を受け付け、未アップデートのターミナルを壊さない

**Independent Test**: X-API-KEYヘッダーのみ（JWTなし）でリクエストを送信し、既存の認証フローが動作することを検証

### Implementation

- [ ] T013 [US4] `services/commons/src/kugel_common/security.py` の認証優先順位を確認・実装。contracts/terminal-auth-api.md に従い: (1) Authorization Bearer (token_type="terminal") → (2) Authorization Bearer (ユーザーJWT) → (3) X-API-KEY + terminal_id。T008の修正と整合性を確認
- [ ] T014 [US4] 後方互換性テストを `services/commons/tests/` に追加。APIキーのみ→既存フロー動作、JWT＋APIキー両方→JWT優先、JWTなし＋APIキーなし→401のテストケース

**Checkpoint**: 既存のAPIキー認証が引き続き動作し、JWT認証との共存が確認済み

---

## Phase 7: User Story 5 - CartサービスのJWTクレーム活用 (Priority: P2)

**Goal**: CartサービスがJWTクレームからターミナルコンテキストを抽出し、master-data呼び出し時にJWTを転送。ターミナルサービスへの認証呼び出しを排除

**Independent Test**: ターミナルJWT付きでカート操作リクエストを送信し、ターミナルサービスへのHTTP呼び出しが行われず、JWTクレームからTerminalInfoDocumentが構築されることを検証

### Implementation

- [ ] T015 [US5] `services/cart/app/dependencies/terminal_cache_dependency.py` に `get_terminal_info_with_jwt_or_cache()` を追加。JWTが提供された場合はクレームから `terminal_claims_to_terminal_info()` でTerminalInfoDocumentを構築（HTTP呼び出しなし）。APIキーが提供された場合は既存のキャッシュ付きフロー（後方互換）
- [ ] T016 [US5] CartのWebリポジトリ（`services/cart/app/` 内の PaymentMasterWebRepository, ItemMasterWebRepository, SettingsMasterWebRepository）を修正。JWT利用可能時は `Authorization: Bearer <jwt>` ヘッダーで master-data を呼び出し。JWT未利用時は既存の `X-API-KEY` ヘッダー（後方互換）
- [ ] T017 [US5] `services/cart/app/api/v1/tran.py` を修正し、JWT転送に対応。依存関数の切り替えを適用
- [ ] T018 [US5] CartサービスのJWT対応テストを `services/cart/tests/` に作成。JWT提供時のTerminalInfoDocument構築、JWT転送でのmaster-data呼び出し、APIキー提供時の既存フロー（後方互換）のテストケース

**Checkpoint**: Cartサービスがターミナルサービスへの認証呼び出しなしに動作し、master-dataへのJWT転送が機能

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 全ストーリーにまたがる検証と品質確認

- [ ] T019 全既存テストの実行（`./scripts/run_all_tests_with_progress.sh`）でリグレッションがないことを確認
- [ ] T020 quickstart.md の curl コマンドで認証フロー全体を手動検証（トークン取得→JWT使用→ライフサイクル操作→後方互換）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 依存なし - 即開始可能
- **Foundational (Phase 2)**: Phase 1に依存 - **全ユーザーストーリーをブロック**
- **US1 (Phase 3)**: Phase 2に依存 - JWT生成基盤が必要
- **US2 (Phase 4)**: Phase 2に依存 - JWT検証基盤が必要。US1と並列可能
- **US3 (Phase 5)**: Phase 2 + US1に依存 - トークンエンドポイントのパターンを参照
- **US4 (Phase 6)**: Phase 2 + US2に依存 - __get_tenant_id修正後に検証
- **US5 (Phase 7)**: Phase 2 + US2に依存 - ローカルJWT検証が前提
- **Polish (Phase 8)**: 全ストーリー完了後

### User Story Dependencies

```
Phase 1 (Setup)
    │
Phase 2 (Foundational) ← 全ストーリーの前提
    │
    ├── US1 (Phase 3) ←── US3 (Phase 5)  ※ US3はUS1のパターンを参照
    │
    ├── US2 (Phase 4) ←┬─ US4 (Phase 6)  ※ US4はUS2の検証
    │                   └─ US5 (Phase 7)  ※ US5はUS2のJWT検証が前提
    │
Phase 8 (Polish) ← 全ストーリー完了後
```

### Within Each User Story

- 実装 → テスト の順序
- 同一ファイルのタスクは順次実行
- [P] マークのタスクは並列実行可能

### Parallel Opportunities

```bash
# Phase 2: 基盤タスクの並列実行
Task T002: terminal_auth.py (新規ファイル)
Task T003: security.py (既存ファイルに追加)
# → T002とT003は異なるファイルなので並列可能

# Phase 3 + Phase 4: US1とUS2の並列実行
Task T005-T007: US1 (terminal/app/api/v1/auth.py)
Task T008-T010: US2 (commons/security.py + report/dependencies/)
# → 異なるサービス・ファイルなので並列可能

# Phase 7: CartのWebリポジトリ修正
Task T015: terminal_cache_dependency.py
Task T016: Web repositories (複数ファイル)
# → T016はT015の依存関数を使うため順次実行
```

---

## Implementation Strategy

### MVP First (US1 + US2 のみ)

1. Phase 1 (Setup) + Phase 2 (Foundational) を完了
2. Phase 3 (US1: トークン取得) を完了
3. Phase 4 (US2: ローカルJWT検証) を完了
4. **STOP and VALIDATE**: APIキー→JWT取得→JWTで各サービスアクセスの基本フローを検証
5. この時点で主要なパフォーマンス改善（サービス間認証呼び出しの排除）が実現

### Incremental Delivery

1. Setup + Foundational → JWT基盤完成
2. US1 (トークン取得) → テスト → **MVP: JWTが発行できる**
3. US2 (ローカル検証) → テスト → **全サービスでJWT認証が動作**
4. US3 (ライフサイクル再発行) → テスト → **状態変更時にJWTが自動更新**
5. US4 (後方互換) → テスト → **既存ターミナルが壊れないことを確認**
6. US5 (Cart最適化) → テスト → **Cart→Terminal間のHTTP呼び出し排除**
7. Polish → 全体検証

---

## Notes

- [P] タスク = 異なるファイル、依存関係なし
- [Story] ラベルでタスクをユーザーストーリーに紐付け
- 各ストーリーは独立して完了・テスト可能
- 各タスクまたは論理グループ完了後にコミット
- チェックポイントでストーリー単位の検証を実施
- master-data, journal, stock は security.py の修正で自動的にJWT対応（個別の変更不要）
