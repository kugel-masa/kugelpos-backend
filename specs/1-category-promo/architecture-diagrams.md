# カテゴリプロモーション機能 アーキテクチャ図

## 1. システム全体構成図

```mermaid
flowchart TB
    subgraph Client["クライアント"]
        POS["POS端末"]
    end

    subgraph CartService["Cart Service :8003"]
        CartAPI["Cart API<br/>/api/v1/carts"]
        CartSvc["CartService"]
        CategoryPlugin["CategoryPromoPlugin"]
        PromoRepo["PromotionMasterWebRepository"]
    end

    subgraph MasterDataService["Master-Data Service :8002"]
        PromoAPI["Promotion API<br/>/api/v1/tenants/{id}/promotions"]
        PromoSvc["PromotionMasterService"]
        PromoDBRepo["PromotionMasterRepository"]
    end

    subgraph Database["MongoDB"]
        CartDB[("cart_db")]
        MasterDB[("master_db<br/>master_promotion")]
    end

    POS -->|"POST /carts/{id}/lineItems"| CartAPI
    CartAPI --> CartSvc
    CartSvc --> CategoryPlugin
    CategoryPlugin --> PromoRepo
    PromoRepo -->|"GET /promotions/active"| PromoAPI
    PromoAPI --> PromoSvc
    PromoSvc --> PromoDBRepo
    PromoDBRepo --> MasterDB
    CartSvc --> CartDB
```

## 2. プロモーション適用シーケンス図 (必須)

```mermaid
sequenceDiagram
    autonumber
    participant POS as POS端末
    participant CartAPI as Cart API
    participant CartSvc as CartService
    participant Plugin as CategoryPromoPlugin
    participant PromoRepo as PromotionMasterWebRepository
    participant MasterAPI as Master-Data API
    participant MongoDB as MongoDB

    POS->>+CartAPI: POST /carts/{cartId}/lineItems<br/>[itemCode, quantity]
    CartAPI->>+CartSvc: add_items_to_cart_async()

    Note over CartSvc: 0. プラグイン初期化（CartService構築時）
    CartSvc->>Plugin: configure(tenant_id, terminal_info)
    Plugin->>Plugin: PromotionMasterWebRepository生成

    Note over CartSvc: 1. 商品情報取得・明細追加
    CartSvc->>CartSvc: 商品マスタから情報取得
    CartSvc->>CartSvc: CartLineItem作成

    Note over CartSvc: 2. プロモーション適用
    CartSvc->>+Plugin: apply(cart_doc)

    Plugin->>+PromoRepo: get_active_promotions_by_store_async()

    alt キャッシュあり
        PromoRepo-->>Plugin: キャッシュされたプロモーション
    else キャッシュなし
        PromoRepo->>+MasterAPI: GET /promotions/active<br/>?storeCode={code}&terminal_id={id}
        MasterAPI->>+MongoDB: 有効プロモーション検索<br/>(is_active=true, 期間内)
        MongoDB-->>-MasterAPI: プロモーション一覧
        MasterAPI-->>-PromoRepo: Response [promotions]
        PromoRepo->>PromoRepo: キャッシュに保存
        PromoRepo-->>-Plugin: プロモーション一覧
    end

    Note over Plugin: 3. カテゴリ→プロモーションマップ構築
    Plugin->>Plugin: _build_category_promotion_map()
    Note right of Plugin: カテゴリごとに最高割引率を選択

    loop 各LineItemに対して
        Plugin->>Plugin: is_cancelled? → スキップ
        Plugin->>Plugin: is_discount_restricted? → スキップ
        Plugin->>Plugin: 既存のcategory_discount? → スキップ
        Plugin->>Plugin: カテゴリコードでプロモーション検索

        alt マッチするプロモーションあり
            Plugin->>Plugin: _apply_promotion_to_line_item()
            Note right of Plugin: DiscountInfo作成<br/>promotion_code設定<br/>promotion_type設定
        end
    end

    Plugin-->>-CartSvc: 更新されたcart_doc

    Note over CartSvc: 4. 小計・税計算
    CartSvc->>CartSvc: calculate_subtotal()
    CartSvc->>CartSvc: calculate_taxes()

    CartSvc-->>-CartAPI: CartDocument
    CartAPI-->>-POS: Response<br/>{lineItems: [{discounts: [...]}]}
```

## 3. クラス図

```mermaid
classDiagram
    class AbstractSalesPromo {
        <<abstract>>
        +configure(tenant_id, terminal_info)
        +apply(cart_doc, sales_promo_code, value) CartDocument
        +sales_promo_code() string
    }

    class CategoryPromoPlugin {
        -_sales_promo_code: string
        -promotion_master_repo: PromotionMasterWebRepository
        +configure(tenant_id, terminal_info)
        +apply(cart_doc) CartDocument
        -_build_category_promotion_map(promotions) dict
        -_has_category_promotion(line_item) bool
        -_apply_promotion_to_line_item(line_item, promo_info)
    }

    class PromotionMasterWebRepository {
        -tenant_id: string
        -terminal_info: TerminalInfoDocument
        -base_url: string
        -_cached_promotions: list
        +get_active_promotions_by_store_async(store_code) list
        +clear_cache()
    }

    class PromotionMasterDocument {
        +tenant_id: string
        +promotion_code: string
        +promotion_type: string
        +name: string
        +start_datetime: datetime
        +end_datetime: datetime
        +is_active: bool
        +detail: dict
    }

    class CategoryPromoDetail {
        +target_store_codes: list~string~
        +target_category_codes: list~string~
        +discount_rate: float
    }

    class CartDocument {
        +cart_id: string
        +line_items: list~CartLineItem~
        +store_code: string
    }

    class CartLineItem {
        +line_no: int
        +item_code: string
        +category_code: string
        +unit_price: float
        +quantity: int
        +is_discount_restricted: bool
        +is_cancelled: bool
        +discounts: list~DiscountInfo~
    }

    class DiscountInfo {
        +seq_no: int
        +discount_type: string
        +discount_value: float
        +discount_amount: float
        +detail: string
        +promotion_code: string
        +promotion_type: string
    }

    AbstractSalesPromo <|-- CategoryPromoPlugin
    CategoryPromoPlugin --> PromotionMasterWebRepository
    PromotionMasterWebRepository ..> PromotionMasterDocument
    PromotionMasterDocument *-- CategoryPromoDetail
    CartDocument *-- CartLineItem
    CartLineItem *-- DiscountInfo
    CategoryPromoPlugin ..> CartDocument
```

## 4. プロモーション適用判定フロー

```mermaid
flowchart TD
    Start([商品追加開始]) --> GetPromos[有効プロモーション取得]
    GetPromos --> HasPromos{プロモーション<br/>あり?}
    HasPromos -->|No| End([処理終了])
    HasPromos -->|Yes| BuildMap[カテゴリマップ構築]
    BuildMap --> LoopStart{次のLineItem}

    LoopStart -->|あり| CheckCancelled{is_cancelled?}
    LoopStart -->|なし| End

    CheckCancelled -->|Yes| LoopStart
    CheckCancelled -->|No| CheckRestricted{is_discount_restricted?}

    CheckRestricted -->|Yes| LoopStart
    CheckRestricted -->|No| CheckExisting{既存の<br/>category_discount?}

    CheckExisting -->|Yes| LoopStart
    CheckExisting -->|No| FindPromo{カテゴリに<br/>マッチする<br/>プロモーション?}

    FindPromo -->|No| LoopStart
    FindPromo -->|Yes| ApplyDiscount[割引適用]

    ApplyDiscount --> CreateDiscount[DiscountInfo作成]
    CreateDiscount --> SetPromoCode[promotion_code設定]
    SetPromoCode --> SetPromoType[promotion_type設定]
    SetPromoType --> AddToList[discountsに追加]
    AddToList --> LoopStart
```

## 5. データフロー図

```mermaid
flowchart LR
    subgraph Input["入力"]
        Cart["CartDocument<br/>・line_items<br/>・store_code"]
        Promo["PromotionMaster<br/>・promotion_code<br/>・target_category_codes<br/>・discount_rate"]
    end

    subgraph Process["処理"]
        Match["カテゴリマッチング"]
        Calc["割引額計算<br/>unit_price × qty × rate%"]
        Select["最高割引選択"]
    end

    subgraph Output["出力"]
        Discount["DiscountInfo<br/>・promotion_code<br/>・promotion_type<br/>・discount_value<br/>・discount_amount"]
    end

    Cart --> Match
    Promo --> Match
    Match --> Select
    Select --> Calc
    Calc --> Discount
```

## 6. 複数プロモーション時の最適選択

```mermaid
flowchart TB
    subgraph Promotions["同一カテゴリに対する複数プロモーション"]
        P1["Promo A<br/>discount_rate: 10%"]
        P2["Promo B<br/>discount_rate: 15%"]
        P3["Promo C<br/>discount_rate: 5%"]
    end

    subgraph Selection["選択ロジック"]
        Compare["割引率比較"]
        Best["最高割引率選択"]
    end

    subgraph Result["適用結果"]
        Applied["Promo B (15%) を適用"]
    end

    P1 --> Compare
    P2 --> Compare
    P3 --> Compare
    Compare --> Best
    Best --> Applied

    style P2 fill:#90EE90
    style Applied fill:#90EE90
```

## 7. 店舗フィルタリング

```mermaid
flowchart TB
    subgraph PromoTypes["プロモーションタイプ"]
        AllStores["全店舗対象<br/>target_store_codes: []"]
        SpecificStores["特定店舗対象<br/>target_store_codes: ['001', '002']"]
    end

    subgraph CurrentStore["現在の店舗: 001"]
        Store["store_code: 001"]
    end

    subgraph FilterLogic["フィルタロジック"]
        Check1{"target_store_codes<br/>が空?"}
        Check2{"現在の店舗が<br/>リストに含まれる?"}
    end

    subgraph Result["結果"]
        Apply["適用対象"]
        Skip["スキップ"]
    end

    AllStores --> Check1
    Check1 -->|Yes| Apply

    SpecificStores --> Check2
    Check2 -->|Yes| Apply
    Check2 -->|No| Skip

    style Apply fill:#90EE90
    style Skip fill:#FFB6C1
```

## 8. APIレスポンス構造

```mermaid
flowchart TB
    subgraph Response["APIレスポンス"]
        direction TB
        LineItems["lineItems[]"]

        subgraph Item["lineItem"]
            ItemCode["itemCode: '49-01'"]
            CategoryCode["categoryCode: '001'"]
            Discounts["discounts[]"]

            subgraph DiscountInfo["discount"]
                DType["discountType: 'percent'"]
                DValue["discountValue: 10.0"]
                DAmount["discountAmount: 100"]
                PCode["promotionCode: 'SUMMER_SALE'"]
                PType["promotionType: 'category_discount'"]
            end
        end
    end

    LineItems --> Item
    Discounts --> DiscountInfo
```

---

## 関連ファイル

| コンポーネント | ファイルパス |
|---------------|-------------|
| CategoryPromoPlugin | `services/cart/app/services/strategies/sales_promo/category_promo.py` |
| PromotionMasterWebRepository | `services/cart/app/models/repositories/promotion_master_web_repository.py` |
| CartService | `services/cart/app/services/cart_service.py` |
| PromotionMasterDocument | `services/master-data/app/models/documents/promotion_master_document.py` |
| Promotion API | `services/master-data/app/api/v1/promotion_master.py` |
| プラグイン設定 | `services/cart/app/services/strategies/plugins.json` |
