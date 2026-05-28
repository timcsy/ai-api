# Tasks: 憑證暫停 / 恢復

**Input**: Design documents from `/specs/019-allocation-pause-resume/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/pause-resume.md, quickstart.md
**Tests**: 強制 TDD（Constitution Principle I）—— 每個 user story 先寫失敗測試再實作。

## Phase 1: Setup

- [X] T001 確認測試基線：`uv run pytest -q` 全綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 全綠、`uv run ruff check .` 無錯（Docker 開著才跑得了 testcontainers 整合測試）。作為退化比對基準（SC-005）。

## Phase 2: Foundational（阻擋所有 user story）

> 新增三個 enum 列舉值是共同地基（皆 `native_enum=False`，免 migration）。

- [X] T002 [P] 在 `src/ai_api/models/allocation.py` 的 `AllocationStatus` 加 `paused = "paused"`。
- [X] T003 [P] 在 `src/ai_api/models/call_record.py` 的 `CallOutcome` 加 `rejected_paused = "rejected_paused"`。
- [X] T004 [P] 在 `src/ai_api/models/auth_audit.py` 的 `AuditEventType` 加 `allocation_paused` / `allocation_resumed`。

## Phase 3: User Story 1 — 暫停一把憑證 (P1) 🎯 MVP

**Goal**: admin 暫停 active 憑證 → 呼叫即時被擋（`allocation_paused`），token / 配額 / 鎖定不變。
**Independent Test**: 暫停一把 active 憑證 → 用同一 token 呼叫 proxy → 403 `allocation_paused`；憑證仍在、token 未變、未鎖定。

### Tests（先寫，須 Red）

- [X] T005 [P] [US1] 建 `tests/contract/test_allocation_pause_resume.py`：`POST /admin/allocations/{id}/pause` 對 active → 200、status=`paused`、寫稽核 `allocation_paused`（FR-001/006）。
- [X] T006 [P] [US1] 於同檔加測：pause 後該 allocation 的 token_prefix / `quota_tokens_per_month` 不變、且**無** reclaim lock（FR-003/004, US1-AS3）。
- [X] T007 [P] [US1] 建 `tests/integration/test_proxy_paused.py`：對 `paused` 憑證用原 token 呼叫 `/v1/chat/completions` → 403 + error code `allocation_paused`，CallRecord 記為 `rejected_paused`（FR-005/008, US1-AS2）。

### Implementation

- [X] T008 [US1] 在 `src/ai_api/services/allocations.py` 加 `pause(allocation_id, *, paused_by=None)`：查 allocation；僅當 `status==active` 切為 `paused` 並寫稽核 `allocation_paused`；非 active 拋可辨識錯誤（供端點轉 409）；**不**動 token / 配額 / 不呼叫 `_lock_reclaim`。
- [X] T009 [US1] 在 `src/ai_api/proxy/router.py` 狀態檢查段加 `status == "paused"` → 回 `allocation_paused`（403）；error map 加 `"allocation_paused": CallOutcome.rejected_paused`（沿用既有「先 lookup 後檢查」順序，紀錄帶 allocation_id）。
- [X] T010 [US1] 在 `src/ai_api/api/allocations.py` 加 `POST /allocations/{id}/pause`（`require_admin_token` router）：比照 `unquarantine`，200 回更新後 allocation、404 不存在、409 非 active（依 `contracts/pause-resume.md`）。
- [X] T011 [US1] 跑 T005–T007 轉綠。

## Phase 4: User Story 2 — 恢復一把憑證 (P1)

**Goal**: admin 恢復 paused 憑證 → 同一把 token 立即又能呼叫。
**Independent Test**: 恢復一把 paused 憑證 → 用**原 token** 呼叫 proxy → 成功（不需 rotate）。

### Tests（先寫，須 Red）

- [X] T012 [P] [US2] 於 `tests/contract/test_allocation_pause_resume.py` 加測：`POST /admin/allocations/{id}/resume` 對 paused → 200、status=`active`、寫稽核 `allocation_resumed`（FR-002/006）。
- [X] T013 [P] [US2] 於 `tests/integration/test_proxy_paused.py` 加測：pause → resume 後，用**原 token**（非新發）呼叫 proxy → 成功（FR-003, US2-AS2）。

### Implementation

- [X] T014 [US2] 在 `src/ai_api/services/allocations.py` 加 `resume(allocation_id, *, resumed_by=None)`：僅當 `status==paused` 切回 `active` 並寫稽核 `allocation_resumed`；非 paused 拋可辨識錯誤。
- [X] T015 [US2] 在 `src/ai_api/api/allocations.py` 加 `POST /allocations/{id}/resume`：200 / 404 / 409（非 paused）。
- [X] T016 [US2] 跑 T012–T013 轉綠。

## Phase 5: User Story 3 — 狀態機防呆 (P2)

**Goal**: pause/resume 只在 active↔paused 間轉移，對 revoked/quarantined/已是目標狀態一律拒絕、零改動。
**Independent Test**: 對 revoked / quarantined / 已 paused / 已 active 嘗試非法 pause/resume → 409、目標憑證不變。

### Tests（先寫，須 Red）

- [X] T017 [P] [US3] 於 `tests/contract/test_allocation_pause_resume.py` 加測：pause 對 revoked / quarantined / 已 paused → 409、allocation 不變（FR-007, US3-AS1/AS3）。
- [X] T018 [P] [US3] 加測：resume 對 active / revoked / quarantined → 409、不變（FR-007, US3-AS2）。
- [X] T019 [P] [US3] 加測：pause/resume 對不存在 id → 404。

### Implementation

- [X] T020 [US3] 確認 T008/T014 的狀態守衛 + T010/T015 端點把服務層錯誤轉 409；補齊缺口使 T017–T019 轉綠（多為驗證既有實作，必要時微調錯誤碼/訊息對齊契約）。

## Phase 6: User Story 1+2 前端

**Goal**: admin 在分配列/詳情可暫停/恢復，文案與撤回區分。

### Tests（先寫，須 Red）

- [X] T021 [P] [US1] 建 `frontend/src/__tests__/admin-allocations-pause.test.tsx`：mock 分配列，active 顯「暫停」、paused 顯「恢復」+ 狀態徽章；點「暫停」呼叫 `POST .../pause`、點「恢復」呼叫 `.../resume`；文案與「撤回」可區分（US1/US2, Edge）。

### Implementation

- [X] T022 [US1] 在 `frontend/src/routes/admin/allocations.tsx` 加暫停/恢復：active→「暫停」鈕（呼叫 `/admin/allocations/{id}/pause`）、paused→「恢復」鈕（`/resume`）+ paused 狀態徽章；invalidate 分配 query；與「撤回」並列、文案明確區分（暫停可逆/保留 token；撤回終局）。
- [X] T023 [P] [US1] 在 `frontend/src/routes/admin/member-detail.tsx` 的分配列同樣加暫停/恢復（次要，複用同 mutation 模式）。
- [X] T024 [US2] 跑 T021 轉綠；`tsc --noEmit` 乾淨。

## Phase 7: Polish & Cross-cutting

- [X] T025 全套：`uv run pytest -q` 綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 綠、`uv run ruff check .` 無錯；確認 revoke / unquarantine / quota / usage 零退化（FR-009, SC-005）。
- [X] T026 確認無新 migration：`DATABASE_URL="sqlite+aiosqlite:////tmp/p019.db" uv run alembic upgrade head` 仍止於 0012。
- [X] T027 依 `quickstart.md` 手動走一遍：暫停 → 原 token 呼叫被擋 → 恢復 → 原 token 又能用 → 非法狀態 409；UI 暫停/恢復文案與撤回可區分。

## Dependencies

- T001 基線在最前。
- Phase 2（T002–T004）阻擋所有 story（enum 值是地基）。
- US1（T005–T011）為 MVP；US2（T012–T016）依賴 US1 的 pause 存在（才測得到 pause→resume）；US3（T017–T020）依賴 US1/US2 的服務 + 端點。
- 前端（T021–T024）依賴後端端點（T010/T015）。
- Phase 7 在最後。

## Parallel 範例

- T002–T004（三個不同 model 檔的 enum 值）可並行。
- T005–T007（不同測試檔/函式）可並行撰寫。
- T017–T019 同檔不同測試函式，可並行。

## MVP

**US1（暫停）+ US2（恢復）= 可交付 MVP**：可逆性是全部價值，兩者一體。US3 為正確性護欄（多為驗證既有狀態守衛）。
