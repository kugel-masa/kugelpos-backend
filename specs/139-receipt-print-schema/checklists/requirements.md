# 仕様書品質チェックリスト: device-agnostic な印字データスキーマ（XML 撤去・JSON 化）

**目的**: 計画フェーズに進む前に仕様書の完全性と品質を検証する
**作成日**: 2026-06-07
**タイプ**: 機能要求
**フィーチャー**: [spec.md](../spec.md)（#139）

## 内容の品質

- [x] 実装の詳細（言語・フレームワーク）が spec に混入していない（pydantic 表現は contracts に分離）
- [x] ユーザー価値とビジネスニーズに焦点を当てている
- [x] すべての必須セクションが完成している

## 要件の完全性

- [x] `[要確認]` マーカーが残っていない（Clarifications で確定）
- [x] 要件がテスト可能で明確である（各 FR に受け入れ基準）
- [x] 成功基準が測定可能である（SC-001〜006）
- [x] すべての受け入れシナリオが定義されている（US1〜US4）
- [x] エッジケースが特定されている
- [x] スコープが明確に定義されている（Out of Scope で device-gateway/能力照会/冪等性を除外）
- [x] 依存関係が特定されている（stpos #316 流用元、Issue #139）

## kugelpos 固有の確定事項（stpos #316 からの再スコープ）

- [x] **DeviceGW API 契約・frontend パススルー契約はスコープ外**（消費者責務として短く参照）
- [x] **terminal の開閉店/現金レシートも JSON 化対象**（kugel_common XML 廃止に伴い必須）
- [x] **report の帳票レシート生成器（4 種）も JSON 化対象**（`AbstractReceiptData` 経由のため連動）
- [x] **R/J/RJ チャネルは kugelpos に存在しない** → FR-007 はチャネル軸を導入せず `journal_text` 維持に限定
- [x] **spec 番号 = issue 番号（139）** に統一（流用元 stpos の方式に合わせる）

## 備考

- 影響範囲: kugel_common + cart + terminal + journal + report。`receipt_text` 参照は 146 箇所（document/schema/transformer/pub-sub/テスト）。
- 印字生成器は計 7（cart×1, terminal×2, report×4）。基底 `AbstractReceiptData` の XML 撤去により全生成器が連動。
