# プロモーションマスタ キャッシュ改善 実装計画

## 概要

本ドキュメントは、プロモーションマスタのカートドキュメント埋め込みによるキャッシュ改善の実装計画を記述する。
[spec.md](./spec.md) の機能要件に基づき、技術的な設計と実装タスクを定義する。

## 技術コンテキスト

### 既存アーキテクチャ

| コンポーネント | 技術 | 説明 |
|---------------|------|------|
| cart サービス | FastAPI + Dapr State | プロモーション取得タイミングの変更、ReferenceMasters拡張 |
| master-data サービス | FastAPI + MongoDB | プロモーションマスタAPI（変更なし） |

### 関連する既存コード

| ファイル | 説明 |
|---------|------|
| `services/cart/app/models/documents/cart_document.py` | CartDocument / ReferenceMasters定義 |
| `services/cart/app/models/repositories/cart_repository.py` | カートの作成・キャッシュ処理 |
| `services/cart/app/services/cart_service.py` | カート作成、プロモーション適用のオーケストレーション |
| `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | プロモーションプラグイン基底クラス |
| `services/cart/app/services/strategies/sales_promo/category_promo.py` | カテゴリプロモーションプラグイン |
| `services/cart/app/models/repositories/promotion_master_web_repository.py` | master-data API呼び出しリポジトリ |
| `services/cart/app/models/documents/promotion_master_document.py` | プロモーションマスタドキュメントモデル |

### 依存関係

- ReferenceMastersパターン（cart）: items, taxes, settingsで確立済み
- PromotionMasterWebRepository（cart）: 存在確認済み、呼び出し元を変更
- PromotionMasterDocument（cart）: 存在確認済み、変更不要
- master-data プロモーションAPI: 存在確認済み、変更不要

## フェーズ0: 調査・設計

### 調査項目

| 項目 | 結果 |
|------|------|
| ReferenceMastersの既存パターン | カート作成時に `settings_master`, `tax_master`, `item_master` を取得・埋め込み。`item_master` は商品追加時に随時更新される |
| カート作成フロー | `create_cart_async()` 内で各マスタを順次取得し、`cart_repo.create_cart_async()` に渡す。失敗時は `CartCannotCreateException` |
| プラグイン呼び出しI/F | `AbstractSalesPromo.apply(cart_doc)` → `CartDocument` を返す。`_apply_sales_promotions_async()` がフェーズ別にプラグインを呼び出し |
| CategoryPromoPluginのデータ取得 | `apply()` 内で毎回 `promotion_master_repo.get_active_promotions_by_store_async()` を呼び出し |
| エラーハンドリング方針 | 現状: プロモーション取得失敗時は空リストで続行。改善後: カート作成失敗とする |

### 設計決定

| 決定事項 | 選択 | 理由 |
|---------|------|------|
| キャッシュ方式 | ReferenceMasters埋め込み | 税マスタ・設定マスタと同じ確立済みパターン。取引内の一貫性を保証 |
| 取得タイミング | カート作成時（1回） | 取引開始時点のプロモーション条件で全商品の売価を統一 |
| TTLキャッシュ | 不採用 | TTL満了タイミングで取引途中にデータが変わるリスクがある |
| プロモーション取得失敗時 | カート作成失敗 | 空リストで続行すると顧客に割引が適用されず不利益が発生する |
| プラグインI/F変更 | `apply(cart_doc, promotions)` | プラグインがリポジトリを直接保持する必要がなくなり、責務が明確化 |
| `promotions` パラメータ | Optional（デフォルト: None） | 後方互換性を維持。将来プラグインが独自取得する選択肢も残す |

## フェーズ1: データモデル設計

### 変更エンティティ

#### 1. ReferenceMasters（cart_document.py）

| フィールド | 型 | 変更 |
|-----------|-----|------|
| items | `Optional[list[ItemMasterDocument]]` | 既存 |
| taxes | `Optional[list[TaxMasterDocument]]` | 既存 |
| settings | `Optional[list[SettingsMasterDocument]]` | 既存 |
| **promotions** | **`Optional[list[PromotionMasterDocument]]`** | **追加** |

デフォルト値: `[]`（空リスト）— 改善前に作成された既存カートドキュメントとの後方互換性を維持。

#### 2. AbstractSalesPromo.apply()（abstract_sales_promo.py）

```python
# 変更前
@abstractmethod
async def apply(self, cart_doc) -> CartDocument:

# 変更後
@abstractmethod
async def apply(self, cart_doc, promotions: list = None) -> CartDocument:
```

### API設計

API変更なし。master-dataサービスの既存エンドポイントをそのまま使用する。

| エンドポイント | 変更 |
|--------------|------|
| `GET /tenants/{tenant_id}/promotions/active` | 変更なし（呼び出し元が変わるのみ） |

## フェーズ2: 実装タスク

### タスク一覧

| # | ファイル | タスク | 依存 | 優先度 |
|---|---------|--------|------|--------|
| 1 | `cart_document.py` | ReferenceMasters に `promotions` フィールド追加、import追加 | - | 高 |
| 2 | `cart_repository.py` | `create_cart_async` に `promotion_master` パラメータ追加、格納処理追加 | 1 | 高 |
| 3 | `cart_service.py` | `create_cart_async` にプロモーション取得処理追加、`PromotionMasterWebRepository` のインスタンス化をサービス側に移動 | 2 | 高 |
| 4 | `cart_service.py` | プロモーション取得失敗時の例外ハンドリング追加 | 3 | 高 |
| 5 | `abstract_sales_promo.py` | `apply()` シグネチャに `promotions` パラメータ追加 | - | 高 |
| 6 | `category_promo.py` | 渡された `promotions` を使用するよう変更。リポジトリ依存を削除 | 5 | 高 |
| 7 | `cart_service.py` | `_apply_sales_promotions_async()` で `cart_doc.masters.promotions` を `apply()` に渡す | 5, 6 | 高 |
| 8 | `sales_promo_sample.py` | `apply()` シグネチャ合わせ（存在する場合） | 5 | 低 |
| 9 | テストファイル | 単体テスト: ReferenceMasters.promotions格納確認 | 1 | 高 |
| 10 | テストファイル | 単体テスト: CategoryPromoPlugin.apply()が渡されたpromotionsを使用する確認 | 6 | 高 |
| 11 | テストファイル | 単体テスト: プロモーション取得失敗時のカート作成エラー確認 | 4 | 高 |
| 12 | テストファイル | 単体テスト: プロモーション0件時の正常動作確認 | 3 | 中 |
| 13 | テストファイル | 統合テスト: カート作成→商品登録→精算の一連フロー確認 | 7 | 高 |

### 実装順序

```
Phase 2-1: データモデル・I/F変更
├── Task 1: ReferenceMasters 拡張 (cart_document.py)
├── Task 2: cart_repository.py パラメータ追加
└── Task 5: AbstractSalesPromo.apply() シグネチャ変更

Phase 2-2: コア実装
├── Task 3: cart_service.py プロモーション取得追加
├── Task 4: エラーハンドリング追加
├── Task 6: CategoryPromoPlugin 変更
├── Task 7: _apply_sales_promotions_async() 受け渡し
└── Task 8: SalesPromoSample シグネチャ合わせ

Phase 2-3: テスト
├── Task 9:  ReferenceMasters 単体テスト
├── Task 10: CategoryPromoPlugin 単体テスト
├── Task 11: エラーハンドリング 単体テスト
├── Task 12: プロモーション0件 単体テスト
└── Task 13: 統合テスト
```

## 成果物一覧

| ファイル | 説明 |
|---------|------|
| `specs/71-promotion-cache/spec.md` | 機能仕様書 |
| `specs/71-promotion-cache/plan.md` | 実装計画（本ファイル） |

## リスクと軽減策

| リスク | 影響 | 軽減策 |
|--------|------|--------|
| `apply()` シグネチャ変更の既存プラグインへの影響 | 既存プラグインのビルドエラー | `promotions` をOptionalとし後方互換性維持。全プラグインを同時に更新 |
| プロモーション取得失敗でカート作成が不安定化 | 取引開始不可 | master-dataサービスの可用性監視強化。エラーメッセージで原因を明示しリトライ可能に |
| カートドキュメントサイズの増加 | キャッシュ・通信のオーバーヘッド | プロモーション情報は数KB程度であり影響は軽微 |
| 既存テストへの影響 | テスト失敗 | Phase 2-3 で全テストを修正・追加 |

## 次のステップ

1. 仕様書（spec.md）のクライアント承認
2. Phase 2-1 から実装開始
3. Phase 2-3 でテスト追加・既存テスト修正
4. 統合テスト実施
