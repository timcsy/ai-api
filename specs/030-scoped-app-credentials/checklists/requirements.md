# Specification Quality Checklist: Scoped application credentials（M:N）

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - 註：以 WHAT 表述（key 綁一組分配、依 model 歸戶、不提權）；schema/migration 屬假設層的「重構含 migration」陳述，未綁技術選型。
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain（治理權、Codex 不特別過濾、原則 1 措辭皆已於 knowie-next 收斂）
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic（以使用者可觀察結果表述）
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified（空 scope、分配被停、同 model 兩分配、未知 model、rotate）
- [x] Scope is clearly bounded（〈Assumptions〉含「不做」清單）
- [x] Dependencies and assumptions identified（依賴階段 18 憑證、階段 19 device-flow；需 migration，Postgres 驗）

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows（US1 多 model key、US2 歸戶+拒絕、US3 零回歸、US4 scope 編輯、US5 治理、US6 Codex+收尾A）
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 通過。可進 `/speckit.plan`。
- 規劃重點：憑證 1:N→M:N 的 schema/migration（去 `allocation_id`、加 `member_id` + 憑證-分配 join，既有列搬 scope；**Postgres 整合測試固化零回歸**）；`lookup_by_token` 改為 model-aware 解析（熱路徑、需零回歸契約）；scope CRUD + 擁有者/admin 邊界 + 稽核；清單升成員層；device-flow 多選 + 移除舊 Codex 分頁。
