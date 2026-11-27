# Specification Quality Checklist: 処理できなかったイベントを見えるようにし、直したあとに流し直せるようにする

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-25
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

- 既存の仕組みの名前（Slack の通知、API で提供すること）は、運用の担当者が使う手段として前提に書いた。どのサービスが記録と API を持つか、流し直しの渡し方（元のトピックへ出し直すか、受け手を直接呼ぶか）は plan で決める
- 既定値（まとめて通知する 5 分・10 件、まとめての流し直し 20 件、保持 90 日）は仮の値。clarify で見直せる
- 2026-11-27: デッドレターにするのを受け手自身（17 回の失敗で諦めて記録する）に改めた。RabbitMQ のデッドレターキューは記録できないときの最後の受け皿として残し、期限を付けない（FR-001・FR-002・FR-005・FR-018 を改訂、FR-022 を削除）
- 2026-11-27: Fable と Codex のレビューを反映した。本体は処理の結果だけを返す、定期の掃除（数え損ねと送り損ねた通知）、`_id` = イベント ID、`$literal`、照会の中身のマスク、まとめての流し直しは 202 で裏に回す（FR-003・FR-012・FR-017・SC-002・SC-003 を改訂）
