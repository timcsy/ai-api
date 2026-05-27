# Tasks: 價目表管理 UI (Price List Admin)

**Input**: Design documents from `/specs/016-price-list-admin/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-prices.yaml, quickstart.md

**Tests**: INCLUDED — Constitution I (Test-First) NON-NEGOTIABLE. Each behavioural task's test is written first.

**Organization**: By user story. US1 (view + unpriced) + US2 (add version) are both P1 = MVP. US3 (history) is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete deps). Paths relative to repo root.
- **No migration / no schema change** — reuses existing `price_list`.

---

## Phase 1: Setup

- [X] T001 Confirm baseline green: `uv run pytest -q` (335 expected) + `cd frontend && npm test -- --run` (72 expected); record in PR

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the one shared model change. No table/migration.

- [X] T002 Add `price_version_added` to `AuditEventType` in `src/ai_api/models/auth_audit.py` (no migration — `native_enum=False` VARCHAR(64))

**Checkpoint**: audit value available; pricing backend (price_list + lookup) already exists from Phase 3a.

---

## Phase 3: User Story 1 — Admin 檢視價目與未定價模型 (Priority: P1) 🎯 MVP

**Goal**: list catalog models with current effective price or "未定價".

**Independent Test**: GET `/admin/prices` returns one row per catalog model with current input/output price or `priced:false`; an unpriced new model shows `priced:false`.

### Tests (write first)

- [X] T003 [P] [US1] Unit test `tests/unit/test_price_current_selection.py`: pure current-version selection — multiple versions → latest `effective_from <= now`; future-dated version excluded; no versions → None (unpriced); tz-aware comparison
- [X] T004 [P] [US1] Contract test `tests/contract/test_admin_prices.py` (GET): `/admin/prices` returns catalog rows with `current`/`priced`; priced vs unpriced models reflected; admin-only (401/403)

### Implementation

- [X] T005 [US1] Add `list_catalog_prices(session, now)` to `src/ai_api/services/pricing.py` (join catalog × current price per `provider + slug.split("/",1)[-1]` key; Decimal→str); reuse the same point-in-time selection as `lookup_price_for_call`
- [X] T006 [US1] Create `src/ai_api/api/admin_prices.py` with `GET /prices`; register router in `src/ai_api/main.py` (prefix `/admin`, require_admin_token)
- [X] T007 [US1] Frontend `frontend/src/routes/admin/prices.tsx`: table of catalog models × current price / 「未定價」badge; TanStack query on `/admin/prices`
- [X] T008 [US1] Add 「價目」tab to `frontend/src/routes/admin/observability.tsx` + nested route `observability/prices` in `frontend/src/App.tsx` (no new top-level sub-nav)

**Checkpoint**: admin can see every model's price + spot unpriced ones.

---

## Phase 4: User Story 2 — Admin 新增價目版本 (Priority: P1)

**Goal**: add an append-only price version (point-in-time), without touching history.

**Independent Test**: POST `/admin/prices` for an unpriced model → 201; the model then shows the new price; a `/v1` call on it yields cost > 0; duplicate (provider, model, effective_from) → 409; negative price → 422.

### Tests (write first)

- [X] T009 [P] [US2] Contract test in `tests/contract/test_admin_prices.py` (POST): 201 create; 409 `duplicate_version`; 422 `invalid_price` (negative); tz-aware `effective_from` accepted
- [X] T010 [P] [US2] Integration test `tests/integration/test_price_admin_flow.py`: unpriced model → POST price → `/v1` call cost > 0 (patch litellm); add a later-effective doubled price → new call ~2×, **earlier call's recorded cost unchanged** (point-in-time, SC-004)

### Implementation

- [X] T011 [US2] Add `create_version(session, *, provider, model, input_per_1k, output_per_1k, effective_from, source_note, created_by)` to `src/ai_api/services/pricing.py`: validate non-negative + tz-aware; on `IntegrityError` (unique) raise a typed error; write audit `price_version_added`
- [X] T012 [US2] Add `POST /prices` to `src/ai_api/api/admin_prices.py`: map typed errors → 409 `duplicate_version` / 422 `invalid_price`; return created `PriceVersion`
- [X] T013 [US2] Frontend: 「新增價格」dialog in `prices.tsx` (input/output unit price, effective date, source note); pre-fill provider + model key from the selected catalog row; surface 409/422 inline; invalidate price queries on success

**Checkpoint**: MVP complete — admin views (US1) and fixes unpriced models (US2); cost stops being 0.

---

## Phase 5: User Story 3 — Admin 檢視某模型的歷史價格 (Priority: P2)

**Goal**: audit all price versions for a model, marking current vs scheduled.

**Independent Test**: GET `/admin/prices/history?provider=&model=` returns all versions newest-first with `is_current`; a future-dated version is not current.

### Tests (write first)

- [X] T014 [P] [US3] Contract test in `tests/contract/test_admin_prices.py` (history): `/admin/prices/history` returns versions desc by `effective_from`, exactly one `is_current` when a `<=now` version exists; future version `is_current:false`

### Implementation

- [X] T015 [US3] Add `list_history(session, provider, model)` to `src/ai_api/services/pricing.py` (all versions desc; compute `is_current` per point-in-time) + `GET /prices/history` in `src/ai_api/api/admin_prices.py`
- [X] T016 [P] [US3] Frontend: expandable history per model row in `prices.tsx` (versions list + 「目前生效」/「排程生效」markers)

**Checkpoint**: price history is auditable.

---

## Phase 6: Polish & Cross-Cutting

- [X] T017 [P] Run quickstart.md scenarios 1–4 in browser; confirm SC-001 (unpriced 100% flagged), SC-002 (2-min add), SC-003 (cost > 0 after pricing), SC-004 (history cost unchanged)
- [X] T018 Full regression: `uv run pytest -q` (≥ 335 + new) + `cd frontend && npm test -- --run` (≥ 72) — verifies SC-006 (pricing / usage / CLI zero regression)
- [X] T019 [P] Frontend test `frontend/src/__tests__/`: prices page renders priced/unpriced rows + add-version validation error surfaced

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: strict. **Phase 2 (T002)** blocks US2 (audit).
- **US1 (Phase 3)**: needs nothing beyond existing pricing backend; delivers view. US2's `is_current`/selection reuses US1's selection logic (T005) — so **T005 before T011/T015** (same file `pricing.py`).
- **US2 (Phase 4)**: needs T002 (audit) + T005 (selection). Both P1 → do US1 then US2 for MVP.
- **US3 (Phase 5)**: needs T005 selection; otherwise independent (history view).
- **Phase 6**: after US1–US3.

## Parallel Opportunities

- **US1 tests**: T003 ∥ T004 (different files), write together first.
- **US1 impl**: T005→T006 sequential (service then endpoint); T007, T008 frontend after T006 contract fixed.
- **US2 tests**: T009 ∥ T010.
- **`pricing.py` tasks** (T005, T011, T015) are same file → sequential among themselves.
- **Polish**: T017 ∥ T019; T018 after both.

## Implementation Strategy

**MVP = US1 + US2** (see prices + unpriced; add prices → cost stops being 0). US3 (history) and Polish follow. TDD per task: write the listed test, watch it fail, implement to green. Commit messages end with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
