# Specification Quality Checklist: 毎リクエストでのカートスナップショット提示とサーバ側キャッシュの権威降格（client-carried cart phase 2）

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 当初の [NEEDS CLARIFICATION] 3 件（FR-004 キャッシュ形態 / FR-005 乖離ルール / FR-008 互換方針）は 2026-06-13 のセッションで解決し、Clarifications に記録した。
- 設計の核は (1) 採番を `(business_counter, seq)` 複合の持ち回りにして交換・オフライン確定・ステートレスを両立、(2) 確定の二重計上対策を「下流 `cart_id` 冪等 upsert（後勝ち）」に置き、確定ゲートを設けない、(3) 前提 A-1（1カート=1クライアント）により乖離を異常系に落とし提示スナップショットを正とする、の 3 点。
- 移行方針（FR-008）は**デュアルモード**で確定（2026-06-13）。あり経路=スナップショット権威（ステートレス）、なし経路=サーバ側キャッシュ権威（phase 1 挙動）。キャッシュ撤去・CB/フォールバック除去は移行完了後の後続作業（本スコープ外）。
- 連番は `(business_counter, seq)` 複合（開設セッション内連続）。「端末永久の単一通し整数」は採らない（Out of Scope に明記）。要件が後者に変わる場合は採番方式の再設計が必要。
- ruff 等のコード言及は実装指定ではなく既存システムの文脈参照（phase 1 spec と同水準）。
