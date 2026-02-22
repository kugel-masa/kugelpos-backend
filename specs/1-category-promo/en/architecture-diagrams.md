# Category Promotion Feature Architecture Diagrams

## 1. Overall System Architecture

```mermaid
flowchart TB
    subgraph Client["Client"]
        POS["POS Terminal"]
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

## 2. Promotion Application Sequence Diagram (Required)

```mermaid
sequenceDiagram
    autonumber
    participant POS as POS Terminal
    participant CartAPI as Cart API
    participant CartSvc as CartService
    participant Plugin as CategoryPromoPlugin
    participant PromoRepo as PromotionMasterWebRepository
    participant MasterAPI as Master-Data API
    participant MongoDB as MongoDB

    POS->>+CartAPI: POST /carts/{cartId}/lineItems<br/>[itemCode, quantity]
    CartAPI->>+CartSvc: add_items_to_cart_async()

    Note over CartSvc: 0. Plugin initialization (during CartService construction)
    CartSvc->>Plugin: configure(tenant_id, terminal_info)
    Plugin->>Plugin: Create PromotionMasterWebRepository

    Note over CartSvc: 1. Retrieve product info & add line item
    CartSvc->>CartSvc: Retrieve info from product master
    CartSvc->>CartSvc: Create CartLineItem

    Note over CartSvc: 2. Apply promotion
    CartSvc->>+Plugin: apply(cart_doc)

    Plugin->>+PromoRepo: get_active_promotions_by_store_async()

    alt Cache hit
        PromoRepo-->>Plugin: Cached promotions
    else Cache miss
        PromoRepo->>+MasterAPI: GET /promotions/active<br/>?storeCode={code}&terminal_id={id}
        MasterAPI->>+MongoDB: Search active promotions<br/>(is_active=true, within period)
        MongoDB-->>-MasterAPI: Promotion list
        MasterAPI-->>-PromoRepo: Response [promotions]
        PromoRepo->>PromoRepo: Save to cache
        PromoRepo-->>-Plugin: Promotion list
    end

    Note over Plugin: 3. Build category-to-promotion map
    Plugin->>Plugin: _build_category_promotion_map()
    Note right of Plugin: Select highest discount rate per category

    loop For each LineItem
        Plugin->>Plugin: is_cancelled? → Skip
        Plugin->>Plugin: is_discount_restricted? → Skip
        Plugin->>Plugin: Existing category_discount? → Skip
        Plugin->>Plugin: Search promotion by category code

        alt Matching promotion found
            Plugin->>Plugin: _apply_promotion_to_line_item()
            Note right of Plugin: Create DiscountInfo<br/>Set promotion_code<br/>Set promotion_type
        end
    end

    Plugin-->>-CartSvc: Updated cart_doc

    Note over CartSvc: 4. Subtotal & tax calculation
    CartSvc->>CartSvc: calculate_subtotal()
    CartSvc->>CartSvc: calculate_taxes()

    CartSvc-->>-CartAPI: CartDocument
    CartAPI-->>-POS: Response<br/>{lineItems: [{discounts: [...]}]}
```

## 3. Class Diagram

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
        +category_promo_detail: CategoryPromoDetail
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

## 4. Promotion Application Decision Flow

```mermaid
flowchart TD
    Start([Item addition start]) --> GetPromos[Retrieve active promotions]
    GetPromos --> HasPromos{Promotions<br/>exist?}
    HasPromos -->|No| End([Processing complete])
    HasPromos -->|Yes| BuildMap[Build category map]
    BuildMap --> LoopStart{Next LineItem}

    LoopStart -->|Exists| CheckCancelled{is_cancelled?}
    LoopStart -->|None| End

    CheckCancelled -->|Yes| LoopStart
    CheckCancelled -->|No| CheckRestricted{is_discount_restricted?}

    CheckRestricted -->|Yes| LoopStart
    CheckRestricted -->|No| CheckExisting{Existing<br/>category_discount?}

    CheckExisting -->|Yes| LoopStart
    CheckExisting -->|No| FindPromo{Matching<br/>promotion for<br/>category?}

    FindPromo -->|No| LoopStart
    FindPromo -->|Yes| ApplyDiscount[Apply discount]

    ApplyDiscount --> CreateDiscount[Create DiscountInfo]
    CreateDiscount --> SetPromoCode[Set promotion_code]
    SetPromoCode --> SetPromoType[Set promotion_type]
    SetPromoType --> AddToList[Add to discounts]
    AddToList --> LoopStart
```

## 5. Data Flow Diagram

```mermaid
flowchart LR
    subgraph Input["Input"]
        Cart["CartDocument<br/>・line_items<br/>・store_code"]
        Promo["PromotionMaster<br/>・promotion_code<br/>・target_category_codes<br/>・discount_rate"]
    end

    subgraph Process["Processing"]
        Match["Category matching"]
        Calc["Discount calculation<br/>unit_price × qty × rate%"]
        Select["Select highest discount"]
    end

    subgraph Output["Output"]
        Discount["DiscountInfo<br/>・promotion_code<br/>・promotion_type<br/>・discount_value<br/>・discount_amount"]
    end

    Cart --> Match
    Promo --> Match
    Match --> Select
    Select --> Calc
    Calc --> Discount
```

## 6. Optimal Selection for Multiple Promotions

```mermaid
flowchart TB
    subgraph Promotions["Multiple promotions for the same category"]
        P1["Promo A<br/>discount_rate: 10%"]
        P2["Promo B<br/>discount_rate: 15%"]
        P3["Promo C<br/>discount_rate: 5%"]
    end

    subgraph Selection["Selection logic"]
        Compare["Compare discount rates"]
        Best["Select highest discount rate"]
    end

    subgraph Result["Applied result"]
        Applied["Apply Promo B (15%)"]
    end

    P1 --> Compare
    P2 --> Compare
    P3 --> Compare
    Compare --> Best
    Best --> Applied

    style P2 fill:#90EE90
    style Applied fill:#90EE90
```

## 7. Store Filtering

```mermaid
flowchart TB
    subgraph PromoTypes["Promotion types"]
        AllStores["All stores<br/>target_store_codes: []"]
        SpecificStores["Specific stores<br/>target_store_codes: ['001', '002']"]
    end

    subgraph CurrentStore["Current store: 001"]
        Store["store_code: 001"]
    end

    subgraph FilterLogic["Filter logic"]
        Check1{"target_store_codes<br/>is empty?"}
        Check2{"Current store<br/>in list?"}
    end

    subgraph Result["Result"]
        Apply["Applicable"]
        Skip["Skip"]
    end

    AllStores --> Check1
    Check1 -->|Yes| Apply

    SpecificStores --> Check2
    Check2 -->|Yes| Apply
    Check2 -->|No| Skip

    style Apply fill:#90EE90
    style Skip fill:#FFB6C1
```

## 8. API Response Structure

```mermaid
flowchart TB
    subgraph Response["API Response"]
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

## Related Files

| Component | File Path |
|-----------|-----------|
| CategoryPromoPlugin | `services/cart/app/services/strategies/sales_promo/category_promo.py` |
| PromotionMasterWebRepository | `services/cart/app/models/repositories/promotion_master_web_repository.py` |
| CartService | `services/cart/app/services/cart_service.py` |
| PromotionMasterDocument | `services/master-data/app/models/documents/promotion_master_document.py` |
| Promotion API | `services/master-data/app/api/v1/promotion_master.py` |
| Plugin configuration | `services/cart/app/services/strategies/plugins.json` |
