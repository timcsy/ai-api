# Tasks: 成員自助用量總覽

**Input**: Design documents from `/specs/018-member-usage-overview/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/me-usage.md, quickstart.md
**Tests**: 強制 TDD（Constitution Principle I）—— 每個 user story 先寫失敗測試再實作。

## Phase 1: Setup

- [X] T001 確認測試基線：`uv run pytest -q` 全綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 全綠、`uv run ruff check .` 無錯，作為退化比對基準（SC-005）。

## Phase 2: Foundational（阻擋 US1 / US2）

> `aggregate_usage` 的 member-scope 是 summary 與 breakdown 共同地基，先做。

### Tests（先寫，須 Red）

- [X] T002 [P] 建 `tests/integration/test_usage_member_scope.py`：建立成員 A、B 各自分配與成功呼叫，斷言 `aggregate_usage(group_by="member", member_id=A)` 只含 A 的數字、完全不含 B（FR-002, SC-003）。
- [X] T003 [P] 於同檔加測：`group_by` 三種值（member / allocation / model）+ `member_id` 皆正確過濾到該成員；不傳 `member_id` 時行為與既有完全一致（FR-003, FR-008）。
- [X] T004 [P] 於同檔加測：只計 `outcome=success`，失敗呼叫不計入 token / 花費 / 次數（FR-005, Edge）。

### Implementation

- [X] T005 在 `src/ai_api/services/usage.py` 的 `aggregate_usage` 加可選參數 `member_id: str | None = None`；非空時於 `base_filters` 加 `Allocation.member_id == member_id`（三分支皆已 join `Allocation`）；保持各分支獨立變數名（避免多分支 select 型別衝突）。
- [X] T006 跑 T002–T004 轉綠；執行既有 `tests/integration/test_aggregation.py` 等 admin usage 測試確認零退化。

## Phase 3: User Story 1 — 儀表板整體用量摘要 (P1) 🎯 MVP

**Goal**: 成員在儀表板一眼看到本月總 token / 估算花費 / 呼叫次數（含未定價低估提示），嚴格只看自己。
**Independent Test**: 有數筆呼叫的成員，`/me/usage` 的 summary = 其所有成功呼叫加總；儀表板顯示該摘要；無呼叫顯示 0。

### Tests（先寫，須 Red）

- [X] T007 [P] [US1] 建 `tests/integration/test_me_usage.py`：以成員 session 打 `GET /me/usage`，回 `summary`（total/prompt/completion tokens、total_cost_usd、call_count），數字 = 該成員所有成功呼叫加總；無呼叫成員回全 0（FR-001, SC-002, Edge）。
- [X] T008 [P] [US1] 於同檔加測：成員 A 的 `/me/usage` 完全不含 B 的用量，且無任何 query 參數能取得他人資料（FR-002, SC-003）。
- [X] T009 [P] [US1] 於同檔加測：未登入 → 401（授權）。
- [X] T010 [P] [US1] 於同檔加測：存在「成功、`total_tokens>0` 但 `cost_usd` NULL/0」的呼叫時 `summary.has_unpriced=true`；全部有價目時為 `false`（FR-006, SC-004）。
- [X] T011 [P] [US1] 建 `frontend/src/__tests__/dashboard-usage.test.tsx`：mock `/me/usage`，斷言儀表板渲染總 token / 估算花費 / 呼叫次數；`has_unpriced=true` 時顯示「含未定價項目，花費為低估」（SC-001, FR-006）。

### Implementation

- [X] T012 [US1] 在 `src/ai_api/api/me.py` 新增 `GET /me/usage`（`current_member` 依賴，唯讀）：預設區間本月 UTC 月初→now(UTC)，沿用 admin 的 `from<to` / 範圍上限驗證；回 `{from,to,summary}`。summary 由 `aggregate_usage(group_by="member", member_id=member.id)` 單列 + 未定價 count 組成；依 `contracts/me-usage.md`。
- [X] T013 [US1] 在 `src/ai_api/services/usage.py` 加未定價計數 helper（成功 + `total_tokens>0` + `cost_usd` IS NULL/0 + member + 區間），供 `has_unpriced`。
- [X] T014 [US1] 在 `frontend/src/routes/dashboard.tsx` 頂部加「用量摘要」區塊：TanStack Query 取 `/me/usage`，顯示本月總 token / 估算花費 / 呼叫次數；`has_unpriced` 時顯示低估提示；載入 / 空狀態處理。
- [X] T015 [US1] 跑 T007–T011 轉綠；`tsc --noEmit` 乾淨。

## Phase 4: User Story 2 — 用量明細與拆分 (P2)

**Goal**: 成員把用量按 model / 分配拆分，並選時間區間。
**Independent Test**: `group_by` 各列加總 = summary；切區間數字隨之變。

### Tests（先寫，須 Red）

- [X] T016 [P] [US2] 於 `tests/integration/test_me_usage.py` 加測：`GET /me/usage?group_by=model` 回 `breakdown[]`，各列 token/花費/次數加總 = `summary`（FR-003, SC-002）。
- [X] T017 [P] [US2] 加測：`group_by=allocation` 只含該成員自己的分配；`group_by=member` 回 422（契約）。
- [X] T018 [P] [US2] 加測：指定 `from`/`to` 區間數字依區間重算；測試走 `client.get(..., params=...)` 讓 httpx URL-encode（FR-004，借鏡 ISO datetime quote 教訓）。

### Implementation

- [X] T019 [US2] 擴充 `GET /me/usage`（`api/me.py`）：接受 `group_by=model|allocation`（拒 `member`），帶 `group_by` 時附 `breakdown`（`aggregate_usage(group_by=..., member_id=member.id)`）。
- [X] T020 [US2] 在 `frontend/src/routes/dashboard.tsx` 加時間區間切換（本月 / 近 7 天 / 近 30 天）與 model/分配拆分檢視（表格或列）。
- [X] T021 [US2] 跑 T016–T018 + 前端轉綠。

## Phase 5: User Story 3 — 配額視角 (P3)

**Goal**: 成員看到各分配「本月已用 / 配額」（含池動態配額），無限額顯示為無上限。
**Independent Test**: 有月配額的分配顯示已用/配額與比例；無限額顯示無上限。

### Tests（先寫，須 Red）

- [X] T022 [P] [US3] 於 `frontend/src/__tests__/dashboard-usage.test.tsx`（或新檔）加測：分配有配額時顯示「已用 X / 配額 Y」與比例條；配額為無限額時顯示無上限、不顯示比例條（FR-007）。

### Implementation

- [X] T023 [US3] 在 `frontend/src/routes/dashboard.tsx` 結合 `/me/usage?group_by=allocation`（本月已用）與既有分配的 `quota_tokens_per_month`，於分配呈現「本月已用 / 配額」+ 比例；無限額特例。
- [X] T024 [US3] 跑 T022 轉綠。

## Phase 6: Polish & Cross-cutting

- [X] T025 全套：`uv run pytest -q` 綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 綠、`uv run ruff check .` 無錯；確認既有測試零退化（SC-005, FR-008）。
- [X] T026 依 `quickstart.md` 手動走一遍：真實成員登入 → 產生用量 → 儀表板摘要 / 拆分 / 區間 / 配額 / 未定價提示。
- [X] T027 確認無 schema 變更：`DATABASE_URL="sqlite+aiosqlite:////tmp/x.db" uv run alembic upgrade head` 仍乾淨（本功能不新增 migration）。

## Dependencies

- T001 基線在最前。
- Phase 2（T002–T006）阻擋 US1、US2（兩者都依賴 `aggregate_usage(member_id=)`）。
- US1（T007–T015）為 MVP；US2（T016–T021）依賴 US1 的端點存在（T012）後擴充；US3（T022–T024）依賴前端摘要區塊（T014）。
- Phase 6 在所有 story 後。

## Parallel 範例

- T002–T004（同檔不同測試函式，邏輯獨立）可一起寫。
- T007–T011 跨後端/前端測試，可並行撰寫（標 [P]）。
- T016–T018 同檔不同測試函式，可並行。

## MVP

**US1（儀表板整體用量摘要）= 可交付 MVP**：成員終於能一眼看到自己用了多少、花了多少。US2（拆分/區間）、US3（配額視角）為遞增強化。
