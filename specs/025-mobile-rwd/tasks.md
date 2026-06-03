---
description: "Tasks for 階段 16 — 行動裝置（手機）體驗強化（RWD）"
---

# 任務清單：行動裝置（手機）體驗強化（RWD）

**輸入文件**：`/specs/025-mobile-rwd/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/ui-contracts.md](./contracts/ui-contracts.md) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：**有 DOM 可斷言的行為**（US1 手機導覽、US3 響應式表格 `data-label`）
→ **先寫失敗 vitest（Red）再實作（Green）**。**純視覺 RWD**（溢出/折行/字字斷行）jsdom 無版面引擎、
無法單元測試 → 以 [quickstart.md](./quickstart.md) 的 360px 手動清單驗收（見 research R6）。
**桌機零回歸**：既有 109 vitest 須全程維持綠。

**組織原則**：依使用者故事分組（US1 導覽 → US2 內容不溢出 → US3 寬表格卡片化）。**僅動 `frontend/`、
零新 npm 依賴、零後端/DB 變更。**

## 格式

`- [ ] TaskID [P?] [Story?] 描述 (含絕對檔案路徑)`
- **[P]**：可並行（不同檔案、無未完成依賴）
- **[Story]**：US1–US3；Setup / Foundational / Polish 不加 Story 標

## 路徑慣例

- 前端：`frontend/src/`；測試：`frontend/src/__tests__/`；設定：`frontend/tailwind.config.ts`、`frontend/src/index.css`

---

## Phase 1：Setup

- [X] T001 確認前置：在 `frontend/` 跑 `npm run test && npm run lint && npm run typecheck && npm run build` 全綠，建立「實作前」基準（桌機零回歸對照）；確認 `@radix-ui/react-dialog`、`@radix-ui/react-dropdown-menu`、`lucide-react` 皆已在 `frontend/package.json`（本功能不新增依賴）

---

## Phase 2：Foundational（阻斷性前置）

**⚠️ 跨全站的根因修正，先做；完成後 US1–US3 可平行推進。**

- [X] T002 在 `frontend/tailwind.config.ts` 將 `container.padding: "2rem"` 改為 `padding: { DEFAULT: "1rem", sm: "2rem" }`（根因①：手機釋出版面寬，`sm:` 以上維持 2rem 桌機不變）

**Checkpoint**：手機有效寬增加，放大全站擠壓的根因解除。

---

## Phase 3：US1 — 手機上導覽順暢可達（P1）🎯 MVP

**目標**：header 在 `< md` 收合為漢堡 + `Sheet` 抽屜（含全部目的地），email 不擠掉控制項，子導覽不字字斷行；桌機（≥md）不變。

**獨立驗收**：quickstart「殼層/導覽」區塊；契約見 `contracts/ui-contracts.md` 契約 2。

### Tests First (Red)

- [X] T003 [US1] 新增 `frontend/src/__tests__/mobile-nav.test.tsx`：(a) 手機寬度渲染 `AppShell`（admin 身分）存在可存取漢堡鈕（`aria-label`）；(b) 觸發漢堡 → 抽屜開啟 → 可查得**全部**目的地連結（我的儀表板/模型目錄/管理員 + 8 個管理員子導覽 + 登出）；(c) 桌機寬度下不出現漢堡、維持既有 inline 導覽
- [X] T004 [US1] 跑 T003 確認 **全 Red**（尚無 Sheet/漢堡）

### Implementation (Green)

- [X] T005 [US1] 新增 `frontend/src/components/ui/sheet.tsx`：標準 shadcn Sheet（基於既有 `@radix-ui/react-dialog`，**非新依賴**）；含 `Sheet`/`SheetTrigger`/`SheetContent`/`SheetClose` 等 export
- [X] T006 [US1] 改 `frontend/src/components/app-shell.tsx`：`< md` 隱藏 inline 主導覽與 email、顯示漢堡鈕（`lucide-react` `Menu`）→ 開 `Sheet` 抽屜，內含全部主導覽 + 管理員子導覽 + email + 登出；`≥ md` 維持現有橫排（不動既有 class）
- [X] T007 [US1] 在 `frontend/src/components/app-shell.tsx` 既有橫向管理員子導覽各 `NavLink` 補 `shrink-0 whitespace-nowrap`（防中文字字斷行）；同樣處理 `frontend/src/routes/admin/observability.tsx` 的次級 tab 列
- [X] T008 [US1] 跑 T003 確認 **全 Green**；跑既有 `app-shell.test.tsx` 確認桌機行為零回歸

---

## Phase 4：US2 — 頁面內容不溢出、不擠爆（P2）

**目標**：多欄資訊/表單堆疊單欄、工具列換行、長字串截斷/換行；整頁手機無水平捲動、無字字斷行。

**獨立驗收**：quickstart「管理員頁」「成員端頁」各頁 (A)(B)(C) 三問通過。

> 本階段多為純 CSS（既有 Tailwind 工具），**無 jsdom 可測行為**，以 quickstart 360px 手動清單驗收；
> 規則統一：多欄 `grid-cols-1 sm:grid-cols-N`、工具列 `flex-wrap`、長字串 `truncate`（配 `min-w-0`）/`break-all`、
> 橫排含中文 `whitespace-nowrap`+`min-w-0`。

### 管理員：資訊區塊 / 表單 dialog（多欄堆疊）

- [X] T009 [P] [US2] `frontend/src/routes/admin/home.tsx`：系統資訊 `grid-cols-[max-content_1fr]` → `grid-cols-1 sm:grid-cols-[max-content_1fr]`；最近活動 audit 列加 `flex-wrap`
- [X] T010 [P] [US2] `frontend/src/routes/admin/member-detail.tsx`：登入方式/狀態/管理員 `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`；分配卡 header 工具列加 `flex-wrap`（移除右側 `shrink-0` 擠壓）
- [X] T011 [P] [US2] `frontend/src/routes/admin/model-detail.tsx`：基本資訊 `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`；EditBasics dialog 各 `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`；價格行允許換行
- [X] T012 [P] [US2] `frontend/src/routes/admin/notifications.tsx`：三處 `grid-cols-2`（SMTP host/port、寄件者 email/name 等）→ `grid-cols-1 sm:grid-cols-2`；密碼指紋 `<code>` 加 `break-all`；通知歷史列加 `flex-wrap`
- [X] T013 [P] [US2] `frontend/src/routes/admin/prices.tsx`：AddPrice dialog 各 `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`；價格歷史列加 `flex-wrap`
- [X] T014 [P] [US2] `frontend/src/components/usage-summary.tsx`：統計與 breakdown `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`；大數字避免溢出；header 時段按鈕列加 `flex-wrap`

### 管理員：工具列換行 + 長字串截斷

- [X] T015 [P] [US2] `frontend/src/routes/admin/usage.tsx`：下載按鈕列與篩選列加 `flex-wrap`；名稱欄 `{display_name ?? group_key}` 加 `max-w-[140px] truncate`（配 `min-w-0`）
- [X] T016 [P] [US2] `frontend/src/routes/admin/allocations.tsx`：頂部工具列外/內層 flex 加 `flex-wrap`；email 欄 `truncate min-w-0`；「已不在 catalog」徽章加 `shrink-0 whitespace-nowrap`
- [X] T017 [P] [US2] `frontend/src/routes/admin/members.tsx`：email link cell 加 `truncate max-w-[180px]`（配 `min-w-0`）
- [X] T018 [P] [US2] `frontend/src/routes/admin/providers.tsx`：頂部工具列加 `flex-wrap`；指紋 `<code>` 加 `break-all`
- [X] T019 [P] [US2] `frontend/src/routes/admin/tags.tsx`：頂部 3 顆按鈕 + 標題的工具列外/內層加 `flex-wrap`
- [X] T020 [P] [US2] `frontend/src/routes/admin/tag-rules.tsx`：條件欄 regex `<code>` 加 `break-all`
- [X] T021 [P] [US2] `frontend/src/routes/admin/access.tsx`：CIDR/pattern `<code>` 加 `break-all`；確認頂部 `shrink-0` 與標題不互擠（必要時 `flex-wrap`）
- [X] T022 [P] [US2] `frontend/src/routes/admin/model-access.tsx`：底部 preview + 套用列加 `flex-wrap`

### 成員端

- [X] T023 [P] [US2] `frontend/src/routes/dashboard.tsx`：端點/gateway URL 的 inline `<code>` 加 `break-all`；claim 卡與分配卡 `flex` 加 `flex-wrap`；「需 admin 解鎖」徽章 `whitespace-nowrap shrink-0`；分配卡標題 `truncate min-w-0`、狀態徽章 `shrink-0`；本月用量大數字允許換行；現價串 `break-words`
- [X] T024 [P] [US2] `frontend/src/routes/catalog.tsx`：model 卡模態串與價格串外層 `break-words`/`flex-wrap`；側欄 `ScrollArea h-[60vh]` 在手機改 `max-h` 或可摺疊
- [X] T025 [P] [US2] `frontend/src/routes/catalog-detail.tsx`：關係卡 `flex` 加 `flex-wrap`/`min-w-0`；價格三欄 `flex gap-8` → `flex-wrap gap-x-8 gap-y-3`；slug `<code>` 加 `break-all`
- [X] T026 [P] [US2] `frontend/src/components/api-usage-example.tsx`：header 描述的 inline `{base}` `<code>` 加 `break-all`；Codex 區 `flex` 加 `flex-wrap`
- [X] T027 [P] [US2] `frontend/src/routes/allocation-detail.tsx`（**非表格部分**）：標題 `truncate min-w-0`、狀態徽章 `shrink-0`；憑證卡按鈕群 `flex-wrap`；配額卡價格串 `break-words`；`resource_model` slug `break-all`（五欄呼叫紀錄表留待 US3 T037）

- [X] T028 [US2] 桌機回歸抽查：跑 `npm --prefix frontend run test && lint && typecheck && build` 全綠（T009–T027 純 CSS class，不應動到既有測試）；360px 手動過一遍 quickstart「US2」相關項

---

## Phase 5：US3 — 寬資料表卡片式堆疊（P3）

**目標**：寬表格在 `< md` 以卡片堆疊（每列一卡、欄位齊全），桌機維持完整表格；單一 `.responsive-table` 機制避免 drift。

**獨立驗收**：quickstart「管理員頁」各表格項 + 契約 `contracts/ui-contracts.md` 契約 1。

### Foundational for US3 + Tests First (Red)

- [X] T029 [US3] 在 `frontend/src/index.css` 新增 `.responsive-table` 機制：`@media (max-width: 767px)` 下 `thead` 隱藏、每 `tr` 變卡片（框/間距）、每 `td` 變 `flex justify-between`、`td::before { content: attr(data-label) }`；`≥ 768px` 完全不生效（桌機原樣）
- [X] T030 [US3] 新增 `frontend/src/__tests__/responsive-tables.test.tsx`：對每個目標表格頁各一斷言（先 Red）——渲染後該表掛有 `.responsive-table`，且每個 body 儲存格帶非空 `data-label`（涵蓋 usage/allocations/members/providers/prices/tag-rules/access/member-detail 內層表）
- [X] T031 [US3] 跑 T030 確認 **全 Red**

### Implementation (Green) — 逐表套用 `.responsive-table` + `data-label`

- [X] T032 [P] [US3] `frontend/src/routes/admin/usage.tsx`：主用量表掛 `.responsive-table`、每 `TableCell` 加 `data-label`；tag 下鑽的**裸 `<table>`** 改用 shadcn `<Table>` + `.responsive-table` 或外層 `overflow-x-auto`（消除 T037 前的唯一未包裹表）
- [X] T033 [P] [US3] `frontend/src/routes/admin/allocations.tsx`：7 欄表掛 `.responsive-table` + `data-label`（狀態欄含 `QuarantineReasonBadge` 維持可用）
- [X] T034 [P] [US3] `frontend/src/routes/admin/members.tsx`：表掛 `.responsive-table` + `data-label`（Tag cell 既有 `flex-wrap` 保留）
- [X] T035 [P] [US3] `frontend/src/routes/admin/providers.tsx`：表掛 `.responsive-table` + `data-label`；動作欄 3 顆按鈕（測試/輪替/停用）改收進 `DropdownMenu`（既有 `@radix-ui/react-dropdown-menu`），手機一螢幕寬可達
- [X] T036 [P] [US3] `frontend/src/routes/admin/prices.tsx`、`frontend/src/routes/admin/tag-rules.tsx`、`frontend/src/routes/admin/access.tsx`（兩表）、`frontend/src/routes/admin/member-detail.tsx`（內層分配表）：各表掛 `.responsive-table` + `data-label`
- [X] T037 [US3] `frontend/src/routes/allocation-detail.tsx`：五欄「最近呼叫」CSS grid 改為手機可讀——`< md` 轉卡片堆疊（沿用 `.responsive-table` 或等效卡片版面），桌機維持原 grid；每列以「標籤：值」呈現
- [X] T038 [US3] 跑 T030 確認 **全 Green**；桌機回歸抽查：既有測試全綠、≥768px 表格目視不變

---

## Phase 6：Polish 與跨領域

- [X] T039 跑 `npm --prefix frontend run test`（含既有 109 + 新增 mobile-nav/responsive-tables）全綠
- [X] T040 跑 `npm --prefix frontend run lint && typecheck && build` 全綠；確認 **bundle 無因新依賴增長**（`package.json` 依賴清單與實作前一致）
- [~] T041 （待你手機親驗）[P] 依 [quickstart.md](./quickstart.md) 在 **360px**（Chrome DevTools 或真機）以 **admin** 身分逐頁手動驗收（SC-001/003/004/005/007）
- [~] T042 （待你手機親驗）[P] 依 quickstart 以 **一般成員** 身分驗收成員端頁（dashboard/catalog/catalog-detail/allocation-detail）
- [X] T043 [P] 桌機零回歸（SC-006）：≥768px 逐頁目視與實作前一致；確認「已做對、別動」清單（圖表/heatmap/`<pre>`/catalog grid/成本 Badge）行為不變
- [X] T044 [P] 文件：`knowledge/design/frontend.md` 補一節「RWD 規範」（手機斷點策略、`.responsive-table` 機制與 `data-label` 約定、header Sheet 收合、CJK 字字斷行防範）
- [X] T045 [P] 更新 `knowledge/vision.md` 階段 16 → ✅（填完成日、列實際交付、連結 history 與 design/frontend.md）；roadmap/現狀/狀態塊三處同步改「階段 16 完成」
- [X] T046 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 16：行動裝置（手機）體驗強化（RWD）」詳情
- [X] T047 commit + push + 開 PR；**push 前先 `npm --prefix frontend run lint && typecheck && build`**；等 CI（test/frontend/image build）全綠後 squash merge 到 main
- [X] T048 main image build 綠後 `helm upgrade ai-api deploy/helm/ai-api -n ai-ccsh --reuse-values --set image.tag=sha-<main> --set frontend.image.tag=sha-<main> --set storedResponseCleanup.enabled=true --set storedResponseCleanup.schedule="0 3 * * *"`；rollout 完成後在手機（ai-ccsh.tew.tw）真機抽查 quickstart 殼層導覽 + 一個寬表格卡片化
- [X] T049 收尾：確認 vision 階段 16 ✅、history 補上、roadmap 狀態一致；標記 tasks 全完成

---

## 依賴與順序

```text
Phase 1 (Setup: 基準綠)
   ↓
Phase 2 (Foundational: container padding 根因) ── 解除全站擠壓放大
   ↓
Phase 3 (US1: 手機導覽) ─── MVP，最大痛點；sheet.tsx + app-shell（TDD）
   │
Phase 4 (US2: 內容不溢出) ─── 純 CSS 機械式掃；多檔 [P] 可並行；手動驗收
   │
Phase 5 (US3: 寬表格卡片化) ─── .responsive-table（TDD）+ 逐表套用；多表 [P]
   ↓
Phase 6 (Polish: 全測/lint/build + 360px 雙身分手動驗收 + 桌機零回歸 + 文件 + 部署)
```

**US 獨立性**：US1（導覽）、US2（內容）、US3（表格）各自可獨立交付與驗證；共同前置僅 T002（container padding）。

**MVP 建議**：US1（手機導覽收合）即解決使用者最大痛點、可獨立上線；US2、US3 陸續增益。

**[P] 並行機會**：
- US2：T009–T027 幾乎全 [P]（不同檔案）
- US3：T032–T036 [P]（不同檔案）
- Polish：T041–T046 [P]

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 Foundational | 1 | 0 |
| 3 US1（P1，MVP） | 6 | 2 |
| 4 US2（P2） | 20 | 0（純 CSS，手動驗收） |
| 5 US3（P3） | 10 | 2 |
| 6 Polish | 11 | 0 |
| **總計** | **49** | **4** |

---

## 格式檢核

- ✅ 所有任務 `- [ ] T###` 開頭、含 ID、描述、絕對/相對檔案路徑
- ✅ Setup / Foundational / Polish 無 Story 標；US1–US3 任務含 `[US#]` 標
- ✅ 可並行任務標 `[P]`
- ✅ TDD：US1（T003→T005-7→T008）、US3（T030→T032-37→T038）皆 Tests First → Red → 實作 → Green；US2 純視覺以 quickstart 手動驗收（憲章 I 之可測邊界，見 research R6）

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
