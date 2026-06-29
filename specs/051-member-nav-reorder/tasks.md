---
description: "Task list for 會員導覽重排——凸顯「應用」"
---

# Tasks: 會員導覽重排——凸顯「應用」

**Input**: Design documents from `/specs/051-member-nav-reorder/`
**Prerequisites**: spec.md（必要）、plan.md（精簡版）。無 data-model/contracts（純呈現層）。

**Tests**: constitution 強制 TDD——先寫斷言**新順序**的失敗測試（既有 nav 測試只斷言「存在」、不斷言順序，故順序測試是新的、會先紅），再重排。

**Organization**: 依 user story（P1/P2）。範圍極小：核心是單一陣列重排。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 跑基線 `cd frontend && npx vitest run src/__tests__/app-shell.test.tsx src/__tests__/mobile-nav.test.tsx` 確認起點綠（之後比對零回歸）。

---

## Phase 2: Foundational

*(無；本功能只動單一 `MAIN_NAV` 陣列 + 對應測試，無跨 story 阻斷性前置。)*

---

## Phase 3: User Story 1 — 會員一眼找到「應用」入口（Priority: P1）🎯 MVP

**Goal**: 會員主導覽順序＝**儀表板 → 應用 → 模型目錄 → 分配 → 用量 → 金鑰**，「應用」第二位；標籤/路由不變。

**Independent Test**: 以一般會員身分檢視桌機主導覽，斷言項目**依序**為新順序、「應用」在第二位、各項 `to`（路由）不變。

### Tests for US1（先寫、必須先紅）

- [X] T002 [US1] 在 `frontend/src/__tests__/app-shell.test.tsx` 加一個**斷言順序**的測試：render app-shell（一般會員），取桌機主導覽的會員項目文字陣列，斷言**嚴格等於** `["我的儀表板","應用","模型目錄","分配","用量","金鑰"]`（用例如 `getAllByRole("link")` 過濾會員項目、比對 textContent 順序）。先紅（現況「應用」在最後）。

### Implementation for US1

- [X] T003 [US1] 在 `frontend/src/components/app-shell.tsx` 重排 `MAIN_NAV` 陣列為：`/dashboard` → `/apps` → `/catalog` → `/allocations` → `/usage` → `/keys`（`/admin` 維持原位、`adminOnly` 不動）；**只改順序**，每筆的 `to`/`label`/`adminOnly` 文字逐字不變。
- [X] T004 [US1] 跑 `cd frontend && npx vitest run src/__tests__/app-shell.test.tsx` 轉綠 + `npx tsc --noEmit`。

**Checkpoint US1**: 桌機導覽新順序、應用第二位、路由不變。

---

## Phase 4: User Story 2 — 桌機與手機看到一致的新順序（Priority: P2）

**Goal**: 手機收合 `Sheet` 的順序與桌機一致（皆新順序）。

**Independent Test**: 手機寬度展開抽屜，斷言項目順序＝新順序，與桌機相同。

**依賴**: US1 的 `MAIN_NAV` 重排已同時讓手機生效（共用來源）；本 story ＝補上手機面的順序斷言（防未來回歸）。

### Tests for US2（先寫、必須先紅前先確認）

- [X] T005 [P] [US2] 在 `frontend/src/__tests__/mobile-nav.test.tsx` 把既有「存在性」斷言**升級為順序斷言**：展開抽屜後取會員項目文字陣列，斷言嚴格等於新順序 `["我的儀表板","應用","模型目錄","分配","用量","金鑰"]`。（T003 完成後此測試應綠；若在 T003 前寫則先紅。）

### Implementation for US2

*(無新實作——US1 的單一 `MAIN_NAV` 重排已涵蓋手機；本 story 只固化順序測試。)*

- [X] T006 [US2] 跑 `cd frontend && npx vitest run src/__tests__/mobile-nav.test.tsx` 轉綠。

**Checkpoint US2**: 桌機+手機順序一致、有測試固化。

---

## Phase 5: Polish & 上線

- [X] T007 全前端零回歸：`cd frontend && npx vitest run && npx tsc --noEmit && npm run build`（確認其他斷言 nav「存在」的測試〔apps-*, dashboard-* 等〕不受影響）。
- [X] T008 PR + squash-merge 到 main（CI 全綠）；**純前端**部署：helm `--reuse-values` + `--set image.tag=sha-d104990`（backend 不動）`--set frontend.image.tag=sha-<new>` + `migrationJob.enabled=false` + storedResponseCleanup。部署後 SPA 200、肉眼確認導覽新順序。
- [X] T009 知識同步：把 `knowledge/vision.md` 階段 37 標 ✅（本刀 = 純重排已上線）；本分支已含的階段 37 stub 引用修正一併帶入該 PR。

---

## Dependencies & Execution Order

- **T001**（基線）→ 之前。
- **US1（T002→T003→T004）**：T002 測試先紅 → T003 重排 → T004 綠。MVP、可獨立交付。
- **US2（T005→T006）**：依賴 T003 的重排；T005 升級手機順序測試、T006 驗綠。
- **Polish（T007→T008→T009）**：全綠 → 部署 → 知識同步。

### 平行機會
- 範圍太小、序列為主。`T005 [P]`（手機測試）可在 T003 後與 T004 並行寫。

## Implementation Strategy

- **MVP = US1**：單一 `MAIN_NAV` 重排即達成桌機+手機新順序；US2 只是把手機順序固化成測試（防回歸）。
- **零回歸鐵律**：標籤/路由逐字不變；既有斷言「存在」的 nav 測試 git diff 僅限「升級成順序斷言」那一處，其餘不動。
- 一個 PR、純前端、frontend-only 部署。
