# Feature Specification: Admin Workflow Consolidation

**Feature Branch**: `013-admin-ux-consolidation`
**Created**: 2026-05-25
**Status**: Draft
**Input**: User description: "Reorganize 11 admin pages around user journeys instead of entity CRUD"

## 問題陳述

Phase 5 結束時 admin 介面有 **11 個頁面**（成員 / 分配 / Provider 憑證 / Tag / Model 存取 / Catalog 管理 / 目錄（檢視）/ 用量 / 配額池 / Rebalance 記錄 / 稽核紀錄），每頁是針對一個資料 entity 的 CRUD。實際使用回饋：

- 完成一個常見任務（例：「讓 alice 用某 model」）要跑 **4-6 個頁面**
- 新 admin 不知從哪開始
- 多處重複功能：`Catalog 管理` / `Model 存取` / `目錄（檢視）` 都圍繞同一個 model entity，但管理面向（CRUD / 存取規則 / member 視角）拆三頁
- 看不出每個 model「對誰可見」要切到別頁
- 診斷「member X 為何看不到 model Y」沒有單一入口

根因：建構時以資料模型為主軸做頁面分解，未先設計 user journey。本 feature **不改任何資料 model**、不刪後端 endpoint，純粹重組 UI + 補 1-2 個輔助 endpoint，讓 admin 完成任務的路徑變短。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 新 admin 第一天上手 (Priority: P1)

**Why this priority**：admin onboarding 是所有後續工作的前置；如果 day-1 卡住，後面什麼都做不了。

第一次拿到 admin 帳號的人登入後，能在**單一頁面**看到「目前缺什麼設定」「下一步要做什麼」，順著做完即可有第一筆可運作的 allocation。

**Independent Test**：以全新 DB（無 provider / 無 catalog / 無 member 除 bootstrap admin / 無 allocation）登入，從 `/admin` 開始**只依頁面提示**操作，能在 **10 分鐘內**得到一筆能成功呼叫 proxy 的 allocation token，過程不需要外部文件指引。

**Acceptance Scenarios**：
1. **Given** 新 DB 空狀態，**When** admin 登入後到 `/admin`，**Then** 看到清楚的進度指示（如 0/N），每個未完成項目都有「現在去做」的明顯 CTA
2. **Given** 完成 provider 設定，**When** 回 `/admin`，**Then** 進度刷新；下一個未完成項目自動被視覺強調
3. **Given** 所有清單完成，**When** 進 `/admin`，**Then** 變成「日常運作」儀表板（顯示用量摘要 / 異常 / 最近活動），而不是繼續顯示 onboarding

### User Story 2 — 給某成員開通某 model 的端對端 (Priority: P1)

**Why this priority**：這是 admin **最高頻**任務，目前要跑 4-6 頁。

Admin 想讓 alice@company.com 能呼叫 `azure/gpt-4o-mini`。理想路徑：從一個入口（Member 或 Model）出發，看到「現在缺什麼」「補完即可」，最多 **2 個頁面跳轉**內完成。

**Independent Test**：在 catalog 已有 model、provider 已配 credential、alice 已是成員（無 tag）狀態下，admin 開通流程要在 **3 步以內**完成並驗證 alice 能呼叫 proxy 200。

**Acceptance Scenarios**：
1. **Given** Model A 設為 restricted + allow `["eng"]`、alice 無 tag，**When** admin 從 Model A 詳情點「給 alice 開通」，**Then** 一鍵自動把 alice 加入 eng tag（或開類似 UX 的快捷路徑）
2. **Given** alice 已能看到 model，**When** admin 在 Member alice 詳情點「建分配」並選 model，**Then** 不必再切到 `/admin/allocations`
3. **Given** alice 完成設定，**When** admin 在 alice 的詳情頁，**Then** 能看到「alice 目前能用的 model 清單」（合併目前散在多頁的資訊）

### User Story 3 — 以 tag 群組做存取規則 (Priority: P2)

**Why this priority**：組織內常見「給整個工程團隊存取 model 集合」「給 contractor 限制 model」這類批次規則。

Admin 在**一個地方**就能看到「某 tag 涵蓋哪些 member」「某 tag 允許 / 禁止哪些 model」，並可雙向編輯。

**Acceptance Scenarios**：
1. **Given** 在 Tag 詳情頁，**When** admin 看 vip tag，**Then** 同時看到「3 個 member 持有此 tag」「5 個 model 將此 tag 列為 allowed」「2 個 model 將此 tag 列為 denied」
2. **Given** 在 Tag 詳情頁，**When** admin 點某 member，**Then** 直接編輯該 member 是否仍歸屬此 tag
3. **Given** 在 Tag 詳情頁，**When** admin 點某 model，**Then** 直接跳到該 model 的存取設定

### User Story 4 — 診斷「為何 X 看不到 Y」(Priority: P2)

**Why this priority**：access policy 變複雜後，admin 必須能快速解釋「為什麼 bob 看不到 claude」。沒有這條路徑，admin 只能猜或翻 DB。

Admin 從**任一入口**（member 詳情 / model 詳情 / 通用診斷頁）能輸入 (member, model) pair，得到清楚的「可見 / 不可見 + 原因鏈」答案。

**Acceptance Scenarios**：
1. **Given** model 限制 `["vip"]`、bob 無 vip tag，**When** admin 在 model 詳情輸入「以 bob 視角預覽」，**Then** 顯示「不可見 — 原因：default_access=restricted 且 bob 的 tag 不命中 [vip]」並提供「給 bob 加 vip tag」按鈕
2. **Given** provider 無 active credential，**When** admin 在 model 詳情看，**Then** 顯示「對所有 member 不可見 — 原因：azure provider 無 active credential」並提供「去新增 azure credential」按鈕
3. **Given** model 命中 denied tag 規則，**When** 預覽，**Then** 答案清楚標明是 deny 規則先生效（非 allow 不命中）

### User Story 5 — 撤回 / 監控 / 異常處理 (Priority: P3)

**Why this priority**：日常維運。雖然每筆功能已存在，但分散：撤回 allocation 在 `/admin/allocations`、看異常在 `/admin/usage`、看 audit 在 `/admin/audit`、看 rebalance log 在 `/admin/rebalance-log`。

Admin 處理「某 member 在搞鬼，先停他」應該在一頁完成（看 member → 看其用量 / 異常 / 最近 audit → 一鍵 disable）。

**Acceptance Scenarios**：
1. **Given** 在 member 詳情，**When** admin 看異常欄，**Then** 看到該 member 最近一週 anomaly_detector 紀錄，含「啟用 quarantine」按鈕
2. **Given** 觀測類功能（用量 / 配額池 / Rebalance log / Audit）相關性高，**When** 整合進「觀測」單一入口（含 tabs / 分段），**Then** admin 不必在 nav 上看到 4 個獨立連結

### Edge Cases

- 11 頁壓縮後，**現有 deep link**（如別人 bookmark 了 `/admin/tags`）必須**仍可運作**（redirect 或保留）
- 跨頁 query state（如 audit 已篩選某 actor）應在跳頁時保留
- onboarding checklist 完成後再加新 entity（例砍掉所有 provider credential）應退回 onboarding 模式
- 「以 X 視角預覽」功能不能洩漏 X 的私人資訊（例 X 的 allocation token）給 admin（admin 本來就看得到，但不該透過「預覽」途徑）

## Requirements *(mandatory)*

### Functional Requirements

**頁面結構**
- **FR-001**: 系統 MUST 將既有 11 個 admin 頁面**重組為 6-7 個**入口（不刪 entity / 不改 DB schema）
- **FR-002**: 系統 MUST 提供 **Model**（合併現 Catalog 管理 + Model 存取 + 目錄檢視）統一頁
- **FR-003**: 系統 MUST 提供 **Member**（強化現 members 頁，含 inline tag / 該成員能用的 model 列表 / 建分配快捷）統一頁
- **FR-004**: 系統 MUST 提供 **Tag** 詳情頁，雙向顯示「持有此 tag 的 member」與「此 tag 涵蓋的 model 規則」
- **FR-005**: 系統 MUST 把觀測類（用量 / 配額池 / Rebalance log / 稽核）整合為 **觀測（Observability）** 單一入口，內可分 tab

**任務引導**
- **FR-006**: 系統 MUST 在 `/admin` 提供 onboarding checklist（已有，需強化下一步引導）
- **FR-007**: 任何 entity 缺失提示（例「該 model 對應 provider 無 credential」）MUST 內含**跳轉 button** 指向下一步該去的頁面 + 帶入 query 預填
- **FR-008**: User Story 2 端對端流程 MUST 可在**從 model 或 member 任一入口出發**達成，無需切回 `/admin/allocations`

**診斷工具**
- **FR-009**: 系統 MUST 提供「以指定 member 視角預覽 model 可見性」功能：給定 (member, model) 回 `{visible: bool, reason_chain: [...]}`
- **FR-010**: 此功能 MUST 提供新 backend endpoint：`GET /admin/members/{id}/visibility?model_slug=...` 或類似命名
- **FR-011**: 診斷結果 MUST 提供「修補」捷徑（加 tag / 設 credential / 改 policy）

**遷移**
- **FR-012**: 既有 admin 頁 URL（`/admin/tags`、`/admin/catalog-manage` 等）MUST 仍可訪問（redirect 到新位置或保留為 deep-link 短網址）
- **FR-013**: 既有後端 endpoint MUST 全數保留（不破壞 #12 已合的 API contract）

### Key Entities

無新增 entity。所有資料 model 沿用 Phase 5。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新 admin 從 0 狀態到第一筆可呼叫 proxy 的 allocation，**全程不需開外部文件**，10 分鐘內完成（US1）
- **SC-002**: 「讓 alice 用 model X」標準任務從目前 4-6 頁跳轉減為 **2 個頁面**內完成（US2）
- **SC-003**: 「為何 bob 看不到 claude」這類問題能在 **15 秒內**從 UI 給出含原因鏈的答案（US4）
- **SC-004**: Admin sub-nav 頂層連結數從 **11 條減為 6-7 條**（FR-001）
- **SC-005**: 既有 deep link（11 個舊路徑）100% 仍可訪問（無 404）
- **SC-006**: 既有後端 API contract test 全綠（無 endpoint 破壞）

## Assumptions

- 後端 entity / endpoint / 權限模型不變
- 沿用既有 UI stack（React 19 + shadcn + TanStack Query）
- 不引入 i18n（仍只繁中）
- 觀測類整合不改既有 export（CSV / JSON 仍按原路徑）
- 「以 X 視角預覽」不需快取，每次即時計算（百人量級）
- 砍頁面後**舊 URL redirect** 用前端 React Router 處理，不影響後端
