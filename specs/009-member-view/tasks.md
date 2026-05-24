# Tasks: 階段 3b.1 — Member View

**Input**: Design documents from `/specs/009-member-view/`
**Prerequisites**: plan.md, spec.md, research.md, contracts/ui-routes.md, quickstart.md

**Tests**: TDD enforced — Vitest unit/component (前端) + pytest contract (後端)。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

### Frontend deps + shadcn 元件

- [ ] T001 在 `frontend/package.json` 新增 Radix primitives：`@radix-ui/react-checkbox`、`@radix-ui/react-switch`、`@radix-ui/react-tabs`、`@radix-ui/react-progress`、`@radix-ui/react-toast`、`@radix-ui/react-separator`、`@radix-ui/react-scroll-area`；跑 `npm install`
- [ ] T002 [P] 建立 `frontend/src/components/ui/badge.tsx`（hand-write from shadcn defaults）
- [ ] T003 [P] 建立 `frontend/src/components/ui/progress.tsx`
- [ ] T004 [P] 建立 `frontend/src/components/ui/tabs.tsx`
- [ ] T005 [P] 建立 `frontend/src/components/ui/separator.tsx`
- [ ] T006 [P] 建立 `frontend/src/components/ui/scroll-area.tsx`
- [ ] T007 [P] 建立 `frontend/src/components/ui/checkbox.tsx`
- [ ] T008 [P] 建立 `frontend/src/components/ui/switch.tsx`
- [ ] T009 [P] 建立 `frontend/src/components/ui/toast.tsx` + `toaster.tsx` + `use-toast.ts` trio
- [ ] T010 確認 `cd frontend && npm run typecheck && npm run build` 仍綠（無新元件被引用之前）

---

## Phase 2: Foundational

### Backend endpoint extension（先做，因 frontend 將消費新 shape）

- [ ] T011 建立 `tests/contract/test_me_calls_pagination.py`：
  - `?limit=20` 回最近 20 筆 + `next_before_id`
  - `?limit=20&before_id=<X>` 回 X 之前的 20 筆
  - 回 ≤ limit 時 `next_before_id=null`
  - 不帶 query → default limit=20
  - 403 / 404 行為不變
- [ ] T012 修改 `src/ai_api/api/me.py` `/me/allocations/{id}/calls` endpoint：
  - 加 `limit: int = Query(20, ge=1, le=100)`、`before_id: str | None = Query(None)`
  - 內部呼叫 `list_for_allocation(..., limit=limit + 1, before=before_id)`
  - 切分 items 與計算 `next_before_id`（research.md §11 邏輯）
  - response shape 改 `{items: [...], next_before_id: str | null}`
- [ ] T013 確認 T011 全綠 + `uv run pytest -q` 既有 195 tests 不回歸（總 196）

### Frontend foundational

- [ ] T014 [P] 建立 `frontend/src/lib/clipboard.ts`：`copyToClipboard(text)` (research.md §5)
- [ ] T015 [P] 建立 `frontend/src/hooks/use-catalog-filters.ts`：URL ↔ filter state hook (research.md §2)
- [ ] T016 [P] 建立 `frontend/src/__tests__/clipboard.test.ts`：mock `navigator.clipboard`，cover happy + fallback
- [ ] T017 [P] 建立 `frontend/src/__tests__/use-catalog-filters.test.ts`：toggle / setSingle / clear 行為；URL 同步
- [ ] T018 修改 `frontend/src/contexts/auth.tsx`：`AuthProvider` 接受 `queryClient?` prop；`logout()` 內呼叫 `queryClient?.clear()` (FR-027)
- [ ] T019 建立 `frontend/src/components/app-shell.tsx`：sticky header + nav (Dashboard / Catalog) + member email + Logout button + `<Outlet />`（research.md §7）
- [ ] T020 建立 `frontend/src/__tests__/app-shell.test.tsx`：header 渲、nav links 高亮 active、logout 觸發
- [ ] T021 修改 `frontend/src/App.tsx`：
  - 把 `<AuthProvider>` 改傳 `queryClient`
  - 路由結構：`<Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>` 包 4 個業務 route
  - `/` 重導 `/dashboard`
- [ ] T022 [P] 刪除 `frontend/src/routes/home.tsx`（被 dashboard 取代）

**Checkpoint**：T011-T022 完成後 `npm run typecheck && npm test -- --run`
全綠（含新 4 個前端 tests + 1 個 backend test）。

---

## Phase 3: US1 — Dashboard (P1)

**Goal**：登入後看到 member info + allocations 列表。
**Independent Test**：訪 `/dashboard` 顯示 alice email + 1 個 allocation 卡片。

### Tests First

- [ ] T023 [US1] 建立 `frontend/src/__tests__/dashboard.test.tsx`：
  - 載入中 → spinner
  - 0 allocations → empty state 文字
  - 2 active allocations → 2 張卡片，每張含 model name + token prefix + status badge + quota bar
  - 切「含已撤回」switch → 加入 revoked
  - `/me/allocations` 500 → 錯誤區塊 + 重試按鈕

### Impl

- [ ] T024 [US1] 建立 `frontend/src/routes/dashboard.tsx`：
  - 用 `useQuery(["me"])` + `useQuery(["me","allocations",{include_revoked}])`
  - 顯示 member email + provider + active count
  - allocations 列表用 shadcn Card + Badge + Progress
  - empty state、error state
  - switch (include_revoked) 用 useState 控制

---

## Phase 4: US2 — Allocation Detail (P1)

**Goal**：點 allocation → 詳細頁 + 呼叫歷史 cursor pagination。
**Independent Test**：30 筆呼叫場景 → 20 筆 + 載入更多 + 10 筆 + 按鈕消失。

### Tests First

- [ ] T025 [US2] 建立 `frontend/src/__tests__/allocation-detail.test.tsx`：
  - quota=1000 + usage=750 → progress bar 75% + 文字
  - quota=null → 「無限額」標籤、無 progress
  - 30 筆呼叫 → 表格初始 20 筆、點「載入更多」追加 10、按鈕消失
  - 403 → 「無權限」+ 回首頁連結（**非** redirect）
  - 404 → 「找不到」

### Impl

- [ ] T026 [US2] 建立 `frontend/src/routes/allocation-detail.tsx`：
  - `useParams<{id: string}>()`
  - `useInfiniteQuery` 對 calls endpoint（research.md §4）
  - 從 `/me/allocations` 找出當下 allocation 取 quota
  - 計算「本月 total_tokens」累加：用 calls 的 items（簡化版；後端正式統計留 admin 端）
  - shadcn Progress + Table（自刻簡單 table，sm 元件不必額外引入）
  - 403/404 內嵌錯誤頁
- [ ] T027 [US2] App.tsx 加 route `/dashboard/allocations/:id` 包在 AppShell 內

---

## Phase 5: US3 — Catalog browse + filter (P1)

**Goal**：filter sidebar + 結果 grid；URL = filter state。
**Independent Test**：勾 vision+function-calling+low → 唯一命中 gpt-4o-mini；URL 同步。

### Tests First

- [ ] T028 [US3] 建立 `frontend/src/__tests__/catalog.test.tsx`：
  - mock `/catalog/models` + `/catalog/filters` 回 9 model fixture
  - 初始 grid 顯示 8 個（含 deprecated 預設隱藏）
  - 勾 capability=vision → URL `?capability=vision`，grid 過濾
  - 勾兩個 capability → URL repeat key（AND 語意）
  - cost_tier radio 變動更新 URL
  - 切 include_deprecated switch → 結果含 deprecated
  - 0 hits → 友善訊息

### Impl

- [ ] T029 [US3] 建立 `frontend/src/routes/catalog.tsx`：
  - left sidebar 用 `useQuery(["catalog","filters",{include_deprecated}])` 取 facet counts
  - right grid 用 `useQuery(["catalog","models", filters])`
  - 用 `useCatalogFilters()` hook 連動 URL ↔ checkbox state
  - sidebar 用 ScrollArea + Checkbox + Switch
  - grid 卡片用 shadcn Card + Badge (cost_tier, family)
  - 空命中 message
- [ ] T030 [US3] App.tsx 加 route `/catalog`

---

## Phase 6: US4 — Catalog Detail + copy curl (P1)

**Goal**：detail 頁 + tabs + 複製 curl。
**Independent Test**：訪 detail → 顯示 curl → 點按鈕 → toast。

### Tests First

- [ ] T031 [US4] 建立 `frontend/src/__tests__/catalog-detail.test.tsx`：
  - 顯示 description + capabilities + modality icons
  - tabs 切換 curl / JSON
  - 點「複製 curl」→ `navigator.clipboard.writeText` 被呼叫 + toast 顯示
  - clipboard unavailable → fallback 顯示 + 「請手動複製」訊息
  - deprecated 模型顯示 warning banner

### Impl

- [ ] T032 [US4] 建立 `frontend/src/routes/catalog-detail.tsx`：
  - `useParams<{slug: string}>()` + `useQuery(["catalog","model",slug])`
  - shadcn Tabs：curl / JSON body
  - 「複製 curl」按鈕呼叫 `copyToClipboard()` + `useToast()`
  - deprecated banner（shadcn Alert variant=destructive）
- [ ] T033 [US4] App.tsx 加 route `/catalog/:slug`（splat for `/`）

---

## Phase 7: US5 — Header nav + logout (P2)

**Goal**：sticky header 在每頁；logout 清 cache。

說明：T019 + T020 已建 AppShell 含 header；T018 已加 queryClient.clear()。本
phase 是 polish + 整合驗證。

- [ ] T034 [US5] 在 `app-shell.test.tsx` 補測：nav links 高亮、logout → queryClient.clear() 被呼叫
- [ ] T035 [US5] 手動驗證（quickstart §5）：登入 alice → logout → 登入 bob → 看不到 alice cache

---

## Phase 8: Polish

- [ ] T036 [P] 跑 `cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build` 全綠
- [ ] T037 [P] 跑 `uv run pytest -q && uv run ruff check . && uv run mypy src/ai_api` 全綠
- [ ] T038 [P] 更新 `frontend/README.md`：加 dashboard / catalog / allocation detail 章節
- [ ] T039 [P] 更新 `docs/frontend.md`：加 routes 表 + AppShell 模式
- [ ] T040 [P] 更新 `knowledge/vision.md` 階段 3b：標 3b.1 完成
- [ ] T041 PR 描述附 quickstart §2-§5 執行紀錄

---

## Dependencies

```
Phase 1 (Setup: deps + 9 shadcn ui files)
   │
   ▼
Phase 2 (Foundational: backend endpoint + clipboard + filter hook + AppShell + cache)
   │
   ├─→ Phase 3 (US1 — dashboard) ──────┐
   │                                    │
   ├─→ Phase 4 (US2 — allocation detail) — depends on App.tsx route from Phase 2
   │
   ├─→ Phase 5 (US3 — catalog list)
   │
   ├─→ Phase 6 (US4 — catalog detail)
   │
   └─→ Phase 7 (US5 — nav polish ─ 多在 Phase 2 已實作)
        │
        ▼
   Phase 8 Polish
```

**Story dependencies**：
- US1-US4 全部依賴 Phase 2 的 AppShell + App.tsx 路由結構；之後彼此獨立可並行
- US5 在 Phase 2 已實作（header + queryClient.clear）；Phase 7 是 polish
- 後端 endpoint 必須先做（T011-T013），否則 US2 的 useInfiniteQuery 拿到舊
  shape 會炸

---

## Parallel Execution Opportunities

- **Phase 1**：T002-T009 (8 個 shadcn 元件) 全部並行；T010 為 gate
- **Phase 2**：T011 / T014 / T015 / T016 / T017 都並行；T018-T021 略循序（同檔）
- **Phase 3-6**：4 個 user story 完全並行（各自獨立檔案）
- **Phase 8**：全部並行

---

## Implementation Strategy

### MVP

**Phase 1+2+3** = MVP（dashboard 可看到 allocations 列表）。
**+ Phase 4** = allocation detail（呼叫歷史看得到）。
**+ Phase 5+6** = catalog（vision 招牌 feature）。
**+ Phase 7+8** = polish。

### TDD Discipline

每個 user story：unit/component test commit → impl commit。同 3b.0 模式。

### Risk Hot Spots

1. **Backend endpoint shape breaking change**：原 list → dict；要確認沒有其
   他 caller（grep `list_for_allocation` 與 `/me/allocations/.+/calls`）
2. **useInfiniteQuery initial pageParam**：必須 `initialPageParam: null` 否則
   會出現 `undefined` 跑出去
3. **shadcn checkbox controlled vs uncontrolled**：URL state 是 source of
   truth → 一律 controlled (`checked={...}` + `onCheckedChange={...}`)
4. **URL query string repeated key encoding**：FastAPI 預設能處理；測試環
   境用 MemoryRouter 加 `initialEntries` 直接驗
5. **Toast 元件需要 `<Toaster />` mount 在根**：忘了 mount 會無聲失敗 → 在
   App.tsx 內加；測試 mock useToast hook
6. **`/catalog/:slug` 含 `/` 在 React Router v7**：要 splat (`:slug*` 或
   `/catalog/*`) — 測試覆蓋 `azure%2Fgpt-4o-mini` 與 `azure/gpt-4o-mini`
   兩種寫法
7. **`useSearchParams` 與 React strict mode**：可能 double-set state；用
   `setSearchParams(prev => ...)` 函式式更新比較安全

---

## Format Validation

✅ 全部 41 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-7 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
