# Implementation Plan: 毎リクエストでのカートスナップショット提示とサーバ側キャッシュの権威降格（client-carried cart phase 2）

**Branch**: `156-stateless-cart` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/156-stateless-cart/spec.md`

## Summary

POS が**既存カートへの全変更系リクエストに署名付きスナップショットを同梱**し、バックエンドは検証・再構成のうえ操作を適用、新しいスナップショットを返す。これによりクライアント保持スナップショットが取引状態の正となり、サーバ側キャッシュは（移行期間後に）権威でなくなる。技術アプローチ:

- **あり/なし分岐は DI 層**で行い、phase 1 の検証・再構成（`snapshot_service` / `restore_cart_async`）を毎リクエスト・キャッシュ非依存に一般化する（R-002）。ビジネスロジックは経路非依存。
- **取引連番を `(business_counter, seq)` 複合の持ち回り**に再定義（R-003）。`business_counter` は terminal service の open エポック（既存）、`seq` は cart_document に載せて端末が持ち回る。`terminal_counter` 採番はあり経路で不使用、移行後撤去。交換は新 open=新エポックで seq 復元不要。
- **二重計上対策は確定ゲートを設けず下流で収束**: tranlog に `cart_id` を追加（R-004、#152 中核）し、report/journal/stock を `cart_id` 基準の冪等収束へ（R-005）。lost-ACK 再送は同一 cart_id・同一番号で1件に収束。
- **デュアルモード**（`CART_REQUEST_SNAPSHOT_MODE` env、`DUAL`/`REQUIRED`）でクライアント段階移行を許容（R-007）。キャッシュ撤去は移行完了後（本スコープ外）。
- **リクエスト展開ミドルウェア**を commons に新設（展開後サイズガード付き、R-006）。

## Technical Context

**Language/Version**: Python 3.12+（既存サービスと同一）
**Primary Dependencies**: FastAPI、Pydantic v2、Motor（async MongoDB）、Dapr（pub/sub `pubsub-tranlog-report` / topic `topic-tranlog`、state store）。署名は phase 1 の `kugel_common.utils.hmac_signer`（標準ライブラリのみ）。リクエスト展開は標準 `gzip` + `brotli`（クライアント .NET 8 が `br`/`gzip` 標準対応）
**Storage**: MongoDB テナント別 DB。tranlog（report/journal）・stock_update のインデックスを cart_id 基準へ是正。監査は phase 1 `log_cart_restore` を一般化
**Testing**: pytest 3 層（unit / integration / e2e、既存の自動マーキング規約）。デュアルモードのため あり/なし × キャッシュ正常/障害 のマトリクスを integration で担保
**Target Platform**: Linux コンテナ（Docker Compose / Azure Container Apps）
**Project Type**: マイクロサービス（変更は cart + commons + report/journal/stock + terminal 軽微）
**Performance Goals**: あり経路の毎リクエスト検証+再構成で p95 +50ms 以内（phase 1 実装比、SC-006）
**Constraints**: 40 商品カートでスナップショット同梱リクエストの圧縮後 ≤15KB（SC-005）。展開後サイズ上限ガード必須（zip-bomb 対策）。確定は中央権威への同期問い合わせ禁止（オフライン確定両立、FR-006）
**Scale/Scope**: cart 変更系 12 エンドポイントのリクエスト契約拡張 + DI 分岐 + 採番再定義 + commons 展開ミドルウェア + 下流 3 サービスの冪等化（#152）
**前提（spec Assumptions）**: A-1 1カート=1クライアント / A-2 逐次引き継ぎ / A-3 同一操作リトライ / A-4 端末が seq 権威
**Auth 前提**: 任意バックエンド接続は JWT 認証前提（#67、phase 1 と同一制約）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 | 根拠 |
|---|---|---|
| 0. 言語規則（成果物は日本語、コード内コメント/ログは英語） | ✅ PASS | spec / plan / research / data-model / quickstart はすべて日本語。実装時のコメント・ログは英語 |
| その他の原則 | N/A | constitution はテンプレート未確定（プレースホルダ）のため評価対象は言語規則のみ |

**Phase 1 設計後の再評価**: 違反なし。新規外部依存は `brotli`（リクエスト展開、commons）のみで、用途が明確。変更は cart / commons / report / journal / stock / terminal に閉じ、プロジェクト追加なし。複雑性は #146 の段階設計に沿う必要最小限（デュアルモードは移行のための一時複雑性で、移行完了後に解消する旨を spec/Out of Scope に明記済み）。

## Project Structure

### Documentation (this feature)

```text
specs/156-stateless-cart/
├── spec.md              # 仕様（Clarifications 確定済み）
├── plan.md              # 本ファイル
├── research.md          # Phase 0: R-001〜R-010
├── data-model.md        # Phase 1: エンベロープ往復・seq・cart_id・インデックス
├── quickstart.md        # Phase 1: 動作確認 6 シナリオ + 計測
├── contracts/
│   └── request-snapshot.yaml  # Phase 1: リクエストへの signedSnapshot 付加 OpenAPI
├── checklists/
│   └── requirements.md  # spec 品質チェックリスト（全項目パス）
└── tasks.md             # /speckit.tasks で生成（本コマンドでは作らない）
```

### Source Code (repository root)

```text
services/commons/src/kugel_common/
├── middleware/
│   └── http_compression.py        # 変更: リクエストボディ展開ミドルウェア追加（展開後サイズガード）
└── models/documents/
    └── base_tranlog.py            # 変更: BaseTransaction に cart_id を追加（#152）

services/cart/app/
├── api/
│   ├── common/schemas.py          # 変更: 変更系リクエストに signed_snapshot（任意）
│   └── v1/
│       ├── cart.py                # 変更: 変更系エンドポイントの DI 切替（あり/なし）
│       └── schemas.py             # 変更: リクエストスキーマに signed_snapshot
├── config/
│   └── settings_cart.py           # 変更: CART_REQUEST_SNAPSHOT_MODE（DUAL/REQUIRED）
├── dependencies/
│   └── get_cart_service.py        # 変更: スナップショット有無で経路分岐（核心）
├── exceptions/
│   └── cart_error_codes.py        # 変更: なし経路拒否（REQUIRED）・連番異常のコード追加
├── models/documents/
│   └── cart_document.py           # 変更: seq フィールド追加
└── services/
    ├── snapshot_service.py        # 変更: 毎リクエスト検証への一般化（restore と共通）+ finalize-context 封筒の build/verify（void/return、R-011）
    ├── cart_service.py            # 変更: あり経路の再構成（キャッシュ非依存）・seq 採番・確定
    └── tran_service.py            # 変更: 確定時 cart_id 引き継ぎ・(business_counter, seq) 反映、void/return の carried 採番（finalize-context 封筒、R-011）

services/report/app/   # 変更: tranlog 取り込みを cart_id 冪等へ、index 是正（#152）、DailyInfo 検証指紋を (business_counter, transaction_no) 順へ（R-012）
services/journal/app/  # 変更: 同上（index 是正）
services/stock/app/    # 変更: stock_update 事前チェック/ index を cart_id 基準へ（$inc 保護温存）
services/terminal/app/ # 変更: seq 初期化コンテキストの提供 + close ログ cart_transaction_last_no を (business_counter, transaction_no) 順へ（R-012）

services/*/tests/      # unit / integration / e2e: あり/なし分岐・採番・交換・下流冪等・計測
```

**Structure Decision**: 変更は cart を中心に commons（tranlog スキーマ + 展開ミドルウェア）と下流 3 サービス（cart_id 冪等化＝#152）に及ぶ。phase 1 の薄い追加と異なり、本フェーズは tranlog スキーマ変更（cart_id）と採番再定義が下流に波及するため**マルチサービス変更**になる。既存の DI / repository / pub-sub 取り込みパターンは踏襲し、新規概念は持ち込まない。

## 確定した設計判断（spec「未解決事項」の解決）

| spec の未解決事項 | 決定 | 詳細 |
|---|---|---|
| デュアルモードの設定キー・値・既定・移行判定 | `CART_REQUEST_SNAPSHOT_MODE`（DUAL/REQUIRED、既定 DUAL）+ なし経路メトリクス | [R-007](./research.md) |
| 照会系（GET）の応答ソース | 移行期間は従来どおりキャッシュ供給、撤去後は後続フェーズ | [R-007](./research.md) |
| seq 初期化のコンテキスト提供 | cart_document に seq 保持（作成時 0）、確定時 +1 | [R-003](./research.md) |
| 下流 cart_id 冪等化・transaction_no キー是正の範囲 | report/journal/stock を cart_id 基準 dedup、index 是正 | [R-004](./research.md) / [R-005](./research.md) |
| 展開アルゴリズムと上限値 | gzip + br、展開後上限（例 1 MB、tasks で確定） | [R-006](./research.md) |
| エンベロープのスキーマ変更要否 | 不要（seq は cart_document 内、schema_version 据え置き） | [R-003](./research.md) |
| 監査の保存先・保持期間 | phase 1 `log_cart_restore` 一般化（TTL なし、異常系のみ） | [R-009](./research.md) |

## 実装フェーズの概要（tasks.md の入力）

1. **基盤（commons）**: `BaseTransaction.cart_id` 追加、リクエスト展開ミドルウェア（サイズガード）— unit テスト先行。
2. **採番再定義（cart）**: `CartDocument.seq`、確定時の `(business_counter, seq)` 反映 + `cart_id` 引き継ぎ（`tran_service`）。あり経路では `terminal_counter` 採番を使わない。なし経路は従来採番（デュアル一貫性）。**void/return も署名付き finalize-context 封筒で carried 採番＋安定 cart_id 冪等化（R-011）**。
3. **あり/なし分岐（cart）**: `get_cart_service` の DI 分岐、リクエストスキーマに `signed_snapshot`、`CART_REQUEST_SNAPSHOT_MODE`、`snapshot_service` の毎リクエスト検証一般化。あり経路はキャッシュ非依存・乖離検知（ベストエフォート）。
4. **下流冪等化（report/journal/stock、#152）**: tranlog/stock_update の dedup を cart_id 基準へ、index 是正、$inc 保護温存。連番整合性の監査検知（R-010）。**全量到達検証の指紋を (business_counter, transaction_no) 順へ決定論化（terminal close + report DailyInfo、R-012）**。
5. **監査一般化 + エラーコード**: `log_cart_restore` を毎リクエスト検証へ拡張、なし経路拒否（REQUIRED）・連番異常コード。
6. **e2e + 計測**: quickstart 6 シナリオ、サイズ/レイテンシ実測（SC-005/SC-006）、結果を issue #156 へ。

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| デュアルモード（2 権威モデルの共存） | 単一 .NET 8 アプリでも全端末への配信は非同時。phase 1↔2 クライアント共存が移行に必須（FR-008） | 必須化一括切替 → 配信途中の旧アプリ端末が全滅。移行不能 |
| マルチサービス変更（下流 3 サービス） | cart_id 冪等収束（#152）はサーバが権威を失った後の唯一の二重計上防止機構。tranlog スキーマ変更が下流に不可避に波及 | cart 内に閉じる → tranlog に cart_id が無く収束不能（下流調査で確認）。確定ゲート（中央レジストリ）→ オフライン確定と両立せず |
