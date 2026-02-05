# 実装タスク一覧

## 概要

カテゴリプロモーション機能の実装タスクを詳細化したもの。

## タスク一覧

### Phase 2-1: 基盤整備

#### Task 1: DiscountInfo拡張

**サービス**: commons
**ファイル**: `services/commons/src/kugel_common/models/documents/base_tranlog.py`
**優先度**: 高
**依存**: なし

**内容**:
- `DiscountInfo` クラスに以下のフィールドを追加:
  - `promotion_code: Optional[str] = None`
  - `promotion_type: Optional[str] = None`
- 後方互換性を維持（既存フィールドは変更しない）

**受入条件**:
- [x] 新規フィールドが追加されている
- [x] 既存のテストが通る
- [x] 型ヒントが正しい

---

#### Task 2: PromotionMasterDocument作成

**サービス**: master-data
**ファイル**: `services/master-data/app/models/documents/promotion_master_document.py`
**優先度**: 高
**依存**: なし

**内容**:
- `PromotionMasterDocument` クラスを作成
- `CategoryPromoDetail` ネストクラスを作成
- AbstractDocumentを継承

**受入条件**:
- [x] 全フィールドが定義されている
- [x] バリデーションルールが適用されている
- [x] 型ヒントが正しい

---

#### Task 3: APIスキーマ作成

**サービス**: master-data
**ファイル**:
- `services/master-data/app/api/common/schemas.py`
- `services/master-data/app/api/v1/schemas.py`

**優先度**: 高
**依存**: Task 2

**内容**:
- リクエスト/レスポンススキーマを作成
  - `PromotionCreateRequest`
  - `PromotionUpdateRequest`
  - `PromotionResponse`
  - `PromotionDeleteResponse`
  - `CategoryPromoDetail`

**受入条件**:
- [x] 全スキーマが定義されている
- [x] camelCase/snake_case変換が設定されている
- [x] バリデーションルールが設定されている

---

### Phase 2-2: master-data 実装

#### Task 4: PromotionMasterRepository作成

**サービス**: master-data
**ファイル**: `services/master-data/app/models/repositories/promotion_master_repository.py`
**優先度**: 高
**依存**: Task 2

**内容**:
- AbstractRepositoryを継承
- 以下のメソッドを実装:
  - `create_promotion_async`
  - `get_promotion_by_code_async`
  - `get_promotions_by_filter_async`
  - `get_promotions_by_filter_paginated_async`
  - `get_active_promotions_async`
  - `get_active_promotions_by_category_async`
  - `get_active_promotions_by_store_async` # 店舗コードでフィルタ
  - `update_promotion_async`
  - `delete_promotion_async`

**受入条件**:
- [x] 全メソッドが実装されている
- [x] 有効プロモーション取得のクエリが正しい
- [x] エラーハンドリングが適切

---

#### Task 5: PromotionMasterService作成

**サービス**: master-data
**ファイル**: `services/master-data/app/services/promotion_master_service.py`
**優先度**: 高
**依存**: Task 4

**内容**:
- ビジネスロジックを実装
  - プロモーションコード重複チェック
  - 日付範囲バリデーション
  - 割引率バリデーション
- Repositoryを呼び出し

**受入条件**:
- [x] 全メソッドが実装されている
- [x] バリデーションが適切
- [x] 例外処理が適切

---

#### Task 6: APIエンドポイント作成

**サービス**: master-data
**ファイル**: `services/master-data/app/api/v1/promotion_master.py`
**優先度**: 高
**依存**: Task 3, Task 5

**内容**:
- FastAPI routerを作成
- 以下のエンドポイントを実装:
  - `POST /promotions`
  - `GET /promotions`
  - `GET /promotions/active`
  - `GET /promotions/{promotion_code}`
  - `PUT /promotions/{promotion_code}`
  - `DELETE /promotions/{promotion_code}`

**受入条件**:
- [x] 全エンドポイントが実装されている
- [x] OpenAPI仕様が正しい
- [x] エラーレスポンスが適切

---

#### Task 7: ルーター登録

**サービス**: master-data
**ファイル**: `services/master-data/app/main.py`
**優先度**: 高
**依存**: Task 6

**内容**:
- promotion_masterルーターをインポート
- app.include_router()で登録

**受入条件**:
- [x] ルーターが登録されている
- [x] /docsでエンドポイントが確認できる

---

#### Task 8: データベースインデックス作成

**サービス**: master-data
**ファイル**: `services/master-data/app/database/database_setup.py`
**優先度**: 中
**依存**: Task 2

**内容**:
- `create_master_promotion_collection` 関数を作成
- 必要なインデックスを定義
- `setup_database` から呼び出し

**受入条件**:
- [x] インデックスが作成される
- [x] 重複チェック用のユニークインデックスが設定されている

---

#### Task 9: プロモーションマスタ単体テスト

**サービス**: master-data
**ファイル**: `services/master-data/tests/test_promotion_master.py`
**優先度**: 高
**依存**: Task 6

**内容**:
- CRUD操作のテスト
- バリデーションエラーのテスト
- 有効プロモーション取得のテスト

**受入条件**:
- [ ] 全エンドポイントのテストがある
- [ ] 正常系・異常系のテストがある
- [ ] テストがパスする

---

### Phase 2-3: cart 実装

#### Task 10: CategoryPromoPlugin作成

**サービス**: cart
**ファイル**: `services/cart/app/services/strategies/sales_promo/category_promo.py`
**優先度**: 高
**依存**: Task 1, Task 6

**内容**:
- AbstractSalesPromoを継承
- `apply` メソッドを実装:
  - master-dataから有効プロモーションを取得（店舗コード指定）
  - 現在の店舗がプロモーション対象かを確認（target_store_codes）
  - 各line_itemのcategory_codeをチェック
  - 一致するプロモーションを適用（最大割引率を選択）
  - is_discount_restrictedをチェック
  - DiscountInfoにpromotion_code, promotion_typeを設定

**受入条件**:
- [ ] プロモーション適用ロジックが正しい
- [ ] 店舗指定が正しく動作する（指定店舗のみ、または全店舗）
- [ ] 最安値選択が正しく動作する
- [ ] 割引制限が尊重される

---

#### Task 11: プラグイン登録

**サービス**: cart
**ファイル**: `services/cart/app/services/strategies/plugins.json`
**優先度**: 高
**依存**: Task 10

**内容**:
- CategoryPromoPluginを登録

```json
{
  "sales_promo_strategies": [
    {
      "module": "app.services.strategies.sales_promo.category_promo",
      "class": "CategoryPromoPlugin",
      "args": ["category_promo"],
      "kwargs": {}
    }
  ]
}
```

**受入条件**:
- [ ] プラグインが登録されている
- [ ] サービス起動時にエラーが出ない

---

#### Task 12: プラグイン呼び出し実装

**サービス**: cart
**ファイル**: `services/cart/app/services/cart_service.py`
**優先度**: 高
**依存**: Task 10, Task 11

**内容**:
- `add_items_to_cart_async` メソッド内で:
  - アイテム追加後、小計計算前に
  - 各sales_promo_strategyの`apply`を呼び出し

**受入条件**:
- [ ] プラグインが呼び出される
- [ ] 正しいタイミングで実行される
- [ ] エラーハンドリングが適切

---

#### Task 13: 取引ログへのプロモーション情報記録

**サービス**: cart
**ファイル**: `services/cart/app/services/tran_service.py`
**優先度**: 高
**依存**: Task 1, Task 12

**内容**:
- CartDocumentからTransactionLogへの変換時に
- line_item.discountsのpromotion_code, promotion_typeを保持

**受入条件**:
- [ ] プロモーション情報が取引ログに記録される
- [ ] 実績集計で使用可能

---

#### Task 14: プロモーション適用統合テスト

**サービス**: cart
**ファイル**: `services/cart/tests/test_category_promo.py`
**優先度**: 高
**依存**: Task 12

**内容**:
- プロモーション適用の統合テスト
- 店舗指定プロモーションテスト（対象店舗のみ適用）
- 全店舗対象プロモーションテスト
- 複数プロモーション時の最安値選択テスト
- 割引制限テスト
- 期限切れプロモーションテスト

**受入条件**:
- [ ] 全シナリオのテストがある
- [ ] テストがパスする

---

### Phase 2-4: report 実装

#### Task 15: プロモーション実績集計プラグイン作成

**サービス**: report
**ファイル**: `services/report/app/services/plugins/promotion_report_maker.py`
**優先度**: 中
**依存**: Task 13

**内容**:
- プロモーション実績集計ロジックを実装
- MongoDB Aggregation Pipelineを使用
- promotion_codeでグループ化

**受入条件**:
- [ ] 集計ロジックが正しい
- [ ] パフォーマンスが適切

---

#### Task 16: 実績集計テスト

**サービス**: report
**ファイル**: `services/report/tests/test_promotion_report.py`
**優先度**: 中
**依存**: Task 15

**内容**:
- 実績集計のテスト
- 期間指定フィルタのテスト
- 集計結果の正確性テスト

**受入条件**:
- [ ] テストがパスする
- [ ] 集計結果が正確

---

## 依存関係図

```
Task 1 (commons: DiscountInfo拡張)
    │
    ├──────────────────────────────────┐
    │                                  │
Task 2 (master-data: Document)         │
    │                                  │
    ├── Task 3 (Schemas)               │
    │       │                          │
    ├── Task 4 (Repository)            │
    │       │                          │
    │       └── Task 5 (Service)       │
    │               │                  │
    │               └── Task 6 (API) ──┤
    │                       │          │
    │                       ├── Task 7 (Router)
    │                       │          │
    │                       └── Task 9 (Test)
    │                                  │
    └── Task 8 (Index)                 │
                                       │
Task 10 (cart: Plugin) ────────────────┘
    │
    ├── Task 11 (Plugin登録)
    │       │
    │       └── Task 12 (呼び出し)
    │               │
    │               ├── Task 13 (取引ログ)
    │               │       │
    │               │       └── Task 15 (report集計)
    │               │               │
    │               │               └── Task 16 (Test)
    │               │
    │               └── Task 14 (Test)
```

## 見積もり

| Phase | タスク数 | 概算工数 |
|-------|---------|---------|
| Phase 2-1 | 3 | 基盤整備 |
| Phase 2-2 | 6 | master-data実装 |
| Phase 2-3 | 5 | cart実装 |
| Phase 2-4 | 2 | report実装 |
| **合計** | **16** | - |
