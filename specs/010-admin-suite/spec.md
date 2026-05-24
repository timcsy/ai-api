# Feature Specification: 階段 3b.2 — Admin Suite

**Feature Branch**: `010-admin-suite`
**Created**: 2026-05-24
**Status**: Draft
**Input**: User description: "階段 3b.2 admin suite — 5 個 admin 視圖 (members, allocations, usage, quota-pool, catalog) + Member.is_admin 後端擴充 (c-β：session-or-token 雙軌認證) + bootstrap 流程"

## Overview

合併原本拆 5 個子階段（3b.2~3b.6）為單一 PR — 因為 admin 5 個視圖共用同一個
shell + auth + table/dialog/form 模式，分 5 個 PR 反而會重複 spec / plan /
CI 開銷。

本階段同時擴後端：`Member.is_admin: bool` 欄位 + admin endpoint 接受
**session-with-admin OR X-Admin-Token**（c-β additive）— 既有 274 處
admin_headers 測試零改動。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bootstrap：把第一個 admin Member 升起來 (Priority: P1)

擁有者用既有 `X-Admin-Token` 把某個 Member 設為 `is_admin=true`。該 Member
下次登入後 session 就帶 admin 權限，可直接訪問 `/admin/*`。

**Why this priority**：沒有 bootstrap 路徑，admin UI 永遠沒人能用。

**Independent Test**：
1. 後端啟動，未有任何 admin Member
2. 用 X-Admin-Token 對 alice@x.com 跑 `PATCH /admin/members/{id} {"is_admin": true}`
3. alice 用一般 local password 登入
4. alice 的 `/me` response 含 `is_admin: true`

**Acceptance Scenarios**:

1. **Given** alice 已是 active Member、is_admin=false，**When** 持
   X-Admin-Token 的人 PATCH `is_admin=true`，**Then** alice 的 DB 欄位更新、
   audit log 記錄。
2. **Given** alice 已 is_admin=true 且已登入，**When** 訪 `GET /me`，
   **Then** response 含 `is_admin: true`。
3. **Given** alice is_admin=true 並登入，**When** 訪 `GET /admin/members`，
   **Then** 200（session-with-admin 通過）。
4. **Given** bob is_admin=false 並登入，**When** 訪 `GET /admin/members`，
   **Then** 403 `forbidden` `not_admin`。
5. **Given** 無 session 但有 X-Admin-Token header，**When** 訪
   `GET /admin/members`，**Then** 200（既有 token 通過保留）。

---

### US2 — Admin nav 條件渲 (Priority: P1)

`is_admin=true` 的 member 在 AppShell header 看到「Admin」連結；非 admin
member 看不到也訪不到。

**Acceptance Scenarios**:

1. **Given** alice is_admin=true 登入，**When** 看 header，**Then**「Admin」
   nav link 出現在 Dashboard / Catalog 之後。
2. **Given** bob is_admin=false 登入，**When** 看 header，**Then** 無
   Admin link；直接訪 `/admin/members` 顯示「無權限查看」內嵌頁（不 redirect）。
3. **Given** alice 點 Admin link，**When** 跳轉，**Then** 預設導向
   `/admin/members`。

---

### US3 — Admin: 成員管理 (Priority: P1)

`/admin/members`：列表 + 新建 + 編輯（disable / re-enable / 升 admin / 降
admin）+ 刪除。

**Independent Test**：admin 訪頁面 → 看到所有 Member 列表；點「新建」開
dialog，填 email + provider + password → 提交 → 列表多一筆。

**Acceptance Scenarios**:

1. **Given** 3 個既有 Member，**When** admin 訪 `/admin/members`，**Then**
   表格顯示 3 筆，每筆含 email、provider、status、is_admin badge、操作按鈕。
2. **Given** admin 點「新建 Member」，**When** dialog 開、填表、submit，
   **Then** POST `/admin/members`、列表 invalidate + 重 fetch、toast「已建立」。
3. **Given** admin 點 row 的「升 admin」，**When** 確認，**Then** PATCH
   is_admin=true、表格更新。
4. **Given** admin 點「停用」，**When** 確認，**Then** PATCH status=disabled、
   badge 變色。
5. **Given** 表單驗證失敗（email 格式錯），**When** submit，**Then** 不發
   request，顯示欄位錯誤訊息。
6. **Given** 後端 409（duplicate email），**When** 收到，**Then** toast 紅
   字錯誤、dialog 不關。

---

### US4 — Admin: Allocation 管理 (Priority: P1)

`/admin/allocations`：列表（含跨 Member）+ 新建 + 調 quota / `quota_locked` /
`is_service_allocation` + 撤回。

**Acceptance Scenarios**:

1. **Given** 5 個 allocation 跨 3 個 Member，**When** admin 訪
   `/admin/allocations`，**Then** 表格顯示 5 筆 + Member email column。
2. **Given** admin 點「新建」，**When** 選 Member + 填 model + （可選）
   quota / service-flag → submit，**Then** POST `/admin/allocations`、
   dialog 顯示新生成的 token（一次性）。
3. **Given** admin 點某 row 的「調 quota」，**When** dialog 改 quota → submit，
   **Then** PATCH `/admin/allocations/{id}` quota_tokens_per_month + 更新。
4. **Given** admin 點「撤回」，**When** 確認，**Then** DELETE 對應 endpoint、
   status badge 變 revoked。
5. **Given** filter「只顯示 active」switch on，**When** 切換，**Then** 表格
   只剩 active。

---

### US5 — Admin: Usage Dashboard (Priority: P1)

`/admin/usage`：按時間區間 + group_by (member / allocation / model) 切分查
詢；表格顯示 token / cost；右上角 CSV / JSON 匯出按鈕（觸發瀏覽器下載）。

**Acceptance Scenarios**:

1. **Given** admin 訪 `/admin/usage`，**When** 預設載入（過去 30 天 +
   group_by=member），**Then** 表格顯示按 member 切分的 token 與 cost 數字。
2. **Given** admin 切 group_by=model + 改時間區間到「本月」，**When** URL
   query 更新，**Then** 表格重 fetch + 顯示新結果。
3. **Given** admin 點「下載 CSV」，**When** click，**Then** 觸發瀏覽器下載
   `usage-<from>-<to>.csv`。
4. **Given** filter 時間 invalid (from > to)，**When** 後端回 400，**Then**
   toast「時間區間不合法」+ 表格不清空。

---

### US6 — Admin: Quota Pool 監控 + 手動 trigger (Priority: P1)

`/admin/quota-pool`：狀態卡（T / reserved / distributable / pool members）+
「手動 rebalance」按鈕 + RebalanceLog 列表（含 detail drawer）。

**Acceptance Scenarios**:

1. **Given** admin 訪 `/admin/quota-pool`，**When** 載入，**Then** 顯示
   `total_T`, `reserved.service`, `reserved.locked`, `distributable`,
   `pool_member_count`, `floor`, `last_rebalance_at`。
2. **Given** admin 點「手動 rebalance」+ 確認，**When** POST，**Then**
   toast 顯示「rebalance done: scanned=X, changed=Y」+ 狀態卡 + log 列表
   重 fetch。
3. **Given** rebalance 失敗（409 pool_exhausted），**When** toast 顯示 →
   admin 看到具體錯誤碼 + message。
4. **Given** 列表中某 RebalanceLog row 點開，**When** drawer 開，**Then**
   顯示完整 details（per-allocation before/after）。
5. **Given** T=0（pool disabled），**When** 訪頁面，**Then** 狀態卡顯示
   「池已停用」+ 手動 trigger 按鈕灰掉。

---

### US7 — Admin: Catalog 預覽 (Priority: P2)

`/admin/catalog`：admin 也能看 catalog（與 member view 同 UI，但走 admin
nav 入口；用來確認新載入的 YAML 內容生效）。

**Why P2**：catalog 本來就 member-visible；admin 預覽純粹是「我也想看」，
不是新功能。

**Acceptance Scenarios**:

1. **Given** admin 訪 `/admin/catalog`，**When** 載入，**Then** 與
   `/catalog` 顯示相同內容（重用 3b.1 `CatalogPage` 元件）。
2. **Given** 從 `/admin/catalog` 點某模型卡片，**When** 跳轉，**Then** 跳到
   `/admin/catalog/{slug}` 重用 `CatalogDetailPage`。

---

### US8 — Admin: RebalanceLog 完整檢視 (Priority: P2)

US6 已包含 inline list + drawer；本 US 是補強單獨路由 `/admin/rebalance-log`
方便深入查詢。

**Acceptance Scenarios**:

1. **Given** admin 訪 `/admin/rebalance-log?limit=50`，**When** 載入，
   **Then** 顯示最近 50 筆，含 triggered_by + scanned + changed 等欄位。
2. **Given** 點某 row，**When** 跳 `/admin/rebalance-log/:id`，**Then** 顯示
   完整 details JSON 並有「複製 JSON」按鈕。

### Edge Cases

- **非 admin member 直接訪 admin URL**：useAuth 拿 `is_admin=false` →
  顯示「無權限查看」內嵌頁；不跳 login（保持登入 session）
- **admin session 過期**：API 回 401 → 既有 `api:unauthorized` 機制觸發 →
  跳 login
- **admin 把自己降為非 admin**：操作完成後立即 invalidate auth context；
  下次 admin route 訪問即拒；應在 UI 加確認步驟（dialog 警告）
- **PATCH is_admin=false 把所有 admin 都降光**：後端 MUST 拒（保證至少 1 個
  admin 存在）— 否則沒人能再升 admin
- **csv download 在不允許 popup 的環境**：用 `<a download>` + Blob URL，
  瀏覽器原生視為下載而非 popup
- **新建 allocation 後 token 只顯示一次**：dialog 含「複製 token」+
  「我已複製」確認按鈕；關閉後 token 從前端 state 清除（不存 localStorage）

## Requirements *(mandatory)*

### Backend extension

- **FR-001**: 新增 `members.is_admin: bool` 欄位（default `false`）；
  Alembic migration 0007；既有 row 自動 false。
- **FR-002**: `Member.is_admin` ORM 欄位；`/me` response 加入 `is_admin`。
- **FR-003**: 新 dep `require_admin(member_or_token)`：
  - 若 request 有有效 X-Admin-Token → 通過（既有行為，**不破壞**現有測試）
  - 若 request 有 active session 且 `member.is_admin=true` → 通過
  - 否則 401（無認證）或 403 `not_admin`（已登入但非 admin）
- **FR-004**: 既有 `require_admin_token` 改為 `require_admin` 的別名（or
  保留並讓兩者並存）；既有 admin endpoints 一律走 `require_admin`，所以
  既有 274 處 admin_headers 測試**不需改動**。
- **FR-005**: `PATCH /admin/members/{id}` 接受新欄位 `is_admin: bool`；
  audit log 記錄 `member_promoted` / `member_demoted` event。
- **FR-006**: 後端 MUST 拒絕「把唯一 admin 降為非 admin」— 回 409
  `last_admin_cannot_demote`。

### Frontend — Admin auth + Shell

- **FR-010**: `AuthContext.member` 加 `is_admin: boolean` (default false 若
  /me 沒回此欄位)。
- **FR-011**: `AppShell` header 含「Admin」nav link 當且僅當
  `member.is_admin === true`。
- **FR-012**: 新 component `<AdminRoute>` 包在 `<ProtectedRoute>` 內：
  - status=loading → spinner
  - is_admin=false → 內嵌「無權限查看」+ 回首頁按鈕（不 redirect）
  - is_admin=true → render children
- **FR-013**: admin 路由 `/admin/members`、`/admin/allocations`、
  `/admin/usage`、`/admin/quota-pool`、`/admin/catalog`、`/admin/rebalance-log`
  皆包在 `<AdminRoute>` 內；`/admin` 重導 `/admin/members`。

### Frontend — Admin Members 視圖

- **FR-020**: `/admin/members`：表格顯示所有 member（email、provider、
  status、is_admin、created_at、操作按鈕）。
- **FR-021**: 「新建 Member」對話框：email + provider (local_password /
  external) + initial_password (僅 local) + send_invitation switch。
- **FR-022**: 行內操作 dropdown：升 admin / 降 admin / 停用 / 啟用 / 重設密
  碼 / 刪除（含確認 dialog）。
- **FR-023**: 客戶端表單驗證：email 格式、密碼 ≥ 12 字元；後端錯誤統一走
  toast。

### Frontend — Admin Allocations 視圖

- **FR-030**: `/admin/allocations`：表格顯示所有 allocation（含跨 member、
  subject_snapshot、resource_model、status、quota、is_service、token_prefix、
  created_at、操作按鈕）。
- **FR-031**: filter sidebar/bar：status (active/revoked/all)、member、
  service-only switch — 用 URL search params 同 3b.1 catalog 模式。
- **FR-032**: 「新建 Allocation」對話框：member 下拉（搜尋） + model +
  （可選）quota + is_service_allocation + note。
- **FR-033**: 新建成功 dialog 顯示一次性 token + 複製按鈕 + 「我已複製」
  關閉。
- **FR-034**: 行內操作：調 quota / 切 quota_locked / 切 is_service / 撤回
  （DELETE）。

### Frontend — Admin Usage 視圖

- **FR-040**: `/admin/usage`：date range picker + group_by 切換器 +
  service_only switch + 結果表格。
- **FR-041**: 表格欄位依 group_by 變動：member → email + total_tokens +
  cost；allocation → token_prefix + member email + tokens + cost；model →
  model name + tokens + cost。
- **FR-042**: 右上角「下載 CSV」、「下載 JSON」按鈕，呼叫 `/admin/usage.csv`、
  `/admin/usage.json`，觸發瀏覽器下載。
- **FR-043**: URL 反映 filter state（date range + group_by + service_only），
  可分享連結。

### Frontend — Admin Quota Pool 視圖

- **FR-050**: `/admin/quota-pool`：狀態卡（T / reserved / distributable / N /
  floor / last_rebalance_at）。
- **FR-051**: 「手動 rebalance」按鈕：確認 dialog → POST → toast 顯示結果。
- **FR-052**: RebalanceLog 列表（最近 20 筆）+ 「載入更多」cursor。
- **FR-053**: 點某 row → drawer / dialog 顯示完整 details JSON。

### Frontend — Admin Catalog 視圖

- **FR-060**: `/admin/catalog` 與 `/admin/catalog/:slug` 直接 mount 3b.1
  既有 `CatalogPage` 與 `CatalogDetailPage`（用同 component，但路由前綴改變）。
- **FR-061**: 「回 admin」連結回 `/admin/members`。

### Frontend — Admin RebalanceLog 視圖（補強）

- **FR-070**: `/admin/rebalance-log?limit=N`：列表。
- **FR-071**: `/admin/rebalance-log/:id`：單筆完整 details + 「複製 JSON」
  按鈕。

### shadcn 元件新增

- **FR-080**: `table`、`dialog`、`alert-dialog`、`dropdown-menu`、`form`
  (整合 react-hook-form + zod)、`select`、`textarea`、`popover`。

### NON-GOAL

- **FR-090** (NON-GOAL): Playwright E2E（留 3b.7）
- **FR-091** (NON-GOAL): 用量圖表（純表格 + 數字；圖表留 3b.7 polish）
- **FR-092** (NON-GOAL): WebSocket / SSE 即時更新（手動 refetch 即可）
- **FR-093** (NON-GOAL): 多選批次操作（一次一筆）
- **FR-094** (NON-GOAL): 暗黑模式 / 主題切換
- **FR-095** (NON-GOAL): admin 自訂 dashboard 排版
- **FR-096** (NON-GOAL): admin 操作 audit viewer UI（既有 audit log 已存
  於 DB；管理員查詢留未來階段）

### Key Entities

- **Member**（既有，擴一個欄位）：
  - +`is_admin: bool` 預設 false

無新表。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: bootstrap：用 X-Admin-Token PATCH 設 is_admin=true 後，該
  member 用一般 login 即可訪 `/admin/members` 200。
- **SC-002**: 既有 274 處 admin_headers 測試**零修改** + 全綠（無回歸）。
- **SC-003**: 非 admin member 直接訪 admin route → 內嵌「無權限」（**不
  redirect 到 login**）。
- **SC-004**: 5 個 admin 視圖各自至少 3 個 acceptance scenario 通過 manual
  test（quickstart §3-§7）。
- **SC-005**: usage CSV 下載：點按鈕後瀏覽器產生 `usage-*.csv`，內容對應
  query filter。
- **SC-006**: 手動 quota-pool rebalance：點擊後 1 秒內看到狀態卡更新 +
  新 RebalanceLog row 出現於列表。
- **SC-007**: 唯一 admin 嘗試降自己 → 後端 409、UI toast「至少需保留一個
  admin」。
- **SC-008**: backend ≥ 199 + 新 ≥ 8 (is_admin contract + endpoint
  permission tests) = ≥ 207 tests 全綠。
- **SC-009**: frontend ≥ 43 + 新 ≥ 25 (5 視圖 × 平均 5 test) = ≥ 68 tests
  全綠。
- **SC-010**: TDD：test commit 早於 impl commit（前後端皆然）。
- **SC-011**: Bundle size ≤ 700KB gzipped（從 120KB 預期加 ~150KB；shadcn
  form/dialog 等是大頭）。

## Assumptions

- **Admin 數量規模**：≤ 10 個 admin（不做 admin role / permission 細分）
- **bootstrap 用既有 X-Admin-Token**：環境變數 `ADMIN_BOOTSTRAP_TOKEN`
  已存在；不引入新 env
- **Admin UI 不做行動版**：min width 1024px
- **CSV 下載交瀏覽器處理**：不在 SPA 內 parse；FastAPI StreamingResponse
  既有
- **Member.is_admin 預設 false**：既有 Member 升級後維持 false，需明確 PATCH
- **單 admin 限制**：「降光所有 admin」要拒；無「至少 N admin」規則
- **3b.7 E2E 將驗整體**：本階段每個視圖至少 5 個 component-level test，
  但跨視圖端到端等 3b.7 用 Playwright
