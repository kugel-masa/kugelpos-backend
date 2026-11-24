# Specification Quality Checklist: 精算を report が確定するスナップショットにする

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-24
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

- サービスの名前（terminal・report・cart）とエラーコード（`412101`・`413007`）は、利用者と運用者がすでに使っている名前・番号なので残した。保存の仕方、索引、エンドポイントのパス、使う技術は書いていない（plan で決める）
- 利用者が決めたこと: report に届かないときは精算を断る（FR-010）、確定集計は 5 種類すべて（FR-008）、名乗った件数は任意で足す（FR-004・FR-013）、精算前の確認を含める（FR-021）
- 合意した既定: 理論在高は売上レポートの現金の欄と同じ式で 1 か所に置く（FR-007）、店舗・期間の日報は未精算があれば断る（FR-016）、速報はその場で集計（FR-018）、救済・強制・複数拠点は扱わない（Out of Scope）
- 配備より前に精算を終えた営業の日報が出せなくなることは、意図した挙動として Assumptions と後方互換性に書いた。plan で、配備の手順として利用者に確かめる
