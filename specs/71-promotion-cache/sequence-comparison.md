# プロモーションマスタ取得 シーケンス比較

## 1. カート作成時

### Before（変更前）

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant Dapr as Dapr State

    Client->>Cart: POST /cart/create
    Cart->>Cart: ターミナル状態チェック
    Cart->>Cart: スタッフサインインチェック
    Cart->>Cart: 店舗情報/設定マスタ/税マスタ取得
    Cart->>Cart: CartDocument 作成
    Cart->>Dapr: カートキャッシュ保存
    Cart-->>Client: cart_id 返却
```

### After（変更後）

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant MD as master-data
    participant Dapr as Dapr State

    Client->>Cart: POST /cart/create
    Cart->>Cart: ターミナル状態チェック
    Cart->>Cart: スタッフサインインチェック
    Cart->>Cart: 店舗情報/設定マスタ/税マスタ取得
    Note over Cart,MD: [追加] プロモーション取得(1回のみ)
    Cart->>MD: GET /promotions/active
    alt 成功
        MD-->>Cart: プロモーション一覧
        Cart->>Cart: ReferenceMasters.promotions に格納
    else 失敗
        MD-->>Cart: エラー
        Cart-->>Client: CartCannotCreateException
    end
    Cart->>Cart: CartDocument 作成(promotions埋め込み済み)
    Cart->>Dapr: カートキャッシュ保存
    Cart-->>Client: cart_id 返却
```

---

## 2. 商品登録時（プロモーション適用）

### Before（変更前）

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant Plugin as CategoryPromoPlugin
    participant MD as master-data

    Client->>Cart: POST /cart/add_item
    Cart->>Cart: 商品マスタ取得/明細追加
    Cart->>Cart: __subtotal_async()
    Note over Cart,MD: [毎回] プロモーション取得
    Cart->>Plugin: apply(cart_doc)
    Plugin->>MD: GET /promotions/active
    MD-->>Plugin: プロモーション一覧
    Plugin->>Plugin: カテゴリ照合/割引適用
    Plugin-->>Cart: cart_doc(割引適用済み)
    Cart->>Cart: calc_subtotal_async()
    Cart-->>Client: cart_doc 返却
```

### After（変更後）

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant Plugin as CategoryPromoPlugin

    Client->>Cart: POST /cart/add_item
    Cart->>Cart: 商品マスタ取得/明細追加
    Cart->>Cart: __subtotal_async()
    Note over Cart,Plugin: [API呼び出しなし] 埋め込みデータ使用
    Cart->>Cart: cart_doc.masters.promotions 取り出し
    Cart->>Plugin: apply(cart_doc, promotions)
    Plugin->>Plugin: カテゴリ照合/割引適用
    Plugin-->>Cart: cart_doc(割引適用済み)
    Cart->>Cart: calc_subtotal_async()
    Cart-->>Client: cart_doc 返却
```

---

## 3. 取引全体フロー比較

### Before（変更前）- 10商品の典型的な取引

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant MD as master-data

    Client->>Cart: カート作成
    Cart-->>Client: cart_id

    loop 商品登録 x 10回
        Client->>Cart: 商品追加
        Cart->>MD: GET /promotions/active
        MD-->>Cart: プロモーション一覧
        Cart-->>Client: cart_doc
    end

    Client->>Cart: 小計
    Cart->>MD: GET /promotions/active
    MD-->>Cart: プロモーション一覧
    Cart-->>Client: cart_doc

    Client->>Cart: 支払追加
    Cart->>MD: GET /promotions/active
    MD-->>Cart: プロモーション一覧
    Cart-->>Client: cart_doc

    Client->>Cart: 精算
    Cart->>MD: GET /promotions/active
    MD-->>Cart: プロモーション一覧
    Cart-->>Client: cart_doc

    Note over Cart,MD: API呼び出し 約13回
```

### After（変更後）- 10商品の典型的な取引

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant Cart as cart
    participant MD as master-data

    Client->>Cart: カート作成
    Note over Cart,MD: プロモーション取得(1回のみ)
    Cart->>MD: GET /promotions/active
    MD-->>Cart: プロモーション一覧
    Cart->>Cart: ReferenceMasters に埋め込み
    Cart-->>Client: cart_id

    loop 商品登録 x 10回
        Client->>Cart: 商品追加
        Cart->>Cart: 埋め込みデータで割引適用
        Cart-->>Client: cart_doc
    end

    Client->>Cart: 小計
    Cart->>Cart: 埋め込みデータで割引適用
    Cart-->>Client: cart_doc

    Client->>Cart: 支払追加
    Cart->>Cart: 埋め込みデータで割引適用
    Cart-->>Client: cart_doc

    Client->>Cart: 精算
    Cart->>Cart: 埋め込みデータで割引適用
    Cart-->>Client: cart_doc

    Note over Cart,MD: API呼び出し 1回
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
