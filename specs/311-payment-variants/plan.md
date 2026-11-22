# Implementation Plan: 支払マスタのサブコード（派生）による支払の分類

**Branch**: `311-payment-variants` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/311-payment-variants/spec.md`
**Issue**: [#311](https://github.com/kugel-masa/kugelpos-backend/issues/311)

## Summary

支払方法（支払マスタ）の下にサブコード（派生）を持たせ、支払をその支払方法の中で分類して記録・集計できるようにする。

- **master-data**: 支払マスタの文書に `variants[]`（`variant_code`・`name`・`is_active`）を内包し、v1 の子リソース `/payments/{payment_code}/variants` で登録・一覧・取得・変更する（削除なし）。一意性は支払方法の中で、条件付きの原子更新で守る
- **commons**: 取引の支払行に `variant_code`・`builtin_description` を追加
- **cart**: 支払の要求に任意の `variant_code`。決定は純関数（販売・返品）に置き、`CartService` がプラグインの前に決めてキーワード引数で渡す（#308 の契約）。取消は売上時の「支払方法＋サブコード」と金額で照合し、返品は売上時の支払種別（売上時の金額まで）か現金 `01` に限る
- **report**: 売上レポート・支払レポートを支払方法単位のまま、サブコード別の内訳を追加

挙動（プラグイン・上限・返金可否・超過預かり・釣銭）は支払方法のまま。既存の支払コードと `plugins.json` は変えない。

## Technical Context

**Language/Version**: Python 3.12+（他のサービスと同じ）
**Primary Dependencies**: FastAPI、Pydantic v2、Motor（MongoDB 非同期）、Dapr（`DaprClientHelper`・状態ストア `masterstore` によるマスタのキャッシュ）。新しい外部依存なし
**Storage**: テナントごとの MongoDB。master-data の `master_payment` の文書に配列を追加（索引の変更なし）。取引ログ（cart・journal・report）の支払行に項目を追加
**Testing**: pytest（unit / integration / e2e の 3 層）、pytest-asyncio。cart の e2e はスナップショットを伴う形で書く
**Target Platform**: Linux コンテナ（Docker Compose・Azure Container Apps）
**Project Type**: マイクロサービス（`services/<service>/app`）
**Performance Goals**: 支払の登録の追加の処理は、キャッシュ済みの支払マスタの配列の走査だけ（数十件）。応答時間の目立つ増加なし
**Constraints**: 追加のみの互換。サブコードの無いマスタで結果が変わらない（spec FR-023）。カートのスナップショットの schema_version を上げない（R-9）
**Scale/Scope**: 1 支払方法あたりサブコード数十件程度

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` で定まっている原則は「0. 言語規則」だけ（他は雛形のまま）。CLAUDE.md の規約を合わせて確認する。

| 項目 | 判定 | 根拠 |
|---|---|---|
| 言語規則（成果物は日本語、コードのコメント・ログは英語） | ✅ | spec・plan・research・data-model・contracts・quickstart は日本語。コードは英語で書く |
| API は `/api/v1/` で版付け、Pydantic のスキーマ、Transformer で変換 | ✅ | 子リソースを v1 に追加。要求・応答のスキーマと Transformer を足す |
| API 命名規約（複数形・snake_case のパス引数・動詞をパスに入れない） | ✅ | `/payments/{payment_code}/variants/{variant_code}`、変更は `PUT` |
| リポジトリパターン・DB 操作は async | ✅ | `PaymentMasterRepository` に非同期のメソッドを足す |
| エラーコード XXYYZZ・サービスの範囲 | ✅ | cart は 4030xx（403018–403022）。master-data は既存の例外 |
| プラグインの契約（#308） | ✅ | `variant_code` はキーワード引数で渡す。契約の範囲内 |
| テストの 3 層・cart e2e の `dual_only` 規則 | ✅ | 新しい cart e2e はスナップショットを伴う |
| コメントアウトしたコードを残さない・型ヒント | ✅ | 実装時に守る |

**Phase 1 後の再確認**: 設計（data-model・contracts）は上の項目に反しない。違反なし。Complexity Tracking は不要。

## Project Structure

### Documentation (this feature)

```text
specs/311-payment-variants/
├── spec.md
├── plan.md              # このファイル
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── master-data-payment-variants.md
│   ├── cart-payments.md
│   └── tranlog-and-reports.md
├── checklists/requirements.md
└── tasks.md             # Phase 2（/speckit.tasks が作る）
```

### Source Code (repository root)

```text
services/commons/src/kugel_common/
└── models/documents/base_tranlog.py           # Payment に variant_code・builtin_description

services/master-data/app/
├── models/documents/payment_master_document.py   # PaymentVariant・variants
├── models/repositories/payment_master_repository.py  # add_variant_async・update_variant_async（条件付きの原子更新）
├── services/payment_master_service.py          # サブコードの登録・一覧・取得・変更
├── api/common/schemas.py                       # 変種の要求・応答、BasePaymentResponse.variants
├── api/common/schemas_transformer.py           # 変換（variant_code 昇順）
├── api/v1/schemas.py                           # v1 の型
└── api/v1/payment_master.py                    # 子リソースの 4 端点
services/master-data/tests/{unit,integration,e2e}/

services/cart/app/
├── models/documents/payment_master_document.py   # variants（読み取り）
├── services/logics/payment_variant_logic.py       # 新設: resolve_sale_variant・match_void_payments・match_return_payments
├── services/cart_service.py                       # 決定 → pay(variant_code=...) → 事後の確認
├── services/strategies/payments/abstract_payment.py  # settle_payment_async・_build_cart_payment が variant を書く
├── services/strategies/payments/{cash,cashless,others}.py  # variant_code を settle へ渡す
├── services/tran_service.py                       # 取消: 鍵 (payment_code, variant_code) で照合 / 返品: 売上時の支払種別か現金・403021・403022
├── api/common/schemas.py                          # BasePaymentRequest.variant_code、BaseTranPayment の 2 項目
├── api/common/schemas_transformer.py              # 支払行の応答
└── exceptions/{cart_error_codes,cart_exceptions}.py  # 403018–403022
services/cart/tests/{unit,integration,e2e}/

services/report/app/
├── models/documents/sales_report_document.py      # PaymentReportTemplate に payment_code・variants
├── models/documents/payment_report_document.py    # PaymentSummaryItem に variants
├── services/plugins/sales_report_maker.py         # 分組の鍵に variant_code、後段で内訳を合算
├── services/plugins/payment_report_maker.py       # 内訳のパイプライン・マスタのサブコード名・マスタの全ページ取得
└── api/common/{schemas,schemas_transformer}.py    # 売上レポートの応答
services/report/tests/{unit,integration}/

docs/{en,ja}/
├── master-data/{api,model}-specification.md
├── cart/{api,model}-specification.md
├── report/{api,model}-specification.md
└── general/error_code_spec.md                    # 403018–403022
```

**Structure Decision**: 既存のサービスの層（documents → repositories → services → api）に沿って足す。新しいモジュールは cart の `payment_variant_logic.py`（純関数）だけ。

## 実装の順序（依存）

1. **commons**: 支払行の 2 項目（他のすべてが依存。変更後に各サービスへ配る `./scripts/build.sh` の commons の手順）
2. **master-data**: 文書・リポジトリ・サービス・API（cart の読み取りが依存）
3. **cart**: 読み取りの型 → 決定の純関数 → 支払の登録 → 取消・返品 → 応答
4. **report**: 売上レポート → 支払レポート
5. **docs**: API・モデル・エラーコードの仕様（en・ja）

US1 は master-data、US2 は commons・cart、US3 は cart、US4 は report。**配備の順序**（research R-14）: サブコードの登録は commons・cart・report を本フィーチャーの版へ配備し終えた後に限る。古い cart はマスタの `variants` を読まずに捨てるので、先に登録するとサブコードの指定が無視されて記帳される。master-data を先に出すことはできるが、その間はサブコードを登録しない（リリースノートと運用手順に書く）。

## テストの方針

| 層 | 対象 |
|---|---|
| unit | master-data: スキーマの検証（コードの形式・空の名前・PUT の追加項目）、サービスの分岐（支払方法なし・重複・なし）。cart: `resolve_sale_variant` の表の全行、`match_void_payments`（鍵の不一致・金額の不一致・省略はサブコードなし）、`match_return_payments`（売上時の鍵・現金・それ以外 403021・上限 403022・停止中のサブコード）、`CartService` の事前の一括決定（2 件目のサブコードが拒否ならプラグインを 1 回も呼ばない）と事後の確認（サブコードを捨てるプラグイン）。|
| integration（MongoDB） | master-data: 条件付きの `$push` の重複拒否（同時 2 件）、位置指定の `$set`、支払マスタの更新でサブコードが残る、削除で消える。report: パイプラインの分組（`(payment_code, variant_code)`）と支払レポートの取引数、期間中に改名したサブコードの名前が最も新しい販売時点のものになること |
| e2e | master-data: 子リソースの CRUD。cart: サブコードでの支払・指定必須・存在しない・停止中・2 件の支払の要求で 2 件目が 403018 のときカートが変わらないこと・取消（鍵ごとの照合）・返品（売上時の支払種別・現金・上限・停止後）|

## Complexity Tracking

違反なし。
