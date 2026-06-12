# Implementation Plan: 署名付きカートスナップショットのレスポンス付加と restore API（client-carried cart phase 1）

**Branch**: `148-cart-snapshot-restore` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/148-cart-snapshot-restore/spec.md`

## Summary

カート変更系の全 API レスポンスに、カート文書全体（`cart.masters` 含む）の HMAC 署名付きスナップショットを追加フィールドとして載せ、署名検証つきの restore API（`POST /api/v1/carts/restore`）で別バックエンド上にカートを再構築できるようにする。技術アプローチ:

- スナップショット = **エンベロープ + `CartDocument.model_dump(mode="json")`**（専用トランスポートスキーマなし、[R-002](./research.md#r-002-スナップショットのトランスポート表現)）。Redis キャッシュ JSON 化（#141/#142）で実証済みのラウンドトリップを restore の再構築に流用する。
- 署名 = **HMAC-SHA256 + canonical JSON**（標準ライブラリのみ、[R-003](./research.md#r-003-正規化canonical-serializationと署名方式)）。汎用署名ユーティリティは kugel_common、ドメインロジックは cart 内（[R-001](./research.md#r-001-署名正規化ユーティリティの置き場所)）。
- 鍵 = 共有シークレット + kid 世代管理（spec Clarifications 確定）。`SNAPSHOT_HMAC_KEYS` 環境変数で現行+前世代を配布（[R-004](./research.md#r-004-署名鍵の設定表現)）。
- 衝突 = 既存サーバ優先 + 差分通知（spec FR-006 確定）。restore レスポンスの `restored` / `diverged` フィールドで表現（[R-009](./research.md#r-009-restore-api-のエンドポイント形状)）。
- 監査 = テナント DB に `log_cart_restore` コレクション新設（[R-007](./research.md#r-007-監査証跡の保存先fr-007)）。

## Technical Context

**Language/Version**: Python 3.12+（既存サービスと同一）
**Primary Dependencies**: FastAPI、Pydantic v2、Motor（async MongoDB）、Dapr（state store `cartstore`）。署名は標準ライブラリ `hmac` / `hashlib` / `json` のみ — **新規外部依存なし**
**Storage**: MongoDB テナント別 DB（`db_cart_{tenant_id}`）に `log_cart_restore` コレクション新設。カートキャッシュ（Redis / `cache_cart` フォールバック）は既存どおり
**Testing**: pytest 3 層（`tests/unit` / `tests/integration` / `tests/e2e`、既存の自動マーキング規約に従う）
**Target Platform**: Linux コンテナ（Docker Compose / Azure Container Apps）
**Project Type**: マイクロサービス（変更は cart + kugel_common に限定）
**Performance Goals**: スナップショット生成+署名で p95 +50ms 以内（SC-006）
**Constraints**: 40 商品カートで gzip 後 15KB 以下（SC-005、#147 の圧縮が前提）。スナップショット生成失敗は縮退（操作は成功、warning ログ — R-006）
**Scale/Scope**: cart 変更系 12 エンドポイントへのフィールド付加 + 新規 1 エンドポイント + 新規コレクション 1
**Out-of-scope dependency**: 取引確定の cart_id 冪等化（tranlog への `cart_id` 追加 + 確定時重複検査）は**別 issue #152** で対応（spec Clarifications 2026-06-12）。SC-004 の完全達成は当該 issue に依存

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 | 根拠 |
|---|---|---|
| 0. 言語規則（成果物は日本語、コード内コメント/ログは英語） | ✅ PASS | spec / plan / research / data-model / quickstart はすべて日本語。実装時のコメント・ログは英語とする |
| その他の原則 | N/A | constitution はテンプレート未確定（プレースホルダ）のため評価対象は言語規則のみ |

**Phase 1 設計後の再評価**: 違反なし（新規依存なし・変更は cart + commons に閉じる・プロジェクト追加なし）。

## Project Structure

### Documentation (this feature)

```text
specs/148-cart-snapshot-restore/
├── spec.md              # 仕様（Clarifications 3 件確定済み）
├── plan.md              # 本ファイル
├── research.md          # Phase 0: 未解決事項の確定（R-001〜R-010）
├── data-model.md        # Phase 1: エンベロープ・監査レコード・スキーマ変更
├── quickstart.md        # Phase 1: 動作確認手順
├── contracts/
│   └── restore-api.yaml # Phase 1: restore API + snapshot フィールドの OpenAPI
├── checklists/
│   └── requirements.md  # spec 品質チェックリスト（全項目パス）
└── tasks.md             # Phase 2（/speckit.tasks で生成 — 本コマンドでは作らない）
```

### Source Code (repository root)

```text
services/commons/src/kugel_common/
└── utils/
    └── hmac_signer.py                 # 新規: 汎用 HMAC-SHA256 署名/検証（kid 世代管理・canonical JSON）

services/cart/app/
├── api/
│   ├── common/schemas.py              # 変更: BaseCart に signed_snapshot / restored / diverged を追加
│   └── v1/
│       ├── cart.py                    # 変更: restore エンドポイント追加（POST /carts/restore）
│       ├── schemas.py                 # 変更: restore リクエスト/レスポンススキーマ
│       └── schemas_transformer.py     # 変更: transform_cart にスナップショット詰め込み
├── config/
│   └── settings_cart.py               # 変更: SNAPSHOT_HMAC_KEYS / サイズ warning 閾値
├── exceptions/
│   └── cart_error_codes.py            # 変更: 4015xx サブカテゴリ追加（R-010）
├── models/
│   ├── documents/
│   │   └── cart_restore_log_document.py  # 新規: 監査レコード文書
│   └── repositories/
│       └── cart_restore_log_repository.py # 新規: log_cart_restore リポジトリ
└── services/
    ├── snapshot_service.py            # 新規: エンベロープ組み立て/検証/縮退（R-002/R-003/R-006）
    └── cart_service.py                # 変更: restore_cart_async（検証→衝突判定→再構築→監査）

services/cart/tests/
├── unit/        # 署名・正規化・エンベロープ・鍵世代のユニットテスト
├── integration/ # レスポンス付加 + restore 正常系/拒否系/衝突系
└── e2e/         # バックエンド切替の取引継続シナリオ + サイズ/レイテンシ計測
```

**Structure Decision**: 変更は cart サービスと kugel_common のみ（spec「影響するサービス」と一致）。新規ファイル 4、変更ファイル 7 程度の薄い追加で、既存の repository / transformer / dependency injection パターンをそのまま踏襲する。

## 確定した設計判断（spec「未解決事項」の解決）

| spec の未解決事項 | 決定 | 詳細 |
|---|---|---|
| 署名・正規化ユーティリティの置き場所 | 汎用部は kugel_common、ドメイン部は cart | [R-001](./research.md) |
| トランスポート表現 | エンベロープ + CartDocument JSON（専用スキーマなし）、レスポンスは `BaseCart.signed_snapshot` | [R-002](./research.md) |
| 照会系（GET）への付加 | 付加しない（変更系 + restore のみ） | [R-005](./research.md) |
| 生成失敗時の縮退方針 | 縮退許容（操作成功 + フィールド null + warning ログ）。構成エラーは起動時検出 | [R-006](./research.md) |
| 監査証跡の保存先 | テナント DB の新コレクション `log_cart_restore`（TTL なし） | [R-007](./research.md) |
| サイズ超過対策の判断基準 | gzip 後 15KB 超 or p95 +50ms 超で #146 にて対策検討。phase 1 は計測 + warning まで | [R-008](./research.md) |

補足の確定事項: restore エンドポイント形状 [R-009]、エラーコード割当て `4015xx` [R-010]（spec FR-009 の「30YYZZ」表記は実態に合わせて修正する）。

## 実装フェーズの概要（tasks.md の入力）

1. **基盤**: `hmac_signer.py`（commons）+ 鍵設定ロード + 起動時検証 — unit テスト先行
2. **スナップショット付加**: `snapshot_service.py` → transformer → 変更系 12 エンドポイントのレスポンス確認（integration）
3. **restore API**: エラーコード → 監査 repository → `restore_cart_async`（検証 → スコープ → 衝突 → 再構築）→ エンドポイント（integration: 正常/改ざん/スコープ違反/衝突/終端状態）
4. **e2e + 計測**: 二重バックエンド切替シナリオ、サイズ/レイテンシ実測（SC-005/SC-006）、結果を issue #148 へフィードバック

## Complexity Tracking

違反なし（記載不要）。
