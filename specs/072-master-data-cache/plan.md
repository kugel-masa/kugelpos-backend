# Implementation Plan: Cart Master-Data 共通キャッシュ基盤

**Branch**: `072-master-data-cache` | **Date**: 2026-05-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/072-master-data-cache/spec.md`
**Related Issue**: [#125](https://github.com/kugel-masa/kugelpos-backend/issues/125)

## Summary

カートサービスは商品 / 支払 / 販促 / 設定 / 税の各マスタを高頻度で参照するが、現状はリポジトリごとにアドホックなキャッシュ実装（インスタンス変数、TTL あり/なし混在、無効化 API なし）が分散している。本フィーチャはキャッシュ責務を共通基底クラスに集約し、Dapr ステートストア (Redis) でワーカー横断キャッシュを実現する。各リポジトリは `_fetch_one` / `_fetch_list`（取得処理）のみを宣言し、キーの組み立て・TTL・直列化・無効化・障害時フォールバックは基底に委譲する。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, Pydantic v2, Motor (async MongoDB), Dapr (via `DaprClientHelper` 既存ラッパ)
**Storage**:
- 一次データ: MongoDB（既存。マスタ実体は master-data サービス管理）
- キャッシュ層: Dapr State Store (Redis) — 新規コンポーネント `masterstore` (Redis databaseIndex=3) を追加
**Testing**: pytest + pytest-asyncio（3 階層: `tests/unit/`, `tests/integration/`, `tests/e2e/`）
**Target Platform**: Linux コンテナ（Docker Compose / Azure Container Apps）
**Project Type**: Microservices（cart サービスへの追加。共通バックエンドは commons パッケージへ）
**Performance Goals**:
- キャッシュヒット時のマスタ参照レイテンシを直接フェッチ比 80% 以上短縮（SC-002）
- 同一論理キーへの並列参照でもマスタへの実フェッチはフレッシュネス期間あたり最大 1 回（SC-001）
**Constraints**:
- キャッシュバックエンド障害時もカート操作は継続成功（SC-003）
- マルチテナント・マルチストア間でキャッシュ値の漏洩 0 件（SC-006 / SC-006b）
- 「該当なし」応答はキャッシュしない（FR-013 / SC-009）
**Scale/Scope**:
- 改修対象: 6 リポジトリ（Item Web/Grpc, Payment, Promotion, Settings, Tax）+ factory
- 新規: 共通キャッシュバックエンド 3 種（Abstract / InMemory / DaprState）+ master-data 基底クラス + Dapr コンポーネント 1 件
- フェーズ分割: 4 段階リリース（基盤 → ItemMaster → 残り → 旧設定除去）

## Constitution Check

*GATE: Phase 0 開始前に必須。Phase 1 設計後に再評価。*

### 適用される原則

- **言語規則 (Constitution 0)**:
  - 仕様書、計画書、タスク、ドキュメント類は**日本語**で作成
  - コード内のコメント・ログメッセージは**英語**で記述

### Gate 評価

| 項目 | 状態 | 備考 |
|---|---|---|
| 成果物の言語（仕様・計画・タスク・ドキュメント）が日本語であること | PASS | spec.md / plan.md / 以降の成果物すべて日本語で記述 |
| コード内コメント・ログメッセージが英語であること | 設計上 PASS（実装時遵守） | 各サブクラス・基底クラス・キャッシュバックエンドで `# English`, `logger.info("...")` を徹底 |
| その他の原則 (I-V) | N/A | constitution.md がテンプレ未確定のため評価対象なし |

**結論**: 違反なし。Phase 0 へ進行可。

## Project Structure

### Documentation (this feature)

```text
specs/072-master-data-cache/
├── plan.md              # 本ファイル
├── spec.md              # 仕様書
├── research.md          # Phase 0 出力（未解決事項の決着）
├── data-model.md        # Phase 1 出力（クラス / インターフェース構造）
├── quickstart.md        # Phase 1 出力（実装〜検証の動線）
├── contracts/           # Phase 1 出力（基底クラス・バックエンドのインターフェース定義）
├── checklists/
│   └── requirements.md  # /speckit.specify で生成済み
└── tasks.md             # Phase 2 出力（/speckit.tasks で生成）
```

### Source Code (repository root)

本フィーチャは既存のマイクロサービス構成（kugelpos-backend）の cart サービスへの追加。新規ファイル・改修ファイルの配置:

```text
services/
├── commons/                                         # 共有ライブラリ
│   └── src/kugel_common/utils/cache/                # 【新規】キャッシュバックエンド層
│       ├── __init__.py
│       ├── cache_backend.py                         # AbstractCacheBackend
│       ├── in_memory_cache_backend.py               # テスト・フォールバック用
│       └── dapr_state_cache_backend.py              # Dapr 経由 Redis バックエンド
│
├── cart/
│   └── app/
│       ├── models/repositories/
│       │   ├── abstract_master_data_repository.py   # 【新規】共通基底クラス
│       │   ├── item_master_web_repository.py        # 【改修】基底継承化
│       │   ├── item_master_grpc_repository.py       # 【改修】同上
│       │   ├── item_master_repository_factory.py    # 【改修】cache_backend 受け渡し
│       │   ├── payment_master_web_repository.py     # 【改修】
│       │   ├── promotion_master_web_repository.py   # 【改修】
│       │   ├── settings_master_web_repository.py    # 【改修】
│       │   └── tax_master_repository.py             # 【改修】
│       ├── config/settings_cart.py                  # 【改修】設定追加・旧フラグ撤去
│       ├── main.py                                  # 【改修】lifespan で backend を 1 個生成
│       └── dependencies/                            # 【改修】DI で backend を各リポジトリへ
│
└── dapr/components/
    └── masterstore.yaml                             # 【新規】Redis databaseIndex=3, TTL 既定 300s

tests/
├── services/commons/tests/unit/utils/cache/         # 【新規】バックエンド単体テスト
└── services/cart/tests/
    ├── unit/repositories/                            # 【改修】既存テストを新シグネチャに合わせ更新
    ├── integration/                                  # 【新規】DaprStateCacheBackend の実バックエンド検証
    └── e2e/                                          # 既存シナリオがリグレッションなく通ること
```

**Structure Decision**: 既存のマイクロサービス構成を維持。汎用部品（キャッシュバックエンド）は `services/commons/` 配下に置き、master-data リポジトリの基底クラス自体は cart 固有概念のため `services/cart/app/models/repositories/` 配下に配置する。他サービスへの横展開は Out of Scope。

## Complexity Tracking

> Constitution Check に違反なし。本セクションは記入不要。

