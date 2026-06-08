# Specification Quality Checklist: responses 支援判斷（實測 + 手動雙來源）

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-08
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)（以 WHAT 表述；端點/欄位僅在 Entities/Assumptions）
- [x] Focused on user value and business needs（不誤擋、admin 確定知道、成員看得到 Agent 相容）
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain（雙來源、軟化閘門、手動優先、解耦皆於對話收斂）
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified（未測未手動、同步不洗掉、衝突手動優先、不支援回真實錯誤）
- [x] Scope is clearly bounded（只動軸③、無 migration/套件、不改計費）
- [x] Dependencies and assumptions identified（既有 responses 管線 + 測試連線模式、欄位承載）

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows（US1 軟化閘門、US2 實測、US3 手動覆寫、US4 目錄徽章）
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 通過，0 個 NEEDS CLARIFICATION。可進 `/speckit.plan`。
- 規劃重點：軟化 `model_supports_responses`（responses.py:277 閘門）→ 只在手動 no 時擋；新增「測試 responses」端點（沿用 `admin_providers.py` test-connection 模式）；responses 狀態 + 來源以既有欄位承載（無 migration）；移除 `litellm_registry` 的 mode→responses 衍生 + LiteLLM 採納改 merge-preserve；目錄徽章 + 成員 facet（追既有 capabilities sink）。
