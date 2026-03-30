# Tasks: プロモーションマスタ キャッシュ改善

**Input**: Design documents from `/specs/71-promotion-cache/`
**Prerequisites**: plan.md, spec.md

**Tests**: 仕様書(spec.md)セクション11にテスト方針が明記されているため、テストタスクを含める。

**Organization**: 本機能は単一のユーザーストーリー（取引内プロモーションキャッシュ）であるため、機能要件（FR-1〜FR-4）をベースにフェーズ分割する。

## Format: `[ID] [P?] [FR?] Description`

- **[P]**: 並行実行可能（異なるファイル、依存なし）
- **[FR]**: 対応する機能要件（FR-1: 埋め込み, FR-2: プラグインI/F, FR-3: エラー処理, FR-4: 後方互換性）
- 各タスクに対象ファイルパスを含める

## Path Conventions

- `services/cart/app/` — カートサービスのソースコード
- `services/cart/tests/` — カートサービスのテストコード

---

## Phase 1: データモデル・I/F変更

**Purpose**: ReferenceMasters拡張とプラグインI/Fの変更。後続フェーズの前提となる基盤変更。

**⚠️ CRITICAL**: このフェーズが完了しないとコア実装に進めない。

- [ ] T001 [P] [FR-1] `ReferenceMasters` に `promotions` フィールドを追加し、`PromotionMasterDocument` をimportする in `services/cart/app/models/documents/cart_document.py`
- [ ] T002 [P] [FR-2] `AbstractSalesPromo.apply()` のシグネチャに `promotions: list = None` パラメータを追加する in `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py`
- [ ] T003 [FR-1] `create_cart_async()` に `promotion_master` パラメータを追加し、`cart.masters.promotions` に格納する in `services/cart/app/models/repositories/cart_repository.py`

**Checkpoint**: データモデルとI/Fの変更が完了。既存テストはこの時点で一部失敗する可能性あり（apply()シグネチャ変更のため）。

---

## Phase 2: コア実装

**Purpose**: プロモーション取得タイミングの移動とプラグイン改修。本機能の中核。

- [ ] T004 [FR-1] `cart_service.py` の `__init__` に `PromotionMasterWebRepository` のインスタンス化を追加する（プラグインからサービスへ移動） in `services/cart/app/services/cart_service.py`
- [ ] T005 [FR-1] `create_cart_async()` にプロモーションマスタ取得処理を追加し、`cart_repo.create_cart_async()` に渡す in `services/cart/app/services/cart_service.py`
- [ ] T006 [FR-3] プロモーションマスタ取得失敗時に `CartCannotCreateException` を送出する処理を追加する in `services/cart/app/services/cart_service.py`
- [ ] T007 [FR-2] `_apply_sales_promotions_async()` で `cart_doc.masters.promotions` を `strategy.apply()` に渡すよう変更する in `services/cart/app/services/cart_service.py`
- [ ] T008 [P] [FR-2] `CategoryPromoPlugin.apply()` を変更し、渡された `promotions` パラメータを使用するようにする。`configure()` でのリポジトリ生成と `apply()` 内のAPI呼び出しを削除する in `services/cart/app/services/strategies/sales_promo/category_promo.py`
- [ ] T009 [P] [FR-2] `SalesPromoSample.apply()` のシグネチャを `promotions: list = None` に合わせる in `services/cart/app/services/strategies/sales_promo/sales_promo_sample.py`

**Checkpoint**: コア実装完了。カート作成時に1回だけプロモーションを取得し、プラグインはAPI呼び出しを行わない。

---

## Phase 3: テスト修正・追加

**Purpose**: 既存テストの修正と新規テストの追加。仕様の全機能要件を検証する。

### 既存テスト修正

- [ ] T010 [P] `apply()` シグネチャ変更に伴い、既存の CategoryPromoPlugin テストを修正する（promotionsパラメータの追加） in `services/cart/tests/test_category_promo_plugin.py`
- [ ] T011 [P] `apply()` シグネチャ変更に伴い、既存のカテゴリプロモーション統合テストを修正する in `services/cart/tests/test_category_promo.py`
- [ ] T012 [P] `create_cart_async` パラメータ変更に伴い、既存の cart_service テストを修正する in `services/cart/tests/test_cart_service.py`

### 新規テスト追加

- [ ] T013 [P] [FR-1] [FR-4] 単体テスト: `ReferenceMasters` に `promotions` が格納されること、デフォルトが空リスト であること、`promotions` フィールドなしの既存カートJSONが正常にデシリアライズされることを確認する in `services/cart/tests/test_category_promo_plugin.py`
- [ ] T014 [P] [FR-2] 単体テスト: `CategoryPromoPlugin.apply()` が渡された `promotions` リストを使用し、API呼び出しを行わないことを確認する in `services/cart/tests/test_category_promo_plugin.py`
- [ ] T015 [P] [FR-3] 単体テスト: プロモーションマスタ取得失敗時に `CartCannotCreateException` が送出されることを確認する in `services/cart/tests/test_cart_service.py`
- [ ] T016 [P] [FR-4] 単体テスト: プロモーション0件時にカート作成が正常に完了することを確認する in `services/cart/tests/test_cart_service.py`
- [ ] T017 [FR-1] [FR-2] 統合テスト: カート作成→商品登録→精算の一連フローでプロモーションが正しく適用されることを確認する in `services/cart/tests/test_category_promo.py`

**Checkpoint**: 全テスト通過。機能要件FR-1〜FR-4の受入条件を満たしていることを確認。

---

## Phase 4: 仕上げ

**Purpose**: ドキュメント更新と最終確認

- [ ] T018 [P] plan.md の「キャッシュ戦略」設計決定を「実装済み」に更新する in `specs/71-promotion-cache/plan.md`
- [ ] T019 全テストスイートを実行し、既存機能へのリグレッションがないことを確認する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (データモデル・I/F変更)**: 依存なし — 即時開始可能
- **Phase 2 (コア実装)**: Phase 1 の完了が必須
- **Phase 3 (テスト)**: Phase 2 の完了が必須
- **Phase 4 (仕上げ)**: Phase 3 の完了が必須

### Within Each Phase

```
Phase 1:
  T001 (cart_document.py) ─┐
  T002 (abstract_sales_promo.py) ──── 並行実行可能
  T003 (cart_repository.py) ← T001 に依存

Phase 2:
  T004 (cart_service.py __init__) ─→ T005 ─→ T006 ─→ T007  （順序依存）
  T008 (category_promo.py) ← T002 に依存 ──┐
  T009 (sales_promo_sample.py) ← T002 に依存 ── 並行実行可能

Phase 3:
  T010, T011, T012 ── 既存テスト修正（並行可能）
  T013〜T016 ── 新規単体テスト（並行可能）
  T017 ── 統合テスト（上記完了後）
```

### Parallel Opportunities

```
# Phase 1: T001 と T002 は並行実行可能
Task: "T001 ReferenceMasters に promotions フィールド追加"
Task: "T002 AbstractSalesPromo.apply() シグネチャ変更"

# Phase 2: T008 と T009 は並行実行可能
Task: "T008 CategoryPromoPlugin 変更"
Task: "T009 SalesPromoSample シグネチャ合わせ"

# Phase 3: T010〜T016 はすべて並行実行可能
Task: "T010 既存 CategoryPromoPlugin テスト修正"
Task: "T011 既存カテゴリプロモーション統合テスト修正"
Task: "T012 既存 cart_service テスト修正"
Task: "T013 ReferenceMasters 格納テスト"
Task: "T014 CategoryPromoPlugin プロモーション使用テスト"
Task: "T015 取得失敗時エラーテスト"
Task: "T016 プロモーション0件テスト"
```

---

## Implementation Strategy

### MVP (Phase 1 + Phase 2)

1. Phase 1 完了 → データモデルとI/Fの基盤整備
2. Phase 2 完了 → **機能として動作可能**
3. この時点で手動検証可能（カート作成→商品登録→プロモーション適用確認）

### Full Delivery

1. Phase 1 + Phase 2 → 機能実装完了
2. Phase 3 → テスト網羅・品質保証
3. Phase 4 → ドキュメント更新・最終確認

---

## Summary

| 指標 | 値 |
|------|-----|
| 総タスク数 | 19 |
| Phase 1 (データモデル・I/F) | 3 タスク |
| Phase 2 (コア実装) | 6 タスク |
| Phase 3 (テスト) | 8 タスク |
| Phase 4 (仕上げ) | 2 タスク |
| 並行実行可能タスク | 12 タスク (63%) |
| 変更ファイル数 | 6 ソースファイル + 3 テストファイル |

## Notes

- [P] タスク = 異なるファイル、依存なし
- [FR] ラベルは対応する機能要件へのトレーサビリティ
- 各フェーズ完了後にチェックポイントで検証
- タスク完了ごと、または論理グループごとにコミット
