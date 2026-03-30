# プロモーションマスタ取得 シーケンス比較

## 1. カート作成時

### Before（変更前）

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant Dapr as Dapr State

    POS->>Cart: POST /cart/create
    Cart->>Cart: Terminal status check
    Cart->>Cart: Staff sign-in check
    Cart->>Cart: Get store/tax/settings master
    Cart->>Cart: Create CartDocument
    Cart->>Dapr: Save cart to cache
    Cart-->>POS: cart_id
```

### After（変更後）

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant MasterData
    participant Dapr as Dapr State

    POS->>Cart: POST /cart/create
    Cart->>Cart: Terminal status check
    Cart->>Cart: Staff sign-in check
    Cart->>Cart: Get store/tax/settings master
    Note over Cart,MasterData: [Added] Get promotions (once only)
    Cart->>MasterData: GET /promotions/active
    alt Success
        MasterData-->>Cart: Promotion list
        Cart->>Cart: Store in ReferenceMasters.promotions
    else Failure
        MasterData-->>Cart: Error
        Cart-->>POS: CartCannotCreateException
    end
    Cart->>Cart: Create CartDocument (promotions embedded)
    Cart->>Dapr: Save cart to cache
    Cart-->>POS: cart_id
```

---

## 2. 商品登録時（プロモーション適用）

### Before（変更前）

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant Plugin as CategoryPromoPlugin
    participant MasterData

    POS->>Cart: POST /cart/add_item
    Cart->>Cart: Get item master / add line item
    Cart->>Cart: __subtotal_async()
    Note over Cart,MasterData: [Every time] Fetch promotions
    Cart->>Plugin: apply(cart_doc)
    Plugin->>MasterData: GET /promotions/active
    MasterData-->>Plugin: Promotion list
    Plugin->>Plugin: Match category / apply discount
    Plugin-->>Cart: cart_doc (discount applied)
    Cart->>Cart: calc_subtotal_async()
    Cart-->>POS: cart_doc
```

### After（変更後）

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant Plugin as CategoryPromoPlugin

    POS->>Cart: POST /cart/add_item
    Cart->>Cart: Get item master / add line item
    Cart->>Cart: __subtotal_async()
    Note over Cart,Plugin: [No API call] Use embedded data
    Cart->>Cart: Extract cart_doc.masters.promotions
    Cart->>Plugin: apply(cart_doc, promotions)
    Plugin->>Plugin: Match category / apply discount
    Plugin-->>Cart: cart_doc (discount applied)
    Cart->>Cart: calc_subtotal_async()
    Cart-->>POS: cart_doc
```

---

## 3. 取引全体フロー比較

### Before（変更前）- 10商品の典型的な取引

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant MasterData

    POS->>Cart: Create Cart
    Cart-->>POS: cart_id

    loop Add Item x 10
        POS->>Cart: Add Item
        Cart->>MasterData: GET /promotions/active
        MasterData-->>Cart: Promotion list
        Cart-->>POS: cart_doc
    end

    POS->>Cart: Subtotal
    Cart->>MasterData: GET /promotions/active
    MasterData-->>Cart: Promotion list
    Cart-->>POS: cart_doc

    POS->>Cart: Payment
    Cart->>MasterData: GET /promotions/active
    MasterData-->>Cart: Promotion list
    Cart-->>POS: cart_doc

    POS->>Cart: Bill
    Cart->>MasterData: GET /promotions/active
    MasterData-->>Cart: Promotion list
    Cart-->>POS: cart_doc

    Note over Cart,MasterData: API calls: ~13 times
```

### After（変更後）- 10商品の典型的な取引

```mermaid
sequenceDiagram
    participant POS
    participant Cart
    participant MasterData

    POS->>Cart: Create Cart
    Note over Cart,MasterData: Fetch promotions (once only)
    Cart->>MasterData: GET /promotions/active
    MasterData-->>Cart: Promotion list
    Cart->>Cart: Store in cart document
    Cart-->>POS: cart_id

    loop Add Item x 10
        POS->>Cart: Add Item
        Cart->>Cart: Apply discount from stored data
        Cart-->>POS: cart_doc
    end

    POS->>Cart: Subtotal
    Cart->>Cart: Apply discount from stored data
    Cart-->>POS: cart_doc

    POS->>Cart: Payment
    Cart->>Cart: Apply discount from stored data
    Cart-->>POS: cart_doc

    POS->>Cart: Bill
    Cart->>Cart: Apply discount from stored data
    Cart-->>POS: cart_doc

    Note over Cart,MasterData: API calls: 1 time
```

---

## 4. 比較サマリー

| 観点 | Before | After |
|------|--------|-------|
| **プロモーション取得タイミング** | 商品登録/小計/支払/精算の各操作時 | カート作成時(1回のみ) |
| **API呼び出し回数/取引** | 約15回 | 1回 |
| **プロモーションデータの保持場所** | プラグイン内で都度取得(保持しない) | cart.masters.promotions に埋め込み |
| **プラグインの依存先** | PromotionMasterWebRepository(HTTP通信) | 引数 promotions(データのみ) |
| **取引内の価格一貫性** | 保証なし(取得タイミングでデータが異なる可能性) | 保証あり(同一スナップショットを使用) |
| **商品登録のレスポンスタイム** | API遅延に依存(ばらつきあり) | 均一(API呼び出しなし) |
| **プロモーション変更の反映** | 次の操作時に即時反映 | 次回の取引開始時(カート作成時)に反映 |
| **取得失敗時の挙動** | 空リストで続行(割引なし) | カート作成失敗(CartCannotCreateException) |
| **エラー検知タイミング** | 取引途中(商品登録時) | 取引開始前(カート作成時) |
