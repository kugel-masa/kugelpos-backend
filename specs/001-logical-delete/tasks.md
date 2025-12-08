# タスク: 商品カテゴリマスターの論理削除

**日付**: 2025-12-08
**ブランチ**: 001-logical-delete
**入力**: `/specs/001-logical-delete/` からの設計ドキュメント
**前提条件**: plan.md（必須）、spec.md（必須）、research.md、data-model.md、contracts/

## フォーマット: `[ID] [P?] [Story] 説明`

- **[P]**: 並列実行可能（異なるファイル、依存関係なし）
- **[Story]**: このタスクが属するユーザーストーリー（例: US1, US2, US3）
- 説明には正確なファイルパスを含む

---

## Phase 1: セットアップ（共通インフラ）

**目的**: プロジェクト初期化と基本構造

- [ ] T001 ブランチ作成とディレクトリ構造確認: `services/master-data/` 配下の既存構造を確認
- [ ] T002 憲章準拠確認: マイクロサービスアーキテクチャ、テストファースト開発の原則確認

---

## Phase 2: 基盤（必須前提条件）

**目的**: すべてのユーザーストーリー実装前に完了必須のコアインフラ

**⚠️ 重要**: このフェーズ完了まで、ユーザーストーリー作業は開始不可

- [ ] T003 マイグレーションスクリプト作成: `scripts/migrations/add_logical_delete_to_category_master.py` にすべてのテナントデータベースへのフィールド追加スクリプトを実装
- [ ] T004 マイグレーション実行と検証: 既存データに `is_deleted=False, deleted_at=None` を設定し、インデックスを作成
- [ ] T005 データモデル更新: `services/master-data/app/models/documents/category_master_document.py` に `is_deleted` (bool, default=False) と `deleted_at` (datetime, optional) フィールド追加
- [ ] T006 Pydanticバリデータ追加: CategoryMasterDocument に deleted_at の検証ロジック（is_deleted=True時はdeleted_at必須、False時はNone）を実装
- [ ] T007 エラーコード定義: `services/master-data/app/exceptions/master_data_exceptions.py` に論理削除関連のエラーコード（70YYZZ形式）を追加

**チェックポイント**: 基盤準備完了 - ユーザーストーリー実装を並列開始可能

---

## Phase 3: User Story 1 - カテゴリの論理削除 (Priority: P1) 🎯 MVP

**目標**: 削除操作を物理削除から論理削除に変更し、is_deletedフラグで管理する

**独立テスト**: カテゴリを削除してもデータベースに残り、is_deleted=Trueになることを確認

### User Story 1 のテスト（テストファースト開発 - 憲章必須） ⚠️

> **注意: 実装前にこれらのテストを作成し、失敗することを確認**

- [ ] T008 [P] [US1] データクリーンアップテスト作成: `services/master-data/tests/test_clean_data.py` の既存構造に論理削除テスト用クリーンアップ追加
- [ ] T009 [P] [US1] テストデータセットアップ: `services/master-data/tests/test_setup_data.py` に論理削除テスト用カテゴリデータ作成処理追加
- [ ] T010 [US1] 論理削除機能テスト作成: `services/master-data/tests/test_category_master_logical_delete.py` に以下のテストケースを実装
  - カテゴリ削除（DELETEエンドポイント）でis_deleted=True、deleted_atに日時設定を確認
  - 削除後も一意制約（tenant_id, category_code）が維持されることを確認
  - 既に削除済みカテゴリの再削除が冪等性を保つ（成功応答）ことを確認
  - データベースから物理削除されていないことを確認

### User Story 1 の実装

- [ ] T011 [US1] リポジトリ層: 論理削除メソッド追加 - `services/master-data/app/models/repositories/category_master_repository.py` に `soft_delete_async(tenant_id, category_code)` メソッド実装（is_deleted=True, deleted_at=utcnow()を設定）
- [ ] T012 [US1] リポジトリ層: デフォルトクエリ更新 - `category_master_repository.py` のすべての取得メソッドにis_deleted=Falseフィルタを追加（後方互換性維持）
- [ ] T013 [US1] サービス層: 論理削除ロジック追加 - `services/master-data/app/services/category_master_service.py` に論理削除処理を実装（カテゴリ存在確認、リポジトリ呼び出し）
- [ ] T014 [US1] API層: DELETEエンドポイント変更 - `services/master-data/app/api/v1/endpoints/category_master.py` の削除エンドポイントを物理削除から論理削除に変更（サービス層呼び出し）
- [ ] T015 [US1] レスポンススキーマ拡張: `services/master-data/app/api/v1/schemas.py` に is_deleted と deleted_at フィールド追加
- [ ] T016 [US1] 共通スキーマ更新: `services/master-data/app/api/common/schemas.py` の共通レスポンススキーマに論理削除フィールド追加（必要に応じて）
- [ ] T017 [US1] エラーハンドリング追加: 削除済みカテゴリ検出時の404エラー応答実装
- [ ] T018 [US1] ログ追加: 論理削除操作のログ出力（カテゴリコード、テナントID、削除日時）

**チェックポイント**: この時点で User Story 1 は完全に機能し、独立してテスト可能

---

## Phase 4: User Story 2 - 削除済みカテゴリの取得 (Priority: P2)

**目標**: include_deletedパラメータを追加し、削除済みカテゴリも取得可能にする

**独立テスト**: include_deleted=trueで削除済みカテゴリが取得でき、falseで取得できないことを確認

### User Story 2 のテスト（テストファースト開発 - 憲章必須） ⚠️

- [ ] T019 [US2] include_deletedテスト作成: `services/master-data/tests/test_category_master_include_deleted.py` に以下のテストケースを実装
  - include_deleted=falseでは削除済みカテゴリが返されないことを確認
  - include_deleted=trueでは削除済みカテゴリが含まれることを確認
  - 一覧取得エンドポイントでの動作確認
  - 特定カテゴリ取得エンドポイントでの動作確認

### User Story 2 の実装

- [ ] T020 [US2] リポジトリ層: 条件付き取得メソッド追加 - `services/master-data/app/models/repositories/category_master_repository.py` に `find_all_async(tenant_id, include_deleted=False)` と `find_by_code_async(tenant_id, category_code, include_deleted=False)` を実装
- [ ] T021 [US2] サービス層: include_deletedパラメータ対応 - `services/master-data/app/services/category_master_service.py` の取得メソッドに include_deleted パラメータ追加
- [ ] T022 [US2] API層: GETエンドポイントクエリパラメータ追加 - `services/master-data/app/api/v1/endpoints/category_master.py` の一覧取得と特定カテゴリ取得に `include_deleted: bool = Query(False)` パラメータ追加
- [ ] T023 [US2] エラーハンドリング: 削除済みカテゴリ取得時の404エラー（include_deleted=false時のみ）実装
- [ ] T024 [US2] OpenAPI仕様更新: contracts/category_master_api.yaml に準拠した動作確認

**チェックポイント**: この時点で User Story 1 と User Story 2 の両方が独立して動作

---

## Phase 5: User Story 3 - 削除済みカテゴリの復元 (Priority: P3)

**目標**: 削除済みカテゴリを有効な状態に戻す復元機能を提供

**独立テスト**: 削除済みカテゴリを復元してis_deleted=False、deleted_at=Nullになることを確認

### User Story 3 のテスト（テストファースト開発 - 憲章必須） ⚠️

- [ ] T025 [US3] 復元機能テスト作成: `services/master-data/tests/test_category_master_restore.py` に以下のテストケースを実装
  - 削除済みカテゴリの復元成功（is_deleted=False、deleted_at=None）を確認
  - 有効なカテゴリの復元試行で400エラーを確認
  - 存在しないカテゴリの復元試行で404エラーを確認
  - 復元後のカテゴリが通常の取得APIで返されることを確認

### User Story 3 の実装

- [ ] T026 [US3] リポジトリ層: 復元メソッド追加 - `services/master-data/app/models/repositories/category_master_repository.py` に `restore_async(tenant_id, category_code)` メソッド実装（is_deleted=False設定、deleted_atクリア）
- [ ] T027 [US3] サービス層: 復元ロジック実装 - `services/master-data/app/services/category_master_service.py` に復元処理実装（削除済みチェック、エラーハンドリング、リポジトリ呼び出し）
- [ ] T028 [US3] API層: 復元エンドポイント追加 - `services/master-data/app/api/v1/endpoints/category_master.py` に `POST /category-master/{category_code}/restore` エンドポイント実装
- [ ] T029 [US3] エラーハンドリング実装:
  - 削除されていないカテゴリ復元時の400エラー
  - カテゴリが見つからない時の404エラー
- [ ] T030 [US3] ログ追加: 復元操作のログ出力（カテゴリコード、テナントID、復元日時）

**チェックポイント**: すべてのユーザーストーリーが独立して機能する状態

---

## Phase 6: 仕上げと横断的関心事

**目的**: 複数のユーザーストーリーに影響する改善

- [ ] T031 [P] 統合テスト実行: すべてのテストを順次実行（test_clean_data.py → test_setup_data.py → 機能テスト）し、パスすることを確認
- [ ] T032 [P] パフォーマンステスト: is_deletedインデックスによるクエリパフォーマンス確認（p95 < 200ms）
- [ ] T033 [P] ドキュメント最終更新: quickstart.md の手順を検証し、必要に応じて修正
- [ ] T034 [P] API契約検証: contracts/category_master_api.yaml とすべてのエンドポイントの動作が一致することを確認
- [ ] T035 コードレビュー準備: コードスタイル確認（ruff format, ruff check）
- [ ] T036 マイグレーション検証: 開発環境で全テナントへのマイグレーション実行とロールバック手順確認
- [ ] T037 [P] 既存カテゴリ参照の影響確認: 他サービスからのカテゴリ参照に問題がないことを確認（変更通知不要を確認）
- [ ] T038 quickstart.md 検証: クイックスタートガイドに従って動作確認

---

## 依存関係と実行順序

### フェーズ依存関係

- **セットアップ (Phase 1)**: 依存なし - 即座に開始可能
- **基盤 (Phase 2)**: セットアップ完了に依存 - すべてのユーザーストーリーをブロック
- **ユーザーストーリー (Phase 3-5)**: すべて基盤フェーズ完了に依存
  - ユーザーストーリーは並列実行可能（スタッフがいる場合）
  - または優先順位順に順次実行（P1 → P2 → P3）
- **仕上げ (Final Phase)**: すべての必要なユーザーストーリー完了に依存

### ユーザーストーリー依存関係

- **User Story 1 (P1)**: 基盤（Phase 2）完了後に開始可能 - 他ストーリーへの依存なし
- **User Story 2 (P2)**: 基盤（Phase 2）完了後に開始可能 - US1と統合するが独立してテスト可能
- **User Story 3 (P3)**: 基盤（Phase 2）完了後に開始可能 - US1/US2と統合するが独立してテスト可能

### 各ユーザーストーリー内

- テスト（含まれる場合）は実装前に作成し、失敗することを確認必須
- モデル → サービス → エンドポイントの順
- コア実装 → 統合の順
- ストーリー完了後に次の優先度へ移行

### 並列実行の機会

- セットアップタスク中の[P]マーク付きは並列実行可能
- 基盤フェーズ内の[P]マーク付きは並列実行可能（Phase 2内）
- 基盤フェーズ完了後、すべてのユーザーストーリーを並列開始可能（チーム容量があれば）
- ユーザーストーリー内のテストで[P]マーク付きは並列実行可能
- ユーザーストーリー内のモデルで[P]マーク付きは並列実行可能
- 異なるユーザーストーリーは異なるチームメンバーによる並列作業可能

---

## 並列実行の例: User Story 1

```bash
# User Story 1 のすべてのテストを一緒に起動（テストファースト）:
Task T008: "データクリーンアップテスト作成"
Task T009: "テストデータセットアップ"
（T010は T008, T009 完了後）

# User Story 1 のモデル・リポジトリを一緒に実装:
Task T011: "リポジトリ層: 論理削除メソッド追加"
Task T012: "リポジトリ層: デフォルトクエリ更新"
```

---

## 実装戦略

### MVP優先（User Story 1のみ）

1. Phase 1: セットアップ完了
2. Phase 2: 基盤完了（重要 - すべてのストーリーをブロック）
3. Phase 3: User Story 1 完了
4. **停止して検証**: User Story 1 を独立してテスト
5. 準備できていればデプロイ/デモ

### 段階的デリバリー

1. セットアップ + 基盤完了 → 基盤準備完了
2. User Story 1 追加 → 独立してテスト → デプロイ/デモ（MVP!）
3. User Story 2 追加 → 独立してテスト → デプロイ/デモ
4. User Story 3 追加 → 独立してテスト → デプロイ/デモ
5. 各ストーリーは前のストーリーを壊さずに価値を追加

### 並列チーム戦略

複数の開発者がいる場合:

1. チームでセットアップ + 基盤を一緒に完了
2. 基盤完了後:
   - 開発者A: User Story 1
   - 開発者B: User Story 2
   - 開発者C: User Story 3
3. ストーリーは独立して完了・統合

---

## 注意事項

- [P] タスク = 異なるファイル、依存関係なし
- [Story] ラベルはタスクを特定のユーザーストーリーにマッピング（トレーサビリティ）
- 各ユーザーストーリーは独立して完了・テスト可能であるべき
- 実装前にテストが失敗することを確認
- 各タスクまたは論理グループ後にコミット
- 任意のチェックポイントで停止し、ストーリーを独立して検証
- 避けるべき: 曖昧なタスク、同じファイルの競合、ストーリーの独立性を壊す横断的依存関係
- テストファースト開発は憲章で必須 - すべての機能実装前にテストを作成

---

## 完了基準（plan.mdより）

以下の条件をすべて満たすこと:

1. ✅ すべてのテストがパス
2. ✅ マイグレーションが成功
3. ✅ APIコントラクトに準拠
4. ✅ 既存APIの応答時間を維持（<200ms p95）
5. ✅ 憲章のすべての必須原則に準拠
6. ✅ コードレビュー承認
7. ✅ ドキュメント更新完了
