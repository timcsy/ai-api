# Feature Specification: 階段 3b.1 — Member View

**Feature Branch**: `009-member-view`
**Created**: 2026-05-24
**Status**: Draft
**Input**: User description: "階段 3b.1 member view — dashboard + allocation detail + catalog browse + catalog detail；URL = filter single source of truth；含小幅後端 cursor pagination extension"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 一進門看到自己的全貌 (Priority: P1)

成員登入後第一頁是 `/dashboard`，立刻看到「我是誰、有哪些 active allocation、
這個月用了多少 tokens」。不用點任何連結就能回答這三個問題。

**Why this priority**：3b.1 最核心承諾 — vision「成員登入後可看到自己的憑證
與用量」之最低門檻。失去就退化成 3b.0 placeholder。

**Independent Test**：登入後 URL 自動跳 `/dashboard`；頁面顯示 member email +
provider + active allocations 列表（每筆含 model + 上月 token 數 + status badge）。

**Acceptance Scenarios**:

1. **Given** member 已登入 + 有 2 個 active allocation（gpt-4o-mini + dall-e-3），
   **When** 訪 `/dashboard`，**Then** 列表顯示 2 筆，每筆有 model name、
   token prefix、status badge、quota progress bar。
2. **Given** member 有 1 個 revoked allocation 與 1 個 active，**When** 預設
   檢視，**Then** 只顯示 active；切換「含已撤回」開關才顯示 revoked。
3. **Given** member 完全沒有 allocation，**When** 訪 dashboard，**Then** 顯示
   「尚未獲得任何分配，請聯絡管理員」的 empty state，**不是**空白頁面。
4. **Given** API 載入失敗（500），**When** 訪 dashboard，**Then** 顯示錯誤
   區塊 + 重試按鈕，UI 不崩。

---

### User Story 2 - 點進單筆 allocation 看細節 + 最近呼叫 (Priority: P1)

點 dashboard 上一筆 allocation → `/dashboard/allocations/{id}` 顯示完整資訊：
quota progress bar（這個月已用 / quota）、最近 20 筆呼叫 + 「載入更多」cursor
pagination。

**Why this priority**：vision「呼叫可追溯到分配 ID」的 member 端兌現 —
member 自助查自己的呼叫紀錄。

**Independent Test**：點任一 allocation → detail 頁顯示 quota bar；表格列
20 筆呼叫；點「載入更多」追加 20 筆。

**Acceptance Scenarios**:

1. **Given** allocation quota=1000，本月已用 750，**When** 訪 detail，**Then**
   progress bar 75%，文字「已用 750 / 1000」。
2. **Given** allocation `quota=null`（無上限），**When** 訪 detail，**Then**
   不顯示 progress bar，改顯示「無限額」標籤。
3. **Given** allocation 有 35 筆呼叫，**When** 訪 detail，**Then** 表格初始
   顯示 20 筆，「載入更多」追加剩餘 15 筆；之後按鈕消失。
4. **Given** 直接訪別人的 allocation id，**When** 後端回 403，**Then** 顯示
   「無權限查看」+ 回首頁連結（**不是** redirect 到 /login）。
5. **Given** allocation id 不存在，**When** 後端回 404，**Then** 顯示
   「找不到 allocation」。

---

### User Story 3 - 篩 catalog 找適合的模型 (Priority: P1)

進 `/catalog` 看到左 sidebar 多個 facet filter（capability 多選 AND、cost_tier、
modality_input、modality_output、recommended_for）+ 右側結果 grid。勾選 filter
即時更新；filter state 寫入 URL，可分享連結。

**Why this priority**：catalog 是 3b 的招牌 demo — 沒有 filter 跟 Phase 4
backend 配不上。

**Independent Test**：訪 `/catalog` → 看到 9 個模型卡片；勾「capability:
vision」+「capability: function-calling」+「cost_tier: low」→ 只剩 gpt-4o-mini；
URL 變成 `?capability=vision&capability=function-calling&cost_tier=low`；
複製 URL 開新分頁 → 同樣結果。

**Acceptance Scenarios**:

1. **Given** 9 個 active 模型（含 1 個 deprecated 預設隱藏），**When** 訪
   `/catalog`，**Then** 結果 grid 顯示 8 個卡片。
2. **Given** 沒勾任何 filter，**When** 點「capability: vision」checkbox，
   **Then** 結果即時更新，URL 變成 `?capability=vision`。
3. **Given** URL 已含 `?capability=vision&cost_tier=low`，**When** 直接訪
   該 URL，**Then** sidebar 對應 checkbox 預勾、結果已套用 filter。
4. **Given** 切換「含已停用」switch=true，**When** facet count 與結果重算，
   **Then** deprecated 模型也出現。
5. **Given** filter 命中 0 個結果，**When** 顯示，**Then** 顯示「沒有符合條件
   的模型，請放寬 filter」**而非**空白網格。

---

### User Story 4 - 看模型細節 + 複製 curl (Priority: P1)

點 catalog 卡片 → `/catalog/{slug}` 顯示完整 description、example_request
（curl + JSON body 切換 tab）、「複製 curl」按鈕（clipboard write）。

**Why this priority**：vision「不熟 LLM API 的成員看完目錄能自行開始試用」
的最後一哩 — 沒有「複製貼上即可跑」按鈕，目錄價值打折。

**Independent Test**：點 dall-e-3 → 看到 description；點「複製 curl」→
toast 提示「已複製」；貼到 terminal 換上自己的 `$TOKEN` 即可跑。

**Acceptance Scenarios**:

1. **Given** model 含 `example_request.curl` 字串，**When** 點「複製 curl」，
   **Then** clipboard 寫入該字串 + UI toast 提示。
2. **Given** model 含 `example_request.body` JSON，**When** 切換到「JSON」
   tab，**Then** 顯示 pretty-printed JSON。
3. **Given** model 是 deprecated（直接訪 URL），**When** 顯示 detail，**Then**
   頁首顯著的 warning banner + `deprecation_note` 內容。
4. **Given** slug 不存在，**When** 後端回 404，**Then** 跳本地 NotFound 頁。

---

### User Story 5 - Header nav + logout (Priority: P2)

每頁頂部 sticky header：左邊 logo + Dashboard / Catalog 兩個 nav link、右邊
member email + logout 按鈕。logout 後 cache 清空、跳 `/login`。

**Why this priority**：基礎導航；少了會卡在每頁。

**Independent Test**：登入後任一頁 header 都在；點 Catalog → 跳 `/catalog`；
點 logout → cookie 清除、跳 login。

**Acceptance Scenarios**:

1. **Given** 在 dashboard，**When** 點 header「Catalog」，**Then** 跳
   `/catalog`，nav link 高亮在 Catalog。
2. **Given** 已登入，**When** 點 header logout，**Then** 後端 cookie 清除、
   TanStack Query cache 清空、跳 `/login`。
3. **Given** logout 後重新登入別的 member，**When** 看 dashboard，**Then**
   顯示新 member 的資料（不是上一位的 cached 資料）。

### Edge Cases

- **未登入直接訪 /dashboard/allocations/{id}**：ProtectedRoute 跳 login，
  `?next=` 帶原 URL；登入後回原頁。
- **/me/allocations/{id}/calls 無 cursor 時的 race**：用 React Query 的
  `useInfiniteQuery`；同 allocation_id 只發一 query。
- **clipboard API 不可用（HTTP / Safari 老版）**：fallback 提示「請手動複製」+
  顯示完整文字。
- **filter URL 含未知 capability 值**：API 仍回 200 + 空陣列（FR Phase 4），
  UI 顯示「沒有符合條件的模型」。
- **dashboard 上月用量計算**：用 `/me/allocations` 既有 response 中各
  allocation 的近期 tokens（**不**新增後端 endpoint；若資料不夠精確就顯示
  「需查詢細節」）。

## Requirements *(mandatory)*

### Functional Requirements

#### Backend extension（最小幅）
- **FR-001**: 擴 `/me/allocations/{id}/calls` 支援 cursor pagination：
  - 新 query param: `limit` (default 20, max 100)、`before_id` (optional)
  - response 加 `next_before_id` field；null 表已無更多
  - 既有呼叫者（無 query param）行為不變（回最近 20 筆）
  - 含 1 個 contract test 驗 cursor 語意

#### 路由
- **FR-002**: 新增 `/dashboard`（取代 3b.0 placeholder `/`）
- **FR-003**: 新增 `/dashboard/allocations/{id}`
- **FR-004**: 新增 `/catalog`
- **FR-005**: 新增 `/catalog/:slug`（含 `:slug` 可帶 `/`）
- **FR-006**: 已登入訪 `/` MUST 自動重導 `/dashboard`

#### Header
- **FR-007**: sticky `<header>` 每個 protected route 都顯示：
  - 左：logo + Dashboard / Catalog 連結（active state 高亮）
  - 右：member email + Logout 按鈕

#### Dashboard
- **FR-008**: 顯示 member 基本資訊（email、provider、active allocation count）
- **FR-009**: allocations 列表預設只顯示 `status=active`；switch toggle 含
  `status=revoked`
- **FR-010**: 每筆 allocation 卡片含：model name、token_prefix、status badge、
  quota progress bar（若 quota 不為 null）、點擊跳 detail
- **FR-011**: Empty state：「尚未獲得任何分配，請聯絡管理員」

#### Allocation Detail
- **FR-012**: 顯示 quota progress bar：`(本月 total_tokens) / (quota)`；
  >100% 顯示紅色「超額」
- **FR-013**: 表格：呼叫時間 / model / status_code / outcome / total_tokens
- **FR-014**: 「載入更多」按鈕用 `useInfiniteQuery`；點擊追加；無更多時隱藏
- **FR-015**: 403 顯示「無權限」、404 顯示「找不到」— **非** redirect

#### Catalog list
- **FR-016**: 左 sidebar facet filter，呼叫 `GET /catalog/filters` 取
  dimension + count
- **FR-017**: 支援 facet：capability (AND, 多選)、cost_tier (single)、
  modality_input / modality_output (AND, 多選)、recommended_for (AND, 多選)
- **FR-018**: 「含已停用」switch；對應 `?include_deprecated=true`
- **FR-019**: filter state ↔ URL `useSearchParams`（**URL 是 single source
  of truth**；勾選 = 改 URL = 重 query）
- **FR-020**: 右側 grid 卡片：display_name、family badge、cost_tier badge、
  modality icons、recommended_for tags
- **FR-021**: 點卡片跳 `/catalog/:slug`
- **FR-022**: 無命中：「沒有符合條件的模型，請放寬 filter」

#### Catalog Detail
- **FR-023**: 顯示完整 description、modality_input/output、capabilities、
  context_window、cost_tier
- **FR-024**: example_request 用 Tabs：「curl」/「JSON body」
- **FR-025**: 「複製 curl」按鈕用 `navigator.clipboard.writeText`；
  toast 顯示「已複製」；clipboard 不可用 fallback 顯示文字 + 手動複製提示
- **FR-026**: deprecated 模型加 warning banner 顯示 `deprecation_note`

#### Auth + Cache
- **FR-027**: `logout()` MUST 呼叫 `queryClient.clear()` 清空 cache
- **FR-028**: 401 觸發 `api:unauthorized` 已在 3b.0 處理；本階段不重做

#### 不在本階段範圍
- **FR-029** (NON-GOAL): 用量圖表（純 progress bar + 數字；圖表留 3b.3）
- **FR-030** (NON-GOAL): admin 頁面（留 3b.2+）
- **FR-031** (NON-GOAL): 行動版響應式
- **FR-032** (NON-GOAL): 「用此模型建立 allocation」按鈕（admin 操作；留 3b.2）
- **FR-033** (NON-GOAL): 上月「總費用」顯示（避免擴後端 /me/usage 新 endpoint）
- **FR-034** (NON-GOAL): Playwright E2E（留 3b.7）

### Key Entities

無新 DB entity。後端 `/me/allocations/{id}/calls` 加 2 個 query param 是
唯一 schema 變動。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 登入後 5 秒內看到 dashboard 含 allocations 列表（不是 spinner
  卡住）
- **SC-002**: filter 即時：在 `/catalog` 勾選 capability checkbox 後 300ms
  內結果更新
- **SC-003**: filter state 同步 URL：勾任意 filter 後複製 URL 開新分頁，看到
  完全相同的勾選與結果
- **SC-004**: SC-002 演算 vision+function-calling+low → 唯一命中 gpt-4o-mini
  （與 Phase 4 SC-002 對齊）
- **SC-005**: catalog detail 點「複製 curl」→ clipboard 內容為完整 curl
  字串（測試環境用 mock clipboard 驗）
- **SC-006**: allocation detail 30 筆呼叫場景：初始顯示 20 筆，點 1 次「載入
  更多」追加 10 筆，按鈕消失
- **SC-007**: logout 後重新登入別位 member，dashboard 顯示新 member 資料
  （無 cache 殘留）
- **SC-008**: backend 195 + 1 new (cursor pagination contract test) + frontend
  21 prior + 新 ≥ 10 tests 全綠
- **SC-009**: TDD：test commit 早於 impl commit

## Assumptions

- **dashboard「上月 tokens」資料來源**：用 `/me/allocations` 既有 response，
  若該 response 不含 tokens 摘要，dashboard 顯示「點擊查看細節」連結而非數字；
  本階段**不**新增後端 endpoint。
- **catalog filter facet 計數**：直接呼叫 `GET /catalog/filters`，**不**做客戶端
  facet 重算（保證與 backend 一致）。
- **clipboard API**：HTTPS / localhost 才可用；HTTP 環境（dev 偶有）走 fallback。
- **shadcn 元件**：新增 `badge`、`progress`、`tabs`、`separator`、`scroll-area`、
  `checkbox`、`switch` — 同 3b.0 模式 hand-write from defaults。
- **header sticky 樣式**：top: 0 + backdrop blur；高度 ~56px。
- **dashboard / detail / catalog 共用 `<AppShell>` 元件**包裝 header + main slot。
