# データモデル設計

## 概要

カテゴリプロモーション機能で使用するデータモデルを定義する。

## エンティティ

### 1. PromotionMasterDocument

**コレクション名**: `master_promotion`
**サービス**: master-data

```
PromotionMasterDocument
├── _id: ObjectId                    # MongoDB自動生成
├── tenant_id: str                   # テナントID
├── promotion_code: str              # プロモーションコード（一意）
├── promotion_type: str              # プロモーションタイプ
├── name: str                        # 表示名
├── description: str                 # 説明
├── start_datetime: datetime         # 開始日時
├── end_datetime: datetime           # 終了日時
├── is_active: bool                  # 有効フラグ
├── is_deleted: bool                 # 論理削除フラグ
├── category_promo_detail: object    # カテゴリプロモーション詳細（タイプ固有）
│   ├── target_store_codes: list[str]     # 対象店舗コード（空=全店舗）
│   ├── target_category_codes: list[str]  # 対象カテゴリコード
│   └── discount_rate: float              # 割引率（%）
├── created_at: datetime             # 作成日時
└── updated_at: datetime             # 更新日時
```

**フィールド詳細**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| tenant_id | str | Yes | テナント識別子 |
| promotion_code | str | Yes | プロモーション一意識別子 |
| promotion_type | str | Yes | "category_discount" など |
| name | str | Yes | プロモーション表示名 |
| description | str | No | 詳細説明 |
| start_datetime | datetime | Yes | 有効開始日時 |
| end_datetime | datetime | Yes | 有効終了日時 |
| is_active | bool | Yes | 有効/無効フラグ（デフォルト: true） |
| is_deleted | bool | Yes | 論理削除フラグ（デフォルト: false） |
| category_promo_detail | object | No | カテゴリプロモーション固有の詳細 |

**カテゴリプロモーション詳細**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| target_store_codes | list[str] | No | 対象店舗コードのリスト（空=全店舗適用） |
| target_category_codes | list[str] | Yes | 対象カテゴリコードのリスト |
| discount_rate | float | Yes | 割引率（例: 10.0 = 10%オフ） |

**インデックス**:

| インデックス | フィールド | ユニーク |
|-------------|-----------|----------|
| idx_tenant_promotion_code | tenant_id, promotion_code | Yes |
| idx_tenant_type_active | tenant_id, promotion_type, is_active | No |
| idx_tenant_active_datetime | tenant_id, is_active, start_datetime, end_datetime | No |

**バリデーションルール**:

1. `promotion_code` は tenant_id 内で一意
2. `end_datetime` > `start_datetime`
3. `discount_rate` は 0 < rate <= 100
4. `promotion_type` が "category_discount" の場合、`category_promo_detail` は必須
5. `target_category_codes` は少なくとも1つの要素を含む

---

### 2. DiscountInfo（拡張）

**場所**: `services/commons/src/kugel_common/models/documents/base_tranlog.py`

```
DiscountInfo（既存 + 拡張）
├── seq_no: int                      # 連番（既存）
├── discount_type: str               # 割引タイプ（既存）
├── discount_value: float            # 割引値（既存）
├── discount_amount: float           # 割引金額（既存）
├── detail: str                      # 詳細（既存）
├── promotion_code: str              # プロモーションコード（新規）
└── promotion_type: str              # プロモーションタイプ（新規）
```

**新規フィールド**:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| promotion_code | str | No | 適用されたプロモーションのコード |
| promotion_type | str | No | プロモーションタイプ |

**後方互換性**:
- 新規フィールドはすべてOptional
- 既存の取引ログは影響を受けない

---

### 3. CartDocument.CartLineItem（参照）

**場所**: `services/cart/app/models/documents/cart_document.py`

カート明細の割引情報にプロモーション情報を追加する。
既存の `discounts` フィールドに DiscountInfo を追加する際、
新規フィールド（promotion_code, promotion_type）を設定する。

---

## 状態遷移

### プロモーションのライフサイクル

```
[作成] → [有効] ⟷ [無効] → [削除]
           ↓
      [期限切れ]
```

| 状態 | is_active | is_deleted | 現在時刻 |
|------|-----------|------------|----------|
| 有効 | true | false | start ≤ now ≤ end |
| 無効（手動） | false | false | - |
| 期限切れ | true | false | now > end |
| 削除 | - | true | - |

**有効なプロモーションの条件**:
```
is_active = true
AND is_deleted = false
AND start_datetime <= current_time
AND end_datetime >= current_time
```

---

## 関連図

```
┌─────────────────────┐
│ CategoryMaster      │
│ (既存)              │
├─────────────────────┤
│ category_code (PK)  │
│ description         │
│ tax_code            │
└─────────────────────┘
          ▲
          │ 参照
          │
┌─────────────────────┐
│ PromotionMaster     │
│ (新規)              │
├─────────────────────┤
│ promotion_code (PK) │
│ promotion_type      │
│ name                │
│ target_category_    │
│   codes[] ──────────┼──── 1:N 参照
│ discount_rate       │
│ start/end_datetime  │
│ is_active           │
└─────────────────────┘
          │
          │ 適用
          ▼
┌─────────────────────┐
│ CartLineItem        │
│ (既存)              │
├─────────────────────┤
│ item_code           │
│ category_code ──────┼──── マッチング
│ unit_price          │
│ discounts[] ────────┼──── DiscountInfo追加
└─────────────────────┘
          │
          │ 記録
          ▼
┌─────────────────────┐
│ TransactionLog      │
│ (既存)              │
├─────────────────────┤
│ line_items[]        │
│   └── discounts[]   │
│       └── promotion_│
│           code ─────┼──── 実績集計に使用
└─────────────────────┘
```

---

## マイグレーション

### 新規コレクション

1. `master_promotion` コレクション作成
2. インデックス作成

### 既存スキーマ変更

1. `DiscountInfo` に新規フィールド追加（後方互換）
   - 既存データへの影響なし
   - 新規フィールドはOptionalのため、既存コードは変更不要

### データマイグレーション

- 既存データのマイグレーションは不要
- 新規フィールドは新しい取引からのみ設定される
