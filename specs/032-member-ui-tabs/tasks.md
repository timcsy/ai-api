# Tasks: 會員介面分頁化 + 金鑰/分配 概念釐清

**Input**: Design documents from `/specs/032-member-ui-tabs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-routes.md, quickstart.md

**Tests**: 本功能採嚴格 TDD（憲章 I，NON-NEGOTIABLE）。每個 User Story 先寫/改失敗測試（紅）再實作（綠）。

**Organization**: 任務依 User Story 分組，各自可獨立實作與測試。**純前端**，全部路徑在 `frontend/`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔、無未完成相依）
- **[Story]**: US1–US4；Setup/Foundational/Polish 無 Story 標籤

## Path Conventions

Web app：前端在 `frontend/src/`、測試在 `frontend/src/__tests__/`。後端完全不動。

---

## Phase 1: Setup

- [X] T001 確認前端測試可跑：`cd frontend && npm test -- --run app-shell` 應綠（基線），確認 Vitest + RTL 環境正常、無未提交髒測試。

---

## Phase 2: Foundational（阻斷所有 User Story 的前置）

**Purpose**: 抽出可重用的展示元件，讓各頁成為薄殼。這些抽取**不改行為**，把 dashboard 既有 section 原樣搬成獨立元件。

- [X] T002 [P] 新建 `frontend/src/components/api-endpoint-card.tsx`：把 `routes/dashboard.tsx` 的「API 端點」卡 + 其後 token 提示 `Alert` 原樣抽成 `<ApiEndpointCard />`（用 `useAuth()` 取 `member`、`apiBaseUrl()`）。不改文案、不改邏輯。
- [X] T003 [P] 新建 `frontend/src/components/allocation-list.tsx`：把 `routes/dashboard.tsx` 的「可自助領取」section + 「我的分配」section（含 `includeRevoked` switch、`claimableQuery`、`claimMut`、`usageByAlloc`、token reveal dialog、空狀態三步）整段抽成 `<AllocationList />`。行為完全保留。
- [X] T004 確認既有自足元件免改即可重用：`UsageSummary`、`MemberUsageCharts`、`TimeRangeSelect`、`CodexInstallCard`、`AppCredentialsCard`（本階段只確認 import 路徑與 props，不改它們）。

**Checkpoint**: 抽取後 dashboard 仍可暫時 import 這些元件保持原樣綠燈（US2 才正式精簡）。

---

## Phase 3: User Story 1 — 會員分頁導覽（Priority: P1）🎯 MVP

**Goal**: 頂部導覽出現「我的儀表板/金鑰/分配/用量/模型目錄」，3 個新頁各為獨立可深連結路由。

**Independent Test**: 以會員登入 → 見 5 導覽項 → 點/直開 `/keys`、`/allocations`、`/usage` 各載入；`/dashboard/allocations/:id` 仍可達。

### Tests（先紅）

- [X] T005 [P] [US1] 改 `frontend/src/__tests__/app-shell.test.tsx`：斷言會員見 5 導覽項（我的儀表板/金鑰/分配/用量/模型目錄），點「金鑰」「分配」「用量」分別導到 `/keys`、`/allocations`、`/usage`。
- [X] T006 [P] [US1] 改 `frontend/src/__tests__/mobile-nav.test.tsx`：斷言手機 `Sheet` 選單含同 5 項。
- [X] T007 [P] [US1] 新建 `frontend/src/__tests__/keys-page.test.tsx`：render at `/keys` → 見 API 端點卡 + 應用金鑰表格 + 安裝 Codex。
- [X] T008 [P] [US1] 新建 `frontend/src/__tests__/allocations-page.test.tsx`：render at `/allocations` → 見「我的分配」卡列（mock `/me/allocations`）。
- [X] T009 [P] [US1] 新建 `frontend/src/__tests__/usage-page.test.tsx`：render at `/usage` → 見用量摘要 + 圖表（mock `/me/usage`）。
- [X] T010 [P] [US1] 改 `frontend/src/__tests__/legacy-redirects.test.tsx`（或既有 dashboard 測試）：斷言 `/dashboard/allocations/<id>` 仍渲染 `AllocationDetailPage`。

### Implementation（後綠）

- [X] T011 [P] [US1] 新建 `frontend/src/routes/keys.tsx`（`KeysPage`）：薄殼，組合 `<ApiEndpointCard />` + `<AppCredentialsCard />` + `<CodexInstallCard />`。頁首標題「金鑰」。
- [X] T012 [P] [US1] 新建 `frontend/src/routes/allocations.tsx`（`AllocationsPage`）：薄殼，渲染 `<AllocationList />`。頁首標題「分配」。
- [X] T013 [P] [US1] 新建 `frontend/src/routes/usage.tsx`（`UsagePage`）：薄殼，含 `UsageSummary` + `TimeRangeSelect`（自管 `usageRange` state）+ `MemberUsageCharts`。頁首標題「用量」。
- [X] T014 [US1] 改 `frontend/src/App.tsx`：在 `ProtectedRoute > AppShell` 下、admin 區之前加 `/keys`、`/allocations`、`/usage` 三條路由（import 對應頁）。`/dashboard/allocations/:id` 保持原樣。
- [X] T015 [US1] 改 `frontend/src/components/app-shell.tsx`：`MAIN_NAV` 在「我的儀表板」與「模型目錄」之間插入 `{to:"/keys",label:"金鑰"}`、`{to:"/allocations",label:"分配"}`、`{to:"/usage",label:"用量"}`（adminOnly:false）。桌機與手機選單共用，自動生效。

**Checkpoint**: US1 測試全綠；5 分頁可導航、可深連結、可重新整理。此為可獨立交付的 MVP。

---

## Phase 4: User Story 2 — 精簡儀表板（總覽）（Priority: P1）

**Goal**: `/dashboard` 只剩摘要（用量/花費 + 金鑰數 + 分配數 + 快速接入 + 待辦），不再混入金鑰表格/圖表/分配列。

**Independent Test**: 開 `/dashboard` → 只見摘要區塊；無金鑰帳號見「去建立金鑰」連 `/keys`；有可領取見連 `/allocations`。

### Tests（先紅）

- [X] T016 [P] [US2] 改 `frontend/src/__tests__/dashboard.test.tsx`：斷言 `/dashboard` **存在**用量/花費摘要、活躍金鑰數、活躍分配數、安裝 Codex 快速接入；**不存在**應用金鑰完整表格、「用量圖表」標題、「我的分配」整列卡片。
- [X] T017 [P] [US2] 在 `dashboard.test.tsx` 加：無金鑰時待辦連 `/keys`（mock `/me/credentials` 空）；有可領取時待辦連 `/allocations`（mock `/me/claimable-models` 含 `claimable`）。

### Implementation（後綠）

- [X] T018 [US2] 新建 `frontend/src/components/member-overview.tsx`（`<MemberOverview />`）：用既有 query（`/me/allocations`、`/me/credentials`、`/me/claimable-models`、`UsageSummary` 或 `/me/usage`）算活躍金鑰數/分配數與待辦；含本月用量/花費摘要、快速接入（精簡 `CodexInstallCard` 或連 `/keys`）、待辦提示（連 `/keys`、`/allocations`）。各摘要可點擊連對應分頁。
- [X] T019 [US2] 改 `frontend/src/routes/dashboard.tsx`：移除已搬走的區塊（API 端點卡、`AppCredentialsCard`、`UsageSummary`+圖表、可自助領取、我的分配、相關 dialog/state/query），改為渲染 `<MemberOverview />`。保留歡迎標題「我的儀表板」。清掉變死的 import。

**Checkpoint**: US2 測試全綠；dashboard 為精簡總覽，US1 分頁仍正常（內容無重複殘留）。

---

## Phase 5: User Story 3 — 分配 vs 金鑰 一句話講清（Priority: P1）

**Goal**: 分配頁與金鑰頁各放一句白話解釋。

**Independent Test**: 開 `/allocations` 與 `/keys` → 各見「分配＝你能用哪些模型；金鑰＝拿來連線的鑰匙」。

### Tests（先紅）

- [X] T020 [P] [US3] 在 `frontend/src/__tests__/allocations-page.test.tsx` 加：頁首見「分配＝…金鑰＝…」說明（matcher 命中含「分配」與「金鑰」之解釋句）。
- [X] T021 [P] [US3] 在 `frontend/src/__tests__/keys-page.test.tsx` 加：頁首見同一句說明。

### Implementation（後綠）

- [X] T022 [P] [US3] 改 `frontend/src/routes/allocations.tsx`：頁首加說明列（`Alert` 或 `p.text-muted-foreground`）：「分配＝你能用哪些模型；金鑰＝拿來連線的鑰匙」。
- [X] T023 [P] [US3] 改 `frontend/src/routes/keys.tsx`：頁首加同一句說明列。

**Checkpoint**: US3 測試全綠。

---

## Phase 6: User Story 4 — 金鑰卡「編輯」合一 + Rotate 用詞統一（Priority: P2）

**Goal**: 金鑰卡「改名」+「編輯 model」併為單一「編輯」（name+scope 同送 PATCH）；admin Provider 頁英文「Rotate」中文化。

**Independent Test**: 金鑰卡操作列只剩「編輯/重新產生/撤回」，編輯可同時改名+改 model；admin Provider 頁無英文「Rotate」。

### Tests（先紅）

- [X] T024 [P] [US4] 新建/改 `frontend/src/__tests__/app-credentials-card.test.tsx`（或 `dashboard-cards.test.tsx` 對應段）：斷言操作列只有「編輯/重新產生/撤回」（無「改名」「編輯 model」兩顆）；點「編輯」→ 改名 + 變更勾選 → 儲存 → 發出**單一** `PATCH /me/credentials/{id}`，body 同時含 `name` 與 `add`/`remove` 差集。
- [X] T025 [P] [US4] 新建/改 `frontend/src/__tests__/providers-rotate-label.test.tsx`（或既有 providers 測試）：斷言 `/admin/providers` 無 `getByText("Rotate")`，有中文等義按鈕「重新產生金鑰」。

### Implementation（後綠）

- [X] T026 [US4] 改 `frontend/src/components/app-credentials-card.tsx`：把「改名」「編輯 model」兩顆按鈕併為單一「編輯」；合併 rename + edit-scope 兩個 dialog 為一個（名稱 `Input` + 可用 model checkbox）；「儲存」計算 scope 差集（add/remove）與 name 是否變更，送單一 `PATCH`（後端已支援同送，見 `test_credential_rename.py`）。移除 `renameTarget`/`renameName`/`renameMut` 與獨立 edit dialog 的冗餘 state。「重新產生」「撤回」維持獨立。
- [X] T027 [P] [US4] 改 `frontend/src/routes/admin/providers.tsx`：對外文案中文化——按鈕 `Rotate`→「重新產生金鑰」、dialog 標題 `Rotate Credential`→「重新產生上游金鑰」、submit `Rotate`→「重新產生」、toast「Rotate 失敗」→「重新產生失敗」。保留 `rotateMut`/`rotateForm`/`rotateSchema`/API path 等識別字不變。

**Checkpoint**: US4 測試全綠。

---

## Phase 7: Polish & Cross-Cutting

- [X] T028 [P] RWD 檢查（360px）：頂部 5 項導覽 + 手機 `Sheet` 選單不溢出；各新頁沿用既有容器，無水平捲動異常（quickstart 步驟 7）。
- [X] T029 [P] 清除死碼：確認 `dashboard.tsx` 不再 import 已搬走元件；`api-endpoint-card`/`allocation-list` 無重複定義；`npm run lint` 與 `tsc --noEmit` 無錯。
- [X] T030 全量前端測試綠：`cd frontend && npm test -- --run`（含改動與新檔）。
- [ ] T031 部署：等 CI 測試 + image build **皆綠**後，依 memory `deployment-topology` 升級指令 bump `frontend.image.tag`（後端維持上一個 sha；本功能無 migration → 不加 `migrationJob.enabled`）。部署後 smoke：壞 token 打 `/v1/chat/completions` 仍 401（零後端回歸）。

---

## Dependencies & Execution Order

```
Setup(T001)
  └─ Foundational(T002–T004)         # 抽元件，阻斷所有 US
       ├─ US1(T005–T015) 🎯 MVP      # 導覽 + 3 新頁（依賴抽出的元件）
       │    └─ US2(T016–T019)        # 精簡 dashboard（依賴新頁已承接內容，避免重複）
       ├─ US3(T020–T023)             # 一句解釋（依賴 US1 的頁存在）
       └─ US4(T024–T027)             # 編輯合一 + Rotate（獨立於導覽，可平行於 US1 之後）
            └─ Polish(T028–T031)
```

- **US2 依賴 US1**：dashboard 精簡前，內容須先在新頁有家（否則功能遺失）。
- **US3 依賴 US1**：解釋句加在 US1 建好的 `/allocations`、`/keys` 頁。
- **US4 獨立**：金鑰卡編輯合一 + Rotate 中文化不碰導覽，Foundational 後即可動；但建議 US1→US2→US3→US4 依序交付以利測試隔離。

## Parallel Opportunities

- **Foundational**: T002、T003 可平行（不同新檔）。
- **US1 tests**: T005–T010 全 `[P]`（不同測試檔）。
- **US1 impl**: T011、T012、T013 三新頁 `[P]`；T014（App.tsx）、T015（app-shell）依賴頁存在故序後。
- **US3**: T022、T023 不同檔可平行。
- **US4**: T026（金鑰卡）與 T027（providers）不同檔可平行。
- **Polish**: T028、T029 可平行。

## Implementation Strategy

- **MVP = US1**（T001–T015）：分頁導覽 + 3 新頁可獨立交付、可深連結。
- **完整體驗 = + US2 + US3**：精簡儀表板 + 一句解釋，三者同為 P1。
- **收尾 = US4 + Polish**：UI 一致性（編輯合一、Rotate 中文化）+ RWD + 部署。
- 每階段結束跑該階段測試確認綠，最後 T030 全量綠才 T031 部署。
