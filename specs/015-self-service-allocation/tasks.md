# Tasks: 自助領取憑證 (Self-Service Allocation)

**Input**: Design documents from `/specs/015-self-service-allocation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/{me-allocations,admin-self-service}.yaml, quickstart.md

**Tests**: INCLUDED — Constitution I (Test-First) NON-NEGOTIABLE. Each behavioural task's test is written first.

**Organization**: By user story. US1 (admin opt-in) + US2 (member claim) are both P1 — MVP needs both. US3 (revoke-lock + unlock, P2) is the security increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete deps). Paths relative to repo root.

---

## Phase 1: Setup

- [X] T001 Confirm baseline green: `uv run pytest -q` (311 expected) + `cd frontend && npm test -- --run` (69 expected); record in PR

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + ORM + `origin` plumbing every story depends on.

- [X] T002 [P] Add `self_service_enabled` (bool, default false) + `self_service_default_quota` (int nullable) columns to `src/ai_api/models/model_catalog.py`
- [X] T003 [P] Add `AllocationOrigin` enum (`admin`/`self_service`) + `origin` column (default `admin`) to `src/ai_api/models/allocation.py`; export `AllocationOrigin` from `src/ai_api/models/__init__.py`
- [X] T004 [P] Create `SelfServiceReclaimLock` model in `src/ai_api/models/self_service_lock.py` (composite PK `(member_id, model_slug)`, `locked_at`, `locked_by`, `INDEX(member_id)`); export from `src/ai_api/models/__init__.py`
- [X] T005 Add 3 values to `AuditEventType` in `src/ai_api/models/auth_audit.py`: `self_service_claimed`, `self_service_reclaim_locked`, `self_service_unlocked`
- [X] T006 Write Alembic migration `alembic/versions/0012_self_service.py` (down_revision `0011_tag_rules`): catalog +2 cols (server_default) + allocations.origin (server_default `admin`) + create `self_service_reclaim_locks`; verify `alembic upgrade head` then `downgrade -1` round-trips on SQLite
- [X] T007 Extend `AllocationService.create` in `src/ai_api/services/allocations.py` to accept `origin: AllocationOrigin = AllocationOrigin.admin` and persist it; existing callers unchanged

**Checkpoint**: schema migrated, models importable, create() accepts origin.

---

## Phase 3: User Story 1 — Admin 逐 model 開放自助領取並設配額 (Priority: P1) 🎯 MVP

**Goal**: admin opens/closes self-service per model with a required default quota.

**Independent Test**: PATCH a model to `enabled=true, default_quota=50000` → reflected; `enabled=true` without quota → 422; another model stays closed.

### Tests (write first)

- [X] T008 [P] [US1] Contract test `tests/contract/test_admin_self_service.py`: PATCH `/admin/catalog/models/{slug}/self-service` 200 (enable+quota / disable), 422 `quota_required` (enable w/o quota), 404 unknown slug; admin-only (401/403)

### Implementation

- [X] T009 [US1] Create `src/ai_api/api/admin_self_service.py` with `PATCH /catalog/models/{slug:path}/self-service` (validate quota required when enabled); register router in `src/ai_api/main.py`
- [X] T010 [US1] On config change write audit `model_access_policy_updated` with `details.self_service` (in the endpoint or a small service helper)
- [X] T011 [US1] Frontend: add self-service toggle + default-quota input to the model admin settings (`frontend/src/routes/admin/model-detail.tsx` or `model-access.tsx`); TanStack mutation against the PATCH endpoint

**Checkpoint**: admin can open/close + set quota. Nothing claimable by members yet.

---

## Phase 4: User Story 2 — 成員一鍵自助領取憑證 (Priority: P1)

**Goal**: an allowed member self-claims an allocation for an opened model and can call `/v1`.

**Independent Test**: with a model `self_service_enabled` + member access-allowed, `POST /me/allocations {model}` → 201 + one-time token + `origin=self_service` active allocation; disallowed → 403; closed model → 403; second claim → 409.

### Tests (write first)

- [X] T012 [P] [US2] Unit test `tests/unit/test_self_service_eligibility.py`: `SelfServiceService.check` truth table — member_inactive / model_not_self_service / model_forbidden (reuse evaluate_visibility) / already_claimed / reclaim_locked / eligible
- [X] T013 [P] [US2] Contract test `tests/contract/test_me_allocations.py`: `POST /me/allocations` 201 (token+allocation), 403 (`model_forbidden`/`model_not_self_service`/`member_inactive`), 409 (`already_claimed`), 404 (unknown slug); requires session + CSRF; GET still returns `origin`

### Implementation

- [X] T014 [US2] Create `src/ai_api/services/self_service.py`: `check(member, model) -> ClaimEligibility` (reuse `evaluate_visibility` + active-self-service + lock checks per data-model order) and `claim(member, model)` (calls `AllocationService.create(origin=self_service, quota=model.self_service_default_quota)`); `list_claimable(member)` for dashboard
- [X] T015 [US2] Add `POST /me/allocations` to `src/ai_api/api/me.py` (`current_member` + `require_csrf`); map eligibility reasons → 403/409/404 per contract; return one-time token
- [X] T016 [US2] Frontend: member dashboard (`frontend/src/routes/dashboard.tsx`) — "可自助領取" section listing claimable models + 「領取憑證」button + one-time token reveal dialog; surface 403/409 reasons

**Checkpoint**: MVP complete — admin opens (US1) + member self-claims and calls (US2).

---

## Phase 5: User Story 3 — 撤回後鎖定重領，需 admin 解鎖 (Priority: P2)

**Goal**: revoking a self-service allocation locks re-claim until admin unlocks.

**Independent Test**: claim → revoke → re-claim 403 `reclaim_locked` → admin unlock → claim succeeds; audit shows claimed/locked/unlocked.

### Tests (write first)

- [X] T017 [P] [US3] Integration test `tests/integration/test_self_service_flow.py`: end-to-end claim → call `/v1` 200 → admin revoke → re-claim 403 `reclaim_locked` → `GET /admin/self-service-locks` shows it → unlock → claim 201; assert audit events `self_service_claimed` / `self_service_reclaim_locked` / `self_service_unlocked`; assert revoking an `origin=admin` allocation does NOT create a lock

### Implementation

- [X] T018 [US3] Hook `AllocationService.revoke` in `src/ai_api/services/allocations.py`: after revoke, if `allocation.origin == self_service` upsert `SelfServiceReclaimLock(member_id, resource_model)` + audit `self_service_reclaim_locked`
- [X] T019 [US3] Add `GET /admin/self-service-locks` (list w/ member email) + `POST /admin/self-service-locks/unlock` (delete lock, idempotent, audit `self_service_unlocked`) to `src/ai_api/api/admin_self_service.py`
- [X] T020 [US3] In `self_service.py`: `check` returns `reclaim_locked` when a lock exists (already in T014 order — finalize); `claim` emits audit `self_service_claimed` on success
- [X] T021 [P] [US3] Frontend: dashboard shows `reclaim_locked` state (需 admin 解鎖) instead of claim button; admin unlock UI in 觀測 → 分配 (`frontend/src/routes/admin/allocations.tsx`) — lock list + 「解鎖」

**Checkpoint**: revocation has teeth; self-service can't bypass it.

---

## Phase 6: Polish & Cross-Cutting

- [X] T022 [P] Run quickstart.md scenarios 1–4 in browser; confirm SC-001 (30s/3-click claim), SC-002/003 (policy + opt-in 100%), SC-004 (re-claim blocked), SC-006 (1-min config)
- [X] T023 Full regression: `uv run pytest -q` (≥ 311 + new) + `cd frontend && npm test -- --run` (≥ 69) — verifies SC-005 zero regression (origin default admin; quota pool / revoke / proxy unchanged)
- [X] T024 [P] Frontend tests: dashboard claim flow (`frontend/src/__tests__/`) + admin self-service config render/validation

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: strict.
- **Phase 2** blocks all stories (T002–T007).
- **US1 (Phase 3)** and **US2 (Phase 4)** depend only on Phase 2. US2's eligibility reads `self_service_enabled` (column from T002), set directly in test setup — so US2 is testable without US1's endpoint. Both P1; do US1 then US2 for MVP.
- **US3 (Phase 5)** depends on US2 (needs self-service allocations + the eligibility `check` to extend with lock). T018 hook needs `origin` (T003) + lock table (T004).
- **Phase 6** depends on US1–US3.

## Parallel Opportunities

- **Phase 2**: T002 ∥ T003 ∥ T004 (different model files); T005 independent; T006 after T002–T005; T007 after T003.
- **US2 tests**: T012 ∥ T013 (different files), write together first.
- **US3**: T021 frontend ∥ backend T018–T020 once contracts fixed.
- **Polish**: T022 ∥ T024; T023 after both.

## Implementation Strategy

**MVP = US1 + US2** (admin opens + member claims + calls). US3 (revoke-lock) is the security hardening increment; ship after MVP. TDD per task: write the listed test, watch it fail, implement to green. Commit messages end with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
