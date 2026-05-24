# Tasks: 階段 3b.2 — Admin Suite

**Input**: Design documents from `/specs/010-admin-suite/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/{admin-auth,admin-routes,admin-endpoints}.md, quickstart.md

**Tests**: TDD enforced — backend pytest (contract) + frontend Vitest (component)。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

### Frontend deps + shadcn 元件

- [ ] T001 在 `frontend/package.json` 新增依賴：`react-hook-form@^7`、`@hookform/resolvers@^3`、`zod@^3`、`date-fns@^4`、Radix primitives：`@radix-ui/react-dialog`、`@radix-ui/react-alert-dialog`、`@radix-ui/react-dropdown-menu`、`@radix-ui/react-select`、`@radix-ui/react-popover`；跑 `npm install`
- [ ] T002 [P] 建立 `frontend/src/components/ui/table.tsx`（hand-write from shadcn defaults）
- [ ] T003 [P] 建立 `frontend/src/components/ui/dialog.tsx`
- [ ] T004 [P] 建立 `frontend/src/components/ui/alert-dialog.tsx`
- [ ] T005 [P] 建立 `frontend/src/components/ui/dropdown-menu.tsx`
- [ ] T006 [P] 建立 `frontend/src/components/ui/form.tsx`（含 react-hook-form `FormProvider` / `FormField` / `FormItem` / `FormLabel` / `FormControl` / `FormMessage`）
- [ ] T007 [P] 建立 `frontend/src/components/ui/select.tsx`
- [ ] T008 [P] 建立 `frontend/src/components/ui/textarea.tsx`
- [ ] T009 [P] 建立 `frontend/src/components/ui/popover.tsx`
- [ ] T010 確認 `cd frontend && npm run typecheck && npm run build` 仍綠（無新元件引用前）

---

## Phase 2: Foundational

### Backend: migration + Member.is_admin

- [ ] T011 修改 `src/ai_api/models/member.py`：加 `is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)`
- [ ] T012 建立 Alembic migration `alembic/versions/0007_member_is_admin.py`：
  - ALTER `members` ADD `is_admin` BOOL NOT NULL DEFAULT FALSE
  - 擴 `auth_audit_log.event_type` enum：加 `member_promoted`、`member_demoted`
- [ ] T013 修改 `src/ai_api/models/auth_audit.py`：`AuditEventType` enum 加 2 個值

### Backend: require_admin dep (核心)

- [ ] T014 建立 `tests/contract/test_admin_session_auth.py`：5 個情境
  - 有 X-Admin-Token → 200
  - session + is_admin=true → 200
  - session + is_admin=false → 403 `not_admin`
  - session + member.status=disabled → 403 `member_disabled`
  - 無 token + 無 session → 401 `unauthorized`

- [ ] T015 修改 `src/ai_api/api/deps.py`：
  - 新增 `require_admin(request, x_admin_token, session_cookie)` 函式（research.md §1）
  - 將 `require_admin_token` 改為 `require_admin` 的別名（既有 30 個 `Depends(require_admin_token)` callers 不需動）

### Backend: PATCH /admin/members 加 is_admin

- [ ] T016 建立 `tests/contract/test_admin_is_admin_promotion.py`：
  - PATCH `is_admin=true` → 200 + audit event `member_promoted`
  - PATCH `is_admin=false` → 200 + audit event `member_demoted`
  - 升 admin 後 /me 含 `is_admin: true`
  - 升 admin 後 session-only 訪 `/admin/members` 200

- [ ] T017 建立 `tests/contract/test_last_admin_guard.py`：
  - 唯一 active admin 嘗試降 → 409 `last_admin_cannot_demote`
  - audit log 未寫
  - 該 Member 的 is_admin DB 欄位仍 true
  - 兩個 admin 時降一個 → 200

- [ ] T018 修改 `src/ai_api/services/members.py`：新增 `set_is_admin(member_id, is_admin, actor)` 方法（research.md §3）；含 last-admin guard；raise `LastAdminCannotDemoteError`；呼叫 `audit.record()`
- [ ] T019 修改 `src/ai_api/api/admin_members.py`：
  - `UpdateMemberRequest` 加 `is_admin: bool | None = None`
  - `update_member` 若 payload 有 `is_admin` 欄位 → 呼叫 `MemberService.set_is_admin`
  - catch `LastAdminCannotDemoteError` → 409
- [ ] T020 修改 `src/ai_api/api/me.py`：`_member_public` 加 `is_admin: m.is_admin` 欄位

### Backend gate

- [ ] T021 跑 `rm -f ai_api.db && uv run alembic upgrade head && uv run pytest -q` 確認 0007 migration + 既有 199 + 新增 contract tests 全綠

### Frontend Foundational

- [ ] T022 [P] 修改 `frontend/src/contexts/auth.tsx`：`Member` 型別加 `is_admin?: boolean`
- [ ] T023 [P] 修改 `frontend/src/components/app-shell.tsx`：條件渲 Admin nav link (`member?.is_admin === true`)
- [ ] T024 建立 `frontend/src/__tests__/admin-route.test.tsx`：
  - loading → spinner
  - is_admin=false → 「無權限查看」內嵌頁，URL 不變
  - is_admin=true → 渲 children
- [ ] T025 建立 `frontend/src/components/admin-route.tsx`：guard component（research.md §4 + contracts/admin-routes.md）
- [ ] T026 修改 `frontend/src/App.tsx`：加 `<Route element={<AdminRoute />}>` 包 admin route 群（暫時佔位 children）

**Checkpoint**：T011-T026 完成後 backend ≥ 207 tests + frontend typecheck/build
仍綠；admin nav 在 alice 登入後顯示，bob 登入後不顯示。

---

## Phase 3: US1 + US2 — Bootstrap + Admin nav (P1)

說明：bootstrap 流程（後端 PATCH is_admin + audit）已在 Phase 2 完成；admin
nav 條件渲也在 Phase 2 完成。本 phase 補對應的「整合」測試驗證。

- [ ] T027 [US1] 建立 `tests/contract/test_admin_bootstrap_flow.py`：端到端
  - 用 X-Admin-Token 建 alice + PATCH is_admin=true
  - alice 用 local password login → cookie 設定
  - alice GET /me → is_admin=true
  - alice GET /admin/members（session only，無 token）→ 200
  - alice POST /admin/members 建 bob → 201

- [ ] T028 [US2] 在 `frontend/src/__tests__/app-shell.test.tsx` 加 case：
  - member.is_admin=true → Admin nav link 出現
  - member.is_admin=false → Admin link 不出現

**Checkpoint**：US1 + US2 全綠；可手動 bootstrap alice 並看到 admin link。

---

## Phase 4: US3 — Admin Members 視圖 (P1)

### Tests First

- [ ] T029 [US3] 建立 `frontend/src/__tests__/admin-members.test.tsx`：
  - 3 個 member fixture → 表格 3 row
  - 「新建 Member」dialog 開、submit → POST 被呼叫、表格 invalidate
  - dropdown「升 admin」→ PATCH is_admin=true 被呼叫
  - 表單驗證：email 格式錯誤 → 不發 request
  - 後端 409（duplicate email）→ toast、dialog 不關
  - dropdown「降 admin」對唯一 admin → 後端 409 → toast「至少需保留一個 admin」

### Impl

- [ ] T030 [US3] 建立 `frontend/src/routes/admin/members.tsx`：
  - `useQuery(["admin","members"])` 拉列表
  - 表格用 shadcn `<Table>`：email、provider、status、is_admin badge、created_at、actions
  - 「新建」按鈕觸發 `<CreateMemberDialog>`
  - row dropdown：升/降 admin、停用/啟用、重設密碼、刪除（各自走 alert-dialog 確認）
- [ ] T031 [US3] 建立 `frontend/src/routes/admin/members/create-dialog.tsx`：react-hook-form + zod schema（email、provider、password）；提交呼叫 POST + `invalidateQueries`
- [ ] T032 [US3] 修改 `frontend/src/App.tsx`：將 admin/members route 接上 `<AdminMembersPage>`

---

## Phase 5: US4 — Admin Allocations 視圖 (P1)

### Tests First

- [ ] T033 [US4] 建立 `frontend/src/__tests__/use-admin-allocations-filters.test.tsx`：URL ↔ filter hook（status / member_id / service_only）
- [ ] T034 [US4] 建立 `frontend/src/__tests__/admin-allocations.test.tsx`：
  - 5 個 allocation fixture → 表格 5 row
  - status filter `active` → URL 同步
  - 「新建 Allocation」dialog submit → POST + token 顯示 dialog
  - 「我已複製」按鈕 → token 從 state 清除
  - 「調 quota」inline → PATCH 被呼叫
  - 「撤回」alert-dialog 確認 → DELETE 被呼叫

### Impl

- [ ] T035 [US4] 建立 `frontend/src/hooks/use-admin-allocations-filters.ts`：URL state hook（research.md §7）
- [ ] T036 [US4] 建立 `frontend/src/routes/admin/allocations.tsx`：
  - 表格列：member email、subject_snapshot、resource_model、status badge、quota cell、is_service badge、token_prefix、created_at、actions
  - filter bar 用 `<Switch>`（service_only）+ `<Select>`（status / member）
  - 「新建」按鈕觸發 `<CreateAllocationDialog>`
  - row dropdown：調 quota、切 quota_locked、切 is_service、撤回
- [ ] T037 [US4] 建立 `frontend/src/routes/admin/allocations/create-dialog.tsx`：兩階段 dialog（form + 成功後 token 顯示）；token 僅存 component state
- [ ] T038 [US4] 修改 `frontend/src/App.tsx`：接 `<AdminAllocationsPage>`

---

## Phase 6: US5 — Admin Usage 視圖 (P1)

### Tests First

- [ ] T039 [US5] 建立 `frontend/src/__tests__/use-admin-usage-filters.test.tsx`：URL ↔ filter hook（from / to / group_by / service_only）
- [ ] T040 [US5] 建立 `frontend/src/__tests__/download.test.ts`：`triggerDownload(filename, blob)` 建立 `<a>` + click + revoke
- [ ] T041 [US5] 建立 `frontend/src/__tests__/admin-usage.test.tsx`：
  - 預設 group_by=member、30 天 → 表格按 member 切分
  - 切 group_by=model → URL 變、表格欄位變
  - 「下載 CSV」呼叫 `apiBlob('/admin/usage.csv?...')` → `triggerDownload`
  - 後端 400 invalid_time_range → toast、表格不清空

### Impl

- [ ] T042 [US5] 建立 `frontend/src/hooks/use-admin-usage-filters.ts`：URL state（research.md §8）
- [ ] T043 [US5] 建立 `frontend/src/lib/download.ts`：`triggerDownload(filename, blob)`（research.md §6）+ `apiBlob(path)`（不污染 `api<T>`）
- [ ] T044 [US5] 建立 `frontend/src/routes/admin/usage.tsx`：
  - filter bar：date range（兩個 `<Input type="date">` 簡化版；popover 留 polish）、`<Select>` group_by、`<Switch>` service_only
  - 表格依 group_by 切換 columns（member / allocation / model）
  - 右上角「下載 CSV」、「下載 JSON」按鈕
- [ ] T045 [US5] 修改 `frontend/src/App.tsx`：接 `<AdminUsagePage>`

---

## Phase 7: US6 — Admin Quota Pool 視圖 (P1)

### Tests First

- [ ] T046 [US6] 建立 `frontend/src/__tests__/admin-quota-pool.test.tsx`：
  - 載入時顯示 T、reserved、distributable、pool_member_count、floor、last_rebalance_at
  - T=0 → 狀態卡「池已停用」+ 「手動 rebalance」按鈕 disabled
  - 點「手動 rebalance」+ 確認 → POST + toast + 狀態 + log invalidate
  - 失敗 409 pool_exhausted → toast 紅字
  - log row 點開 drawer → 顯示 details JSON

### Impl

- [ ] T047 [US6] 建立 `frontend/src/routes/admin/quota-pool.tsx`：
  - `useQuery(["admin","quota-pool","status"])`
  - `useQuery(["admin","quota-pool","log"])`
  - 狀態卡用 shadcn `<Card>`
  - 「手動 rebalance」按鈕用 alert-dialog 確認 → POST
  - log table → 點 row 開 `<Dialog>` 顯示 details
- [ ] T048 [US6] 修改 `frontend/src/App.tsx`：接 `<AdminQuotaPoolPage>`

---

## Phase 8: US7 + US8 — Catalog preview + RebalanceLog list (P2)

### US7 — Catalog preview

- [ ] T049 [US7] 修改 `frontend/src/App.tsx`：admin 路由群加 `/admin/catalog` → `<CatalogPage>` + `/admin/catalog/*` → `<CatalogDetailPage>`（直接 reuse 3b.1 元件）
- [ ] T050 [US7] 在 `app-shell.tsx` 加判斷：當 path 以 `/admin/` 開頭時，nav 高亮 Admin（catalog 在 admin 視角同樣高亮 Admin link）

### US8 — RebalanceLog 列表 + detail

- [ ] T051 [US8] 建立 `frontend/src/__tests__/admin-rebalance-log.test.tsx`：
  - list endpoint 回 5 筆 → 顯示 5 row
  - 點 row 跳 `/admin/rebalance-log/:id`
  - detail 含 details JSON
  - 「複製 JSON」按鈕呼叫 `copyToClipboard`

- [ ] T052 [US8] 建立 `frontend/src/routes/admin/rebalance-log.tsx`（list + detail 兩個 page in 同一檔，依 useParams 區分）；或拆兩檔
- [ ] T053 [US8] 修改 `frontend/src/App.tsx`：接 `/admin/rebalance-log` + `/admin/rebalance-log/:id`

---

## Phase 9: Polish

### CI gates

- [ ] T054 [P] 跑 `cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build` 全綠
- [ ] T055 [P] 跑 `uv run pytest -q && uv run ruff check . && uv run mypy src/ai_api` 全綠
- [ ] T056 [P] 確認 SC-002：原本 274 處 `admin_headers` 測試**零修改** + 全部通過（用 `git diff main -- tests/` 確認 admin_headers 那些檔案無變更）

### Docs

- [ ] T057 [P] 更新 `frontend/README.md`：admin 路由章節
- [ ] T058 [P] 更新 `docs/frontend.md`：admin auth + AdminRoute 流程
- [ ] T059 [P] 建立 `docs/admin-bootstrap.md`：bootstrap admin 的 SOP（含 backend ENV + curl 步驟）

### Vision

- [ ] T060 [P] 更新 `knowledge/vision.md` 階段 3b：標 3b.2~3b.6 合併完成

### PR

- [ ] T061 PR 描述附 quickstart §1-§9 manual 執行紀錄

---

## Dependencies

```
Phase 1 (Setup: deps + 8 shadcn UI)
   │
   ▼
Phase 2 (Foundational: migration + backend dep + Member.is_admin + AdminRoute + AppShell nav)
   │
   ├─→ Phase 3 (US1 + US2 — bootstrap + nav；整合測試)
   │
   ├─→ Phase 4 (US3 — admin members)
   ├─→ Phase 5 (US4 — admin allocations) — 與 US3 並行
   ├─→ Phase 6 (US5 — admin usage) — 與 US3/US4 並行
   ├─→ Phase 7 (US6 — admin quota-pool) — 與 US3-5 並行
   └─→ Phase 8 (US7 + US8 — catalog preview + rebalance-log) — 與 US3-6 並行
        │
        ▼
   Phase 9 Polish
```

**Story dependencies**：
- US3-US8 全部依賴 Phase 2 的 AdminRoute + App.tsx 路由結構 + 後端 require_admin dep；之後彼此獨立
- US1 + US2 是 bootstrap + nav 行為驗證，本質上 Phase 2 已實作；本 phase 是
  整合測試補強

---

## Parallel Execution Opportunities

- **Phase 1**：T002-T009 (8 個 shadcn 元件) 全部並行；T010 為 gate
- **Phase 2 backend**：T011-T013 依序（同 migration 範疇）；T014-T020 大致循序（同檔多）
- **Phase 2 frontend**：T022-T026 略循序（同檔依賴）
- **Phase 4-8 (US3-US8)**：5 個 user story 完全獨立可並行（各自獨立檔案）；
  同檔 commits 需 sequential
- **Phase 9**：T054-T060 全部並行

---

## Implementation Strategy

### MVP

**Phase 1+2+3 = MVP**（bootstrap 通 + admin nav 可見 + 0 admin 視圖）。
**+ Phase 4 (US3 admin members)** = 第一個可用 admin 視圖。
**+ Phase 5-7 (US4-US6)** = 三個核心 admin 工具。
**+ Phase 8 (US7+US8)** = catalog 預覽 + RebalanceLog detail（補完）。

### TDD Discipline

每個 user story：unit/component test commit → impl commit。同 3b.0/3b.1 模式。

### Risk Hot Spots

1. **require_admin alias 模式**：T015 把 `require_admin_token` 改為 `require_admin`
   的別名。若不小心改錯（如把 token-only path 拿掉）→ 274 admin_headers 測試
   全炸。改完務必跑 `uv run pytest -q` 一次。
2. **Migration 0007 在既有 SQLite test DB 上跑**：`server_default=false` 在
   SQLite 用 `sa.false()` 須 expression；alembic batch_alter 必用。
3. **Last-admin guard 邊界**：要對「升 admin 後再降」這種同 transaction 邊界
   行為小心；service 用 SELECT count 後 UPDATE 之間可能 race（但本 spec 不
   做高並發 admin 操作，可忽略）。
4. **react-hook-form + zod 整合**：shadcn `form.tsx` 元件複雜（FormProvider
   + Controller）；T006 必須完整 copy from shadcn 官方範本（含 type 推導）。
5. **Token 一次性顯示**：T037 token 僅放 React state；切勿 useEffect 把它
   存 localStorage。
6. **CSV download 在 Vitest 環境**：jsdom 沒 `URL.createObjectURL`；T040
   test 需要 mock `URL.createObjectURL` 與 `URL.revokeObjectURL`。
7. **NavLink active state for /admin/***：React Router v7 預設 active 規則
   只 match exact；要用 `end={false}`（NavLink default）讓 `/admin/members`
   也讓 `/admin` link active。

---

## Format Validation

✅ 全部 61 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-8 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
