# Tasks: 階段 10 使用體驗打磨收尾

**Input**: Design documents from `/specs/020-phase10-ux-polish/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/me-allocations-display-name.md, quickstart.md
**Tests**: 強制 TDD（Constitution Principle I）—— 先寫失敗測試再實作。

## Phase 1: Setup

- [X] T001 確認測試基線：`uv run pytest -q` 全綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 全綠、`uv run ruff check .` 無錯（退化比對基準，SC-006）。

## Phase 2: Foundational（阻擋 US1）

> `/me/allocations` 補 `display_name` 是 US1 卡片名稱的地基。

### Tests（先寫，須 Red）

- [X] T002 [P] 於 `tests/contract/test_me_allocations.py` 加測：成員有一張對應目錄 model 的分配 → `/me/allocations` 該筆含 `display_name` = 目錄顯示名稱；既有 `price`/欄位不變（FR-001）。
- [X] T003 [P] 同檔加測：分配的 model 不在目錄（orphan）→ `display_name` 為 `null`、不報錯（Edge）。

### Implementation

- [X] T004 在 `src/ai_api/api/me.py`：`_alloc_public` 加 `display_name` 參數並輸出；`list_my_allocations` 建 slug→display_name map（查 `model_catalog`，比照既有 `price_map`），傳入。orphan→None。
- [X] T005 跑 T002–T003 轉綠；確認既有 `/me/allocations` 測試零退化。

## Phase 3: User Story 1 — 分配卡片名稱 + 現價 (P1) 🎯 MVP

**Goal**: 「我的分配」卡片顯示 display_name（slug 為輔）+ 現價（每 1M），缺價目標「未定價」。
**Independent Test**: 有分配成員開儀表板 → 卡片見名稱與現價；orphan 退回 slug；無價目標未定價。

### Tests（先寫，須 Red）

- [X] T006 [P] [US1] 於 `frontend/src/__tests__/dashboard.test.tsx`（或新檔 `dashboard-cards.test.tsx`）加測：mock `/me/allocations` 回 `display_name` + `price` → 卡片顯示 display_name（slug 為輔）與現價（每 1M）；`price=null` → 「未定價」；`display_name=null` → 退回 slug。

### Implementation

- [X] T007 [US1] 在 `frontend/src/routes/dashboard.tsx`：Allocation 介面加 `display_name?: string | null`、`price?: {...} | null`；卡片標題以 display_name 為主（fallback `resource_model`）、slug 小字為輔；現價以 `lib/price-format` 的 `per1kToPer1m` 顯示每 1M（null→「未定價」）。
- [X] T008 [US1] 跑 T006 轉綠；`tsc --noEmit` 乾淨。

## Phase 4: User Story 4 — 呼叫端點單一可信來源 (P1)

**Goal**: dashboard 與「如何呼叫」範例的 base URL 來自單一 helper、一致。
**Independent Test**: 兩處顯示的網址相同且為實際可達端點。

### Tests（先寫，須 Red）

- [X] T009 [P] [US4] 建 `frontend/src/__tests__/api-base.test.ts`：`apiBaseUrl()` 回 `${window.location.origin}/v1`（mock location）。

### Implementation

- [X] T010 [US4] 新增 `frontend/src/lib/api-base.ts` 匯出 `apiBaseUrl()`；`dashboard.tsx`「API 端點」與 `components/api-usage-example.tsx` 皆改引用它（取代各自硬寫的 `window.location.origin`）。保留 dashboard 跨主機提示（`member.gateway_base_url`）。
- [X] T011 [US4] 跑 T009 + 既有 dashboard/catalog-detail 測試轉綠（確認 ApiUsageExample 仍正常）。

## Phase 5: User Story 2 — 可自助領取卡片可點進詳情 (P2)

**Goal**: claimable 卡片可點進 `/catalog/{slug}`，領取鈕不導頁。

### Tests（先寫，須 Red）

- [X] T012 [P] [US2] 於 `frontend/src/__tests__/dashboard-claim.test.tsx`（或既有）加測：點 claimable 卡片 → 導向 `/catalog/{slug}`；點「領取」鈕 → 觸發領取、不導頁。

### Implementation

- [X] T013 [US2] 在 `dashboard.tsx`：claimable 卡片外層包 Link 至 `/catalog/{slug}`；「領取」鈕 `onClick` 加 `e.stopPropagation()`（或置於 Link 外），避免誤觸導頁。
- [X] T014 [US2] 跑 T012 轉綠。

## Phase 6: User Story 3 — 新成員上手引導 (P2)

**Goal**: 無分配成員見三步引導；有分配則不顯示。

### Tests（先寫，須 Red）

- [X] T015 [P] [US3] 於 `dashboard.test.tsx` 加測：無分配（`/me/allocations` 回 []）→ 顯示三步引導文字；有分配 → 不顯示。

### Implementation

- [X] T016 [US3] 在 `dashboard.tsx` 空狀態加「① 領取憑證 ② 複製 ③ 貼進 Authorization」三步引導（既有空狀態文案旁或取代）。
- [X] T017 [US3] 跑 T015 轉綠。

## Phase 7: User Story 5 — admin 配額 Dialog (P3)

**Goal**: admin 調整配額用 shadcn Dialog 取代 `prompt()`。

### Tests（先寫，須 Red）

- [X] T018 [P] [US5] 建 `frontend/src/__tests__/admin-allocations-quota.test.tsx`：開「調整配額」→ 站內 Dialog 預填目前值；輸入非數字/負數被擋；有效值送出呼叫 `PATCH /admin/allocations/{id}`；空白＝無限額（送 null）。

### Implementation

- [X] T019 [US5] 在 `frontend/src/routes/admin/allocations.tsx`：把「調整配額」`prompt()` 改為 shadcn `Dialog` + 數字輸入（預填、驗證、空白=無限額），送出走既有 `patchMut`。
- [X] T020 [US5] 跑 T018 轉綠。

## Phase 8: User Story 6 — token 文案 (P3)

- [X] T021 [P] [US6] 於 `dashboard.test.tsx` 加測：token 提示文案含自助領取情境關鍵字。
- [X] T022 [US6] 在 `dashboard.tsx` 改 token 提示文案，涵蓋「自助領取」與「管理員分配」兩種來源；跑 T021 轉綠。

## Phase 9: Polish & Cross-cutting

- [X] T023 全套：`uv run pytest -q` 綠、`cd frontend && npx tsc --noEmit && npm test -- --run` 綠、`uv run ruff check .` 無錯；確認既有成員/管理員行為零退化（FR-008, SC-006）。
- [X] T024 確認無新 migration：`DATABASE_URL="sqlite+aiosqlite:////tmp/p020.db" uv run alembic upgrade head` 仍止於 0012。
- [X] T025 依 `quickstart.md` 手動走一遍：卡片名稱/現價、可自助領取導頁、三步引導、端點一致、admin 配額 Dialog、token 文案。

## Dependencies

- T001 基線最前。
- Phase 2（T002–T005）阻擋 US1（display_name）。其餘 US（4/2/3/5/6）彼此獨立、多在 `dashboard.tsx`，依序做避免同檔衝突。
- Phase 9 最後。

## Parallel 範例

- T002–T003（同檔不同測試）可並行。
- 各 US 的測試（T006/T009/T012/T015/T018/T021）撰寫獨立，可並行；但實作多動 `dashboard.tsx`，須依序套用避免衝突。

## MVP

**US1（卡片名稱+現價）+ US4（端點單一來源）= 可交付 MVP**：兩個 P1，直接回應「資訊易消化」與「複製即可用」。US2/US3/US5/US6 為遞增 polish。
