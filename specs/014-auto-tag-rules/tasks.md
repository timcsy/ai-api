# Tasks: Rule-Based Auto-Tagging

**Input**: Design documents from `/specs/014-auto-tag-rules/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tag-rules.yaml, quickstart.md

**Tests**: INCLUDED — Constitution I (Test-First) is NON-NEGOTIABLE for this repo. Each behavioural task has its test written first.

**Organization**: Grouped by user story. US1 + US2 are both P1 (MVP needs both: define rules AND apply at registration). US3 (P2) is incremental.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- Paths are relative to repo root. Backend `src/ai_api/`, frontend `frontend/src/`, tests `tests/`.

---

## Phase 1: Setup

**Purpose**: No new tooling — sits on the existing Phase 5/5.1 stack. Just establish the baseline.

- [X] T001 Confirm baseline green before starting: `uv run pytest -q` (277 expected) and `cd frontend && npm test -- --run` (65 expected); record counts in the PR description

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + ORM + the `source` plumbing that EVERY story depends on. No story can proceed until this phase is done.

- [X] T002 [P] Create `MatcherType` enum + `TagRule` ORM model in `src/ai_api/models/tag_rule.py` (fields per data-model.md: id ULID PK, order_index int indexed, matcher_type enum, pattern str(256), tag str(64), enabled bool default true, created_at, created_by); export from `src/ai_api/models/__init__.py`
- [X] T003 Add `source` (enum `manual`/`auto`, not null, server_default `manual`) + `rule_id` (str(32) nullable) columns to the MemberTag model in `src/ai_api/models/member_tag.py`
- [X] T004 Write Alembic migration `alembic/versions/0011_tag_rules.py` (down_revision → latest head): create `tag_rules` table + `INDEX(enabled, order_index)`; add `member_tags.source` (server_default `manual`) + `member_tags.rule_id` (nullable); verify `uv run alembic upgrade head` then `downgrade -1` round-trips on SQLite
- [X] T005 Extend `MemberTagService.add` in `src/ai_api/services/member_tags.py` to accept `source: str = "manual"` and `rule_id: str | None = None`, persisting them; keep existing callers unchanged (default = manual)

**Checkpoint**: Schema migrated, models importable, `add()` accepts source — stories can now build in parallel.

---

## Phase 3: User Story 1 — Admin 定義學生/老師自動分類規則 (Priority: P1) 🎯 MVP

**Goal**: Admin can CRUD + reorder ordered rules, with regex guarded, and dry-run an email via "測試 email" without creating a member.

**Independent Test**: Build 2 rules (學號 regex → student; `always` → teacher) via the UI/API, POST `/admin/tag-rules/test` with `b10901234@school.edu` → `student` and `prof.wang@school.edu` → `teacher`; submitting `(a+)+$` is rejected with `unsafe_regex`.

### Tests (write first — must fail before implementation)

- [X] T006 [P] [US1] Unit tests for the regex guard in `tests/unit/test_regex_guard.py`: valid pattern passes; un-anchored pattern auto-wrapped to `^(?:...)$`; nested-quantifier `(a+)+$` rejected; `(.*)*` rejected; > 10 quantifiers rejected; uncompilable pattern rejected
- [X] T007 [P] [US1] Unit tests for matchers + evaluate in `tests/unit/test_tag_rule_eval.py`: `email_localpart_regex` with `local_part[:64]` truncation; `email_suffix`/`email_domain` case-insensitive; `always` always matches; first-match-wins ordering; no-match → None; disabled rules skipped
- [X] T008 [P] [US1] Contract tests for all endpoints in `tests/contract/test_admin_tag_rules.py`: GET (ordered), POST 201 + 422 (`invalid_tag`/`unsafe_regex`/`invalid_matcher`), PATCH 200/404/422, DELETE 204/404, POST /reorder 200/422 (id-set mismatch), POST /test 200; all require admin (401/403)

### Implementation

- [X] T009 [US1] Implement regex guard in `src/ai_api/services/tag_rules.py`: `guard_regex(pattern) -> anchored_pattern` (compile, auto-anchor to `^(?:...)$`, reject nested quantifiers / > 10 quantifiers, raise `UnsafeRegexError`); makes T006 pass
- [X] T010 [US1] Implement matchers + `evaluate(email, rules) -> RuleMatch` in `src/ai_api/services/tag_rules.py` (4 matcher_type branches per research.md R3/R4, `local_part[:64]`, case-insensitive, first-match-wins); makes T007 pass
- [X] T011 [US1] Implement `TagRuleService` CRUD + reorder in `src/ai_api/services/tag_rules.py`: `create` (append last order_index, validate tag regex + guard regex for `email_localpart_regex`), `list` (order_index ASC), `update`, `delete`, `reorder` (full id-array rewrite, 422 on set mismatch)
- [X] T012 [US1] Create `src/ai_api/api/admin_tag_rules.py` with 6 operations (GET/POST `/tag-rules`, PATCH/DELETE `/tag-rules/{id}`, POST `/tag-rules/reorder`, POST `/tag-rules/test`) per contracts/tag-rules.yaml; `/test` calls `evaluate` with no DB write; register router in `src/ai_api/main.py` (or existing admin router aggregator); makes T008 pass
- [X] T013 [US1] Create frontend rule management page `frontend/src/routes/admin/tag-rules.tsx`: list (ordered) + create/edit/delete/enable-toggle + reorder + "測試 email" box; TanStack Query hooks against the 6 endpoints; surface `unsafe_regex`/`invalid_tag` errors inline
- [X] T014 [US1] Add entry into the rule page from the Tag area in `frontend/src/routes/admin/` (route `/admin/tag/rules` + a button/tab on the existing Tag page) **without adding a 7th sub-nav item** (per Phase 5.1 principle, research.md R8); wire route in `frontend/src/App.tsx`

**Checkpoint**: Admin can fully manage rules and dry-run emails. Rules exist but are not yet applied at registration.

---

## Phase 4: User Story 2 — 新成員首次註冊自動貼 tag (Priority: P1)

**Goal**: At first member creation (OIDC self-register + admin-create), the rule engine runs first-match-wins and auto-tags the member with `source=auto`.

**Independent Test**: With rules set, register `b10901234@school.edu` via OIDC → member has `student` tag, `source=auto`; `prof.wang@school.edu` → `teacher`; re-login does NOT re-run rules.

### Tests (write first)

- [X] T015 [P] [US2] Integration test `tests/integration/test_auto_tag_on_register.py`: (a) OIDC first-register learns tag via `_find_or_create_oidc_member`; (b) existing member re-login does NOT re-run; (c) `MemberService.create` (admin local member) also auto-tags; (d) no-match + no `always` → no auto tag (not an error); (e) auto tag flows through access policy identically to manual (set model restricted+allowed=[student], assert visibility)

### Implementation

- [X] T016 [US2] Add `apply_to_new_member(session, member)` to `src/ai_api/services/tag_rules.py`: load enabled rules ordered, `evaluate(member.email)`, on match call `MemberTagService.add(member_id, [tag], source="auto", rule_id=rule.id)` (idempotent); on rule-load/eval failure log warning and return without crashing registration (Edge: invalid stored pattern)
- [X] T017 [US2] Call `apply_to_new_member` from `_find_or_create_oidc_member` in `src/ai_api/api/auth.py` — ONLY in the `new = Member(...)` first-register branch, after flush; existing-member path untouched
- [X] T018 [US2] Call `apply_to_new_member` from `MemberService.create` in `src/ai_api/services/members.py` after the member is flushed/created

**Checkpoint**: MVP complete — rules defined (US1) AND applied at registration (US2). Auto tags drive access policy with zero changes to existing access/diagnose code.

---

## Phase 5: User Story 3 — Auto tag 的辨識與稽核 (Priority: P2)

**Goal**: Admin can visually distinguish auto vs manual tags, removal is not re-applied on re-login, and auto-tagging is audited with source + rule id.

**Independent Test**: `b10901234`'s `student` tag shows an "自動" marker; admin removes it, re-login does not re-add; audit shows `member_tag_added` with `source=auto, rule_id=...`.

### Tests (write first)

- [X] T019 [P] [US3] Test in `tests/integration/test_auto_tag_on_register.py` (or new audit test) asserting the `member_tag_added` audit event `details` carries `source=auto` and `rule_id` when auto-tagging; manual add carries `source=manual`

### Implementation

- [X] T020 [US3] In `apply_to_new_member` / the audit write path, ensure the `member_tag_added` audit `details` includes `{source: "auto", rule_id: ...}` (manual path stays `source=manual`); makes T019 pass
- [X] T021 [P] [US3] Expose `source` (+ optional `rule_id`) on the member-tag read DTO so the frontend can render it (check `src/ai_api/api/admin_tags.py` / member-detail serializer); confirm access-policy/diagnose serializers are NOT changed (SC-005)
- [X] T022 [US3] Add an "自動" badge to auto tags in the member tag display: `frontend/src/routes/admin/member-detail.tsx` (and member list inline tag chips if shown), visually distinct from manual

**Checkpoint**: Auto tags are identifiable, auditable, and manually overridable.

---

## Phase 6: Polish & Cross-Cutting

- [X] T023 [P] Run quickstart.md scenarios 1–4 manually (browser) and confirm SC-001 (2 rules < 3 min), SC-002 (100% correct), SC-003 (malicious regex 100% blocked), SC-006 (auto vs manual distinguishable)
- [X] T024 Full regression: `uv run pytest -q` (≥ 277 + new) and `cd frontend && npm test -- --run` (≥ 65) both green — verifies SC-005 zero regression on access policy / diagnose / tag detail
- [X] T025 [P] Frontend page tests for `tag-rules.tsx` in `frontend/src/routes/admin/__tests__/` (render list, create validation error surfaced, "測試 email" result rendered)

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)**: strict, blocking.
- **Phase 2** blocks all user stories (T002–T005 must finish first).
- **US1 (Phase 3)** and **US2 (Phase 4)** both depend only on Phase 2 — but US2's `apply_to_new_member` (T016) reuses `evaluate` (T010, in US1). So **T010 before T016**. Practically: do US1 then US2 (both P1, both needed for MVP).
- **US3 (Phase 5)** depends on US2 (needs auto-tagging to exist to mark/audit it).
- **Phase 6 (Polish)** depends on US1–US3.

### Story-level independence

- US1 is independently testable end-to-end (CRUD + dry-run) without US2.
- US2 needs `evaluate` from US1 but is otherwise its own registration path.
- US3 layers identification/audit on US2's output.

---

## Parallel Opportunities

**Phase 2**: T002 (tag_rule.py) ∥ T003 (member_tag.py) — different files. T004 after both; T005 independent file.

**US1 tests** (all [P], different files, write together first):
```
T006 tests/unit/test_regex_guard.py
T007 tests/unit/test_tag_rule_eval.py
T008 tests/contract/test_admin_tag_rules.py
```
**US1 impl**: T009→T010→T011→T012 are same-file (`tag_rules.py`) / sequential; T013, T014 frontend can start once T012's contract is fixed.

**US3**: T021 (backend DTO) ∥ T022 (frontend badge) after T020.

**Polish**: T023 ∥ T025 ∥ (T024 after both).

---

## Implementation Strategy

**MVP = US1 + US2** (both P1). Stop-and-ship point: admin defines guarded rules and new registrations auto-tag correctly, feeding existing access policy. US3 (P2 identification/audit polish) and Phase 6 follow incrementally.

**TDD per task**: write the listed test task first, watch it fail, then the implementation task makes it pass. Commit message ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
