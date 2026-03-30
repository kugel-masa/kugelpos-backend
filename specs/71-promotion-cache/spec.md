# プロモーションマスタ キャッシュ改善 仕様書

| 項目 | 内容 |
|------|------|
| ドキュメントID | SPEC-002 |
| 関連Issue | #71 |
| 対象サービス | cart |
| 関連サービス | master-data |
| ステータス | レビュー待ち |
| 作成日 | 2026-03-30 |

## 1. 概要

カートサービスのプロモーションプラグイン（CategoryPromoPlugin）において、商品登録などのカート操作のたびにmaster-dataサービスからプロモーションマスタ情報をHTTP取得している現状を改善する。

カート作成時（取引開始時）に1回だけプロモーションマスタを取得し、カートドキュメントに埋め込むことで、パフォーマンスの向上と取引内の価格一貫性を実現する。

## 2. 背景と課題

### 2.1 現状の動作

```
商品登録 → __subtotal_async() → CategoryPromoPlugin.apply()
                                   → master-data API呼び出し（毎回）
                                     GET /tenants/{id}/promotions/active
```

カート操作のたびに `_apply_sales_promotions_async()` が呼び出され、プラグイン内部で毎回master-dataサービスへHTTPリクエストが発生する。

### 2.2 影響を受ける操作

| 操作 | メソッド | API呼び出し |
|------|---------|------------|
| 商品登録 | `add_item_to_cart_async` | 1回/操作 |
| 数量変更 | `update_line_item_quantity_in_cart_async` | 1回/操作 |
| 単価変更 | `update_line_item_unit_price_in_cart_async` | 1回/操作 |
| 明細取消 | `cancel_line_item_from_cart_async` | 1回/操作 |
| 明細割引追加 | `add_discount_to_line_item_in_cart_async` | 1回/操作 |
| 小計 | `subtotal_async` | 1回/操作 |
| カート割引追加 | `add_discount_to_cart_async` | 1回/操作 |
| 支払追加 | `add_payment_to_cart_async` | 1回/操作 |
| 精算 | `bill_async` | 1回/操作 |
| 商品入力再開 | `resume_item_entry_async` | 1回/操作 |

### 2.3 問題点

| 問題 | 説明 |
|------|------|
| **パフォーマンス** | 10商品の一般的な取引で約15回のHTTP APIリクエストが発生。同一パラメータで同じデータを繰り返し取得している |
| **レスポンスのばらつき** | API呼び出しの有無により、商品登録ごとのレスポンスタイムに差が生じる |
| **価格一貫性** | 取引途中でプロモーションマスタが変更された場合、同一取引内で異なるプロモーション条件が適用される可能性がある |

## 3. 改善方針

### 3.1 設計コンセプト

税マスタ・設定マスタと同様に、プロモーションマスタを `ReferenceMasters` に埋め込む。
既に `ReferenceMasters` は商品マスタ（`items`）、税マスタ（`taxes`）、設定マスタ（`settings`）を保持しており、同じパターンを踏襲する。

```
カート作成時:
  create_cart_async()
    ├─ store_info_repo.get_store_info_async()             ← 既存
    ├─ settings_master_repo.get_all_settings_async()      ← 既存
    ├─ tax_master_repo.load_all_taxes()                   ← 既存
    ├─ promotion_master_repo.get_active_promotions_...()  ← 追加（1回のみ）
    └─ cart_repo.create_cart_async(..., promotion_master)  ← 追加
         └─ cart.masters.promotions = promotion_master     ← 埋め込み
```

```
商品登録時:
  add_item_to_cart_async()
    └─ __subtotal_async()
         └─ _apply_sales_promotions_async()
              └─ strategy.apply(cart_doc)
                   └─ cart_doc.masters.promotions を参照（API呼び出しなし）
```

### 3.2 取得タイミングの根拠

| 選択肢 | 採否 | 理由 |
|--------|------|------|
| カート作成時に1回取得 | **採用** | 取引開始時点のプロモーション条件で全商品の売価を決定する。税マスタ・設定マスタと同じ考え方 |
| 商品登録ごとに取得（現状） | 不採用 | パフォーマンス問題および取引内の価格一貫性が保証されない |
| TTLベースのインメモリキャッシュ | 不採用 | TTL満了タイミングで取引途中に異なるプロモーション条件が適用される可能性がある |

## 4. 機能要件

### FR-1: プロモーションマスタのカート埋め込み

| ID | 要件 | 受入条件 |
|----|------|----------|
| FR-1.1 | `ReferenceMasters` に `promotions` フィールドを追加する | `PromotionMasterDocument` のリストを保持できる |
| FR-1.2 | カート作成時にmaster-dataサービスから有効なプロモーションマスタを取得する | `create_cart_async` 内で1回だけAPI呼び出しが行われる |
| FR-1.3 | 取得したプロモーションマスタを `cart.masters.promotions` に格納する | カートドキュメントにプロモーション情報が永続化される |

### FR-2: プラグインI/Fの変更

| ID | 要件 | 受入条件 |
|----|------|----------|
| FR-2.1 | `AbstractSalesPromo.apply()` のシグネチャに `promotions` パラメータを追加する | 既存プラグインが `promotions` を受け取れる |
| FR-2.2 | `_apply_sales_promotions_async()` が `cart_doc.masters.promotions` を取り出し、`apply(cart_doc, promotions)` の引数として渡す | プラグインが独自にAPI呼び出しを行わない |
| FR-2.3 | `CategoryPromoPlugin` が渡されたプロモーション一覧を使用する | プラグイン内でのHTTP通信が発生しない |

### FR-3: エラーハンドリング

| ID | 要件 | 受入条件 |
|----|------|----------|
| FR-3.1 | プロモーションマスタの取得に失敗した場合、カート作成を失敗させる | `CartCannotCreateException` が送出される |
| FR-3.2 | プロモーション取得失敗時、空リストでの取引続行を**行わない** | 割引が適用されないまま取引が進行することがない |
| FR-3.3 | クライアント（レジ）はエラーを受けてリトライできる | カート作成の再実行で復旧可能 |

### FR-4: 後方互換性

| ID | 要件 | 受入条件 |
|----|------|----------|
| FR-4.1 | `promotions` フィールドはOptional（デフォルト: 空リスト）とする | 改善前に作成された既存カートドキュメントが正常に読み込める |
| FR-4.2 | プロモーションが0件の環境でもカート作成が成功する | 有効なプロモーションが存在しない場合、空リストで正常に動作する |

## 5. 変更対象

### 5.1 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `cart/app/models/documents/cart_document.py` | `ReferenceMasters` に `promotions` フィールド追加 |
| `cart/app/models/repositories/cart_repository.py` | `create_cart_async` に `promotion_master` パラメータ追加 |
| `cart/app/services/cart_service.py` | `create_cart_async` でプロモーション取得、`_apply_sales_promotions_async` でプロモーション受け渡し |
| `cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | `apply()` シグネチャ変更 |
| `cart/app/services/strategies/sales_promo/category_promo.py` | 渡されたプロモーション使用、リポジトリ依存の削除 |
| `cart/app/services/strategies/sales_promo/sales_promo_sample.py` | `apply()` シグネチャ合わせ（存在する場合） |
| 関連テストファイル | 上記変更に伴うテスト修正 |

### 5.2 変更しないもの

| 対象 | 理由 |
|------|------|
| master-dataサービスのプロモーションAPI | エンドポイント・レスポンス形式に変更なし |
| `PromotionMasterDocument` | ドキュメントモデル自体に変更なし |
| `PromotionMasterWebRepository` | cartサービス内で引き続き使用（呼び出し元が変わるのみ） |
| プロモーションの適用ロジック（最安値選択等） | ビジネスロジックに変更なし |

## 6. データモデル変更

### 6.1 ReferenceMasters（変更後）

```python
class ReferenceMasters(BaseDocumentModel):
    items: Optional[list[ItemMasterDocument]] = []
    taxes: Optional[list[TaxMasterDocument]] = []
    settings: Optional[list[SettingsMasterDocument]] = []
    promotions: Optional[list[PromotionMasterDocument]] = []  # 追加
```

### 6.2 カートドキュメント（JSON表現）

```json
{
  "cart_id": "...",
  "status": "Idle",
  "masters": {
    "items": [...],
    "taxes": [...],
    "settings": [...],
    "promotions": [
      {
        "promotion_code": "PROMO001",
        "promotion_type": "category_discount",
        "name": "飲料10%OFF",
        "start_datetime": "2026-03-01T00:00:00",
        "end_datetime": "2026-04-30T23:59:59",
        "is_active": true,
        "detail": {
          "targetCategoryCodes": ["BEV"],
          "discountRate": 10.0
        }
      }
    ]
  },
  "line_items": [...]
}
```

## 7. 処理フロー

### 7.1 カート作成（変更後）

```
クライアント → POST /cart/create
                 │
                 ▼
           create_cart_async()
                 │
                 ├─ ターミナル状態チェック（既存）
                 ├─ スタッフサインインチェック（既存）
                 ├─ イベントシーケンスチェック（既存）
                 │
                 ├─ 店舗情報取得（既存）
                 ├─ 設定マスタ取得（既存）
                 ├─ 税マスタ取得（既存）
                 ├─ プロモーションマスタ取得 ←【追加】
                 │    ├─ 成功 → promotions に格納
                 │    └─ 失敗 → 例外送出 → カート作成失敗
                 │
                 ├─ cart_repo.create_cart_async(
                 │      ..., promotion_master=promotions)
                 │
                 └─ カートキャッシュ保存
```

### 7.2 商品登録時のプロモーション適用（変更後）

```
クライアント → POST /cart/add_item
                 │
                 ▼
           add_item_to_cart_async()
                 │
                 └─ __subtotal_async()
                      │
                      ├─ _apply_sales_promotions_async(cart_doc, "line_item")
                      │    │
                      │    └─ strategy.apply(cart_doc, cart_doc.masters.promotions)
                      │         │
                      │         └─ 埋め込みデータを参照（API呼び出しなし）
                      │
                      └─ calc_subtotal_async()
```

## 8. 前提条件

| # | 前提 |
|---|------|
| 1 | 同一取引内では、カート作成時点のプロモーション条件で全商品の売価を決定する |
| 2 | プロモーションマスタの変更は、次回のカート作成（新規取引）から反映される |
| 3 | 営業中にプロモーションマスタが変更されることは稀であり、取引途中の変更反映は不要とする |
| 4 | プロモーション情報のデータサイズは小さく（数KB程度）、カートドキュメントへの埋め込みによるストレージ影響は軽微である |

## 9. 期待される効果

| 指標 | 変更前 | 変更後 |
|------|--------|--------|
| 取引あたりのプロモーションAPI呼び出し回数 | ~15回 | **1回** |
| 取引内の価格一貫性 | 保証なし | **保証あり** |
| 商品登録時のレスポンスタイム | ばらつきあり（API遅延依存） | **均一** |
| カート作成時のレスポンスタイム | 微増（数十ms） | — |
| プロモーション変更の反映タイミング | 即時（次回操作時） | 次回取引開始時 |

## 10. リスクと対策

| リスク | 影響度 | 対策 |
|--------|--------|------|
| プロモーション取得失敗でカートが作成できない | 中 | エラーメッセージで原因を明示し、クライアント側でリトライを実装。master-dataサービスの可用性監視を強化 |
| 取引中にプロモーションが変更されても反映されない | 低 | 仕様として許容（前提条件3）。運用上、プロモーション変更は営業時間外が一般的 |
| カートドキュメントのサイズ増加 | 低 | プロモーション情報は軽量（数KB）。ストレージ・通信への影響は軽微 |
| `apply()` シグネチャ変更による既存プラグインへの影響 | 中 | `promotions` パラメータをOptional（デフォルト: None）とし、後方互換性を維持 |

## 11. Clarifications

### Session 2026-03-30

- Q: master-dataサービスの応答遅延時、プロモーション取得に個別タイムアウト設定は必要か → A: 不要。既存のHTTPクライアント共通タイムアウト（`get_pooled_client`）に従う

## 12. テスト方針

| テスト区分 | 内容 |
|-----------|------|
| 単体テスト | `ReferenceMasters` にプロモーションが格納されることの確認 |
| 単体テスト | `CategoryPromoPlugin.apply()` が渡されたプロモーションリストを使用することの確認 |
| 単体テスト | プロモーション取得失敗時にカート作成が例外を送出することの確認 |
| 単体テスト | プロモーション0件時にカート作成が正常に完了することの確認 |
| 統合テスト | カート作成→商品登録→精算の一連フローでプロモーションが正しく適用されることの確認 |
| 統合テスト | 取引途中でプロモーションマスタを変更しても、当該取引には影響しないことの確認 |
