# Data Model: 支払マスタのサブコード（派生）

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md) | **Date**: 2026-11-22

---

## master-data

### `PaymentMasterDocument`（コレクション `master_payment`・1 文書＝1 支払方法）

| 項目 | 変更 |
|---|---|
| `tenant_id`・`payment_code`・`description`・`limit_amount`・`can_refund`・`can_deposit_over`・`can_change`・`is_active` | 変更なし |
| `variants: list[PaymentVariant]` | **追加**（`Field(default_factory=list)`） |

### `PaymentVariant`（内包・新設）

| 項目 | 型 | 規則 |
|---|---|---|
| `variant_code` | str | `^[A-Za-z0-9_-]{1,20}$`。大文字・小文字を区別。同じ支払方法の中で一意（R-2）。登録後は変更不可 |
| `name` | str | 空でない（前後の空白だけは不可）。支払行の名前になる |
| `is_active` | bool | 既定 `true`。停止は `false`。物理削除しない |
| `created_at` | datetime | 登録時刻（応答では `entry_datetime`） |
| `updated_at` | Optional[datetime] | 最終更新時刻（応答では `last_update_datetime`） |

並び: 登録順に保存し、応答では `variant_code` の昇順に並べる。

### 状態遷移（サブコード）

```text
(なし) --登録--> 有効 <--停止/再開--> 停止中
```

- 削除の遷移は無い。支払方法の削除で文書ごと消える（FR-009）
- 停止中のサブコードは販売で指定できない（403019）。売上時の行にあるサブコードは、停止中でも取消・返品で指定できる（FR-016d）

### 索引

変更なし（既存の `{tenant_id, payment_code}` 一意）。支払方法の中の一意性は条件付きの原子更新で守る（R-2）。

---

## kugel_common

### `BaseTransaction.Payment`（取引の支払行・cart の `CartDocument.Payment` も同じ）

| 項目 | 変更 |
|---|---|
| `payment_no`・`payment_code`・`deposit_amount`・`amount`・`detail` | 変更なし |
| `description` | 意味の変更: サブコードで記帳した行はサブコードの名前、それ以外は支払方法の名前（現行どおり） |
| `variant_code: Optional[str] = None` | **追加**。サブコードなしは `None` |
| `builtin_description: Optional[str] = None` | **追加**。販売時点の支払方法の名前。本フィーチャーの前の行は `None` |

---

## cart

### `PaymentMasterDocument`（読み取り用）

| 項目 | 変更 |
|---|---|
| `variants: list[PaymentVariant]` | **追加**（`Field(default_factory=list)`。`variant_code`・`name`・`is_active`。camelCase の別名で master-data の応答を読む） |

型の構造が変わるので、キャッシュの鍵の指紋（`document_shape`）が変わり、古いキャッシュは読まれない（R-10）。

### サブコードの決定（純関数・`app/services/logics/payment_variant_logic.py`）

```text
VariantDecision
  variant_code: Optional[str]     # 決めたサブコード（None = サブコードなし）
  name: Optional[str]             # 支払行の description にする名前（None = 支払方法の名前）
  builtin_description: str        # 支払行の builtin_description

resolve_sale_variant(pay_doc, requested_code) -> VariantDecision           # R-6
match_void_payments(original_lines, requested) -> list[ReturnLineDecision]          # R-7（不一致は BadRequestBodyException）
match_return_payments(original_lines, requested, cash_code="01") -> list[ReturnLineDecision]   # R-8

ReturnLineDecision
  payment_code: str
  variant_code: Optional[str]
  name: Optional[str]                 # 売上時の行の description。None なら現在のマスタから
  builtin_description: Optional[str]  # 売上時の行の builtin_description。None なら現在のマスタから
  from_original: bool                 # 売上時の行に一致した（False は売上時に無い現金）
```

拒否は例外（`PaymentVariantNotFoundException` 403018・`PaymentVariantInactiveException` 403019・`PaymentVariantRequiredException` 403020・`ReturnTenderNotAllowedException` 403021・`ReturnAmountExceedsOriginalException` 403022）。売上時に無い現金の返品のサブコードは `resolve_sale_variant` で決める。

### 支払の要求（`BasePaymentRequest`・支払の登録・取消・返品で共用）

| 項目 | 変更 |
|---|---|
| `payment_code`・`amount`・`detail` | 変更なし |
| `variant_code: Optional[str] = None` | **追加**（camelCase で `variantCode`） |

### 支払行の応答（`BaseTranPayment`）

| 項目 | 変更 |
|---|---|
| `payment_no`・`payment_code`・`payment_name`・`payment_amount`・`payment_detail` | 変更なし（`payment_name` は支払行の `description`） |
| `variant_code: Optional[str] = None` | **追加** |
| `builtin_payment_name: Optional[str] = None` | **追加**（支払行の `builtin_description`） |

---

## report

### 売上レポート（`SalesReportDocument.payments` の行・`PaymentReportTemplate`）

| 項目 | 変更 |
|---|---|
| `payment_name`・`amount`・`count` | 変更なし（`payment_name` は販売時点の支払方法の名前。無ければ支払行の名前） |
| `payment_code: Optional[str] = None` | **追加** |
| `variants: list[PaymentVariantReport]`（`Field(default_factory=list)`） | **追加** |

### 支払レポート（`PaymentReportDocument.PaymentSummaryItem`）

| 項目 | 変更 |
|---|---|
| `payment_code`・`payment_name`・`count`・`amount`・`ratio` | 変更なし |
| `variants: list[PaymentVariantReport]`（`Field(default_factory=list)`） | **追加** |

### `PaymentVariantReport`（新設・両レポートで共用）

| 項目 | 型 | 規則 |
|---|---|---|
| `variant_code` | Optional[str] | `None` はサブコードなし |
| `variant_name` | str | 売上レポートは期間内で最も新しい販売時点の支払行の名前、支払レポートは現在のマスタの名前（無ければ同じく最も新しい支払行の名前） |
| `amount` | float | 取引種別の符号を掛けて合算 |
| `count` | int | 売上レポートは支払行の数、支払レポートは取引の数（ともに符号付き） |

並び: `variant_code` の昇順、`None` は末尾。

---

## 呼び名の対応（支払方法の名前・サブコードの名前）

| 層 | 支払行の名前（サブコードの名前 or 支払方法の名前） | 販売時点の支払方法の名前 | サブコード |
|---|---|---|---|
| 取引ログ・カートの文書（`BaseTransaction.Payment`） | `description` | `builtin_description` | `variant_code` |
| cart の API の応答（`BaseTranPayment`・camelCase） | `paymentName` | `builtinPaymentName` | `variantCode` |
| report のパイプラインの中間値 | `variant_name` | `builtin_name` | `variant_code` |
| 売上レポートの応答（camelCase） | 内訳の `variantName` | 行の `paymentName` | 内訳の `variantCode` |
| 支払レポートの応答（snake_case） | 内訳の `variant_name`（現在のマスタ優先） | 行の `payment_name`（現在のマスタ） | 内訳の `variant_code` |
