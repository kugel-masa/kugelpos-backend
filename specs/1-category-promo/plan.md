# カテゴリプロモーション機能 実装計画

## 概要

本ドキュメントは、カテゴリプロモーション機能の実装計画を記述する。
[spec.md](./spec.md) の機能要件に基づき、技術的な設計と実装タスクを定義する。

## 技術コンテキスト

### 既存アーキテクチャ

| コンポーネント | 技術 | 説明 |
|---------------|------|------|
| master-data サービス | FastAPI + MongoDB | プロモーションマスタを新規追加 |
| cart サービス | FastAPI + MongoDB | プロモーション適用ロジックを実装 |
| journal サービス | FastAPI + MongoDB | 取引ログにプロモーションコードを記録 |
| report サービス | FastAPI + MongoDB | プロモーション実績集計を実装 |
| commons ライブラリ | Python | 共通スキーマ・ドキュメントを拡張 |

### 関連する既存コード

| ファイル | 説明 |
|---------|------|
| `services/master-data/app/models/documents/category_master_document.py` | カテゴリマスタ（参照） |
| `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | プロモーションプラグイン基底クラス |
| `services/cart/app/services/strategies/plugins.json` | プラグイン設定 |
| `services/cart/app/services/cart_service.py` | カートサービス（プラグイン呼び出し追加） |
| `services/commons/src/kugel_common/models/documents/base_tranlog.py` | 取引ログ基底クラス（割引情報） |

### 依存関係

- カテゴリマスタ（master-data）: 存在確認済み
- 商品マスタ（master-data）: category_codeフィールド存在確認済み
- sales_promoプラグイン構造（cart）: 存在確認済み、未使用
- 取引ログ構造（commons）: DiscountInfo クラス存在確認済み

## フェーズ0: 調査・設計

### 調査項目

| 項目 | 結果 |
|------|------|
| プラグイン呼び出しタイミング | `__subtotal_async` 内、2フェーズモデル（line_item→小計計算→subtotal→再計算）。プラグインは `execution_phase` プロパティで実行フェーズを自己宣言する |
| 既存DiscountInfo構造 | seq_no, discount_type, discount_value, discount_amount, detail |
| プロモーション情報の追加方法 | DiscountInfo.detailにpromotion_codeを格納、または新規フィールド追加 |
| master-data → cart 通信 | DaprClientHelper経由のHTTP呼び出し |

### 設計決定

| 決定事項 | 選択 | 理由 |
|---------|------|------|
| プロモーションマスタの配置 | master-dataサービス | 他のマスタデータと統一 |
| プロモーションタイプの実装 | promotion_typeフィールド | 将来の拡張に対応 |
| カテゴリ詳細の格納方法 | 同一ドキュメント内にネスト | シンプルさ優先、タイプ別コレクションは将来検討 |
| DiscountInfoの拡張 | promotion_code, promotion_typeフィールド追加 | 実績集計に必要 |
| キャッシュ戦略 | 初期リリースではキャッシュなし | パフォーマンス問題発生時に追加 |
| プラグイン実行フェーズ | `execution_phase` プロパティによる自己宣言（B案） | 新規プラグイン追加時にベースコード修正不要。デフォルト `"line_item"`（小計前）、`"subtotal"`（小計後）の2フェーズ。subtotalフェーズのプラグインがない場合は第2パスをスキップ |

## フェーズ1: データモデル設計

詳細は [data-model.md](./data-model.md) を参照。

### 新規エンティティ

1. **PromotionMasterDocument** (master-data)
   - 汎用プロモーション属性 + カテゴリ詳細

2. **DiscountInfo拡張** (commons)
   - promotion_code, promotion_type フィールド追加

### API設計

詳細は [contracts/](./contracts/) を参照。

## フェーズ2: 実装タスク

### タスク一覧

| # | サービス | タスク | 依存 | 優先度 |
|---|---------|--------|------|--------|
| 1 | commons | DiscountInfoにpromotion_code, promotion_typeフィールド追加 | - | 高 |
| 2 | master-data | PromotionMasterDocument作成 | - | 高 |
| 3 | master-data | PromotionMasterRepository作成 | 2 | 高 |
| 4 | master-data | PromotionMasterService作成 | 3 | 高 |
| 5 | master-data | プロモーションAPIスキーマ作成 | 2 | 高 |
| 6 | master-data | プロモーションAPIエンドポイント作成 | 4, 5 | 高 |
| 7 | master-data | main.pyにルーター登録 | 6 | 高 |
| 8 | master-data | データベースインデックス作成 | 2 | 中 |
| 9 | cart | CategoryPromoPlugin作成 | 1, 6 | 高 |
| 10 | cart | plugins.jsonにプラグイン登録 | 9 | 高 |
| 11 | cart | CartServiceでプラグイン呼び出し実装 | 9, 10 | 高 |
| 12 | cart | 取引ログへのプロモーション情報記録 | 1, 11 | 高 |
| 13 | report | プロモーション実績集計プラグイン作成 | 12 | 中 |
| 14 | master-data | プロモーションマスタ単体テスト | 6 | 高 |
| 15 | cart | プロモーション適用統合テスト | 11 | 高 |
| 16 | report | 実績集計テスト | 13 | 中 |

### 実装順序

```
Phase 2-1: 基盤整備
├── Task 1: DiscountInfo拡張 (commons)
├── Task 2: PromotionMasterDocument (master-data)
└── Task 5: APIスキーマ (master-data)

Phase 2-2: master-data 実装
├── Task 3: Repository
├── Task 4: Service
├── Task 6: API エンドポイント
├── Task 7: ルーター登録
├── Task 8: インデックス
└── Task 14: 単体テスト

Phase 2-3: cart 実装
├── Task 9: CategoryPromoPlugin
├── Task 10: プラグイン登録
├── Task 11: プラグイン呼び出し
├── Task 12: 取引ログ記録
└── Task 15: 統合テスト

Phase 2-4: report 実装
├── Task 13: 実績集計プラグイン
└── Task 16: 集計テスト
```

## 成果物一覧

| ファイル | 説明 |
|---------|------|
| `specs/1-category-promo/spec.md` | 機能仕様書 |
| `specs/1-category-promo/spec_review.md` | レビュー記録 |
| `specs/1-category-promo/plan.md` | 実装計画（本ファイル） |
| `specs/1-category-promo/data-model.md` | データモデル設計 |
| `specs/1-category-promo/contracts/` | API契約 |
| `specs/1-category-promo/tasks.md` | 詳細タスク一覧 |
| `specs/1-category-promo/checklists/requirements.md` | 仕様品質チェックリスト |

## リスクと軽減策

| リスク | 影響 | 軽減策 |
|--------|------|--------|
| sales_promoプラグインの呼び出し箇所が不明確 | 実装遅延 | cart_service.pyを詳細調査し、適切な挿入ポイントを特定 |
| DiscountInfo変更の影響範囲 | 既存機能への影響 | 後方互換性を維持（新規フィールドはOptional） |
| パフォーマンス劣化 | ユーザー体験低下 | 負荷テスト実施、必要に応じてキャッシュ導入 |

## 次のステップ

1. `data-model.md` の作成
2. `contracts/` のAPI定義作成
3. `tasks.md` の詳細タスク作成
4. 実装開始
