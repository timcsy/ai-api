# Phase 0 Research: 階段 10 使用體驗打磨收尾

## R1: 分配卡片的 display_name 來源

**Decision**: 後端 `/me/allocations` 序列化補 `display_name`。`list_my_allocations` 已建 `price_map`；比照再建一個 slug→display_name map（查 `model_catalog`），傳入 `_alloc_public`。

**Rationale**: `_alloc_public` 已回 `resource_model`(slug) + `price`，缺的只有 display_name。後端補一個欄位最乾淨——前端零額外請求、不需 catalog map 與 queryKey 管理（避開 experience「queryKey 撞鍵」）。orphan（slug 不在目錄）→ display_name 為 None，前端退回顯示 slug。

**Alternatives considered**: 前端另抓 catalog 取 map — 否決（多一次往返 + queryKey 風險，且 list_my_allocations 已在查 DB）。

## R2: 分配卡片現價

**Decision**: 直接用 `/me/allocations` 既有的 `price`（`{input_per_1k, output_per_1k}`），前端以既有 `lib/price-format` 的 `per1kToPer1m` 顯示每 1M（比照 `allocation-detail.tsx` 既有呈現）；price 為 null → 顯示「未定價」。

**Rationale**: price 已在資料裡、格式化已有；純前端複用，不新增邏輯（experience「同概念別做兩份」）。

## R3: 可自助領取卡片可點進詳情（US2）

**Decision**: 把 claimable 卡片外層包成可點區域導向 `/catalog/{slug}`；「領取憑證」鈕用 `e.stopPropagation()`（或將鈕置於 Link 之外）避免點鈕同時觸發導頁。

**Rationale**: claimable 資料已含 slug + display_name；只是加導頁。stopPropagation 處理 Edge「卡片可點 vs 內部按鈕」。

## R4: 新成員三步引導（US3）

**Decision**: 「我的分配」空狀態（`filtered.length === 0` 且非載入中）顯示三步：① 領取憑證 ② 複製 ③ 貼進 Authorization。已有分配則不顯示。

**Rationale**: 純前端條件渲染，靜態說明；服務願景「讓不會寫程式的人也能用」。

## R5: 呼叫端點單一可信來源（US4）— 修正認知

**現況（讀碼後）**：`dashboard.tsx` 的「API 端點」卡與 `api-usage-example.tsx` **都已用 `window.location.origin`/v1**（並非先前 knowie-judge 筆記所述的「一處 window.location.origin、一處 gateway_base_url」）。兩處其實已一致；dashboard 另有一段條件提示，當 `window.location.origin` 與 `member.gateway_base_url` 不同主機時，附帶顯示 `gateway_base_url`。

**Decision**: 抽一個單一 helper（如 `lib/api-base.ts` 的 `apiBaseUrl()` 回 `${window.location.origin}/v1`），dashboard 與 ApiUsageExample 都引用它——讓「呼叫端點」字面上只有一個來源、未來要改只改一處。保留 dashboard 的跨主機提示（用 `member.gateway_base_url`）作為輔助。

**Rationale**: 兩處已一致，但各自硬寫 `window.location.origin`；抽 helper 才是真正的「單一可信來源」，符合 experience「同概念別做兩份」。`window.location.origin` 是瀏覽器實際可達的入口（dev :47822 經 Vite proxy、prod 同 ingress），比 server 端 `BASE_URL` 更貼近使用者實況；`gateway_base_url` 留作跨主機 fallback 提示。

**Alternatives considered**: 全改用 `gateway_base_url` — 否決（瀏覽器同主機情境下 `window.location.origin` 才是使用者真正打的入口；BASE_URL 設錯時 window.location.origin 仍對）。

## R6: admin 配額調整改 shadcn Dialog（US5）

**Decision**: `admin/allocations.tsx` 的「調整配額」由 `prompt()` 改為 shadcn `Dialog` + 數字輸入：預填目前配額、空白＝無限額、擋非數字/負數，送出走既有 `patchMut`（`PATCH /admin/allocations/{id}`）。

**Rationale**: 一致性 + 輸入驗證（experience「原生 dialog 是另一種割裂」精神，比照階段 7 把 prompt 換 Dialog 的做法）。撤回的 `confirm()` 可後續再換 AlertDialog（非本刀必須，先聚焦配額）。

## R7: token 文案涵蓋自助（US6）

**Decision**: `dashboard.tsx` 既有 token 提示（「您的 API token 在管理員建立分配時一次性顯示…」）改為同時涵蓋「自助領取」與「管理員分配」兩種取得來源。

**Rationale**: 階段 6 起成員多為自助領取；純文案修正。

## 測試策略（TDD）

| 測試 | 類型 | 對應 |
|------|------|------|
| `/me/allocations` 回 `display_name`（來自目錄；orphan→null） | contract | FR-001 |
| 分配卡片顯示 display_name（slug 為輔）+ 現價（每 1M）；未定價標示；orphan 退回 slug | frontend RTL | FR-001/002, US1 |
| 可自助領取卡片點擊導 `/catalog/{slug}`；領取鈕不導頁 | frontend RTL | FR-003, US2 |
| 無分配 → 顯示三步引導；有分配 → 不顯示 | frontend RTL | FR-004, US3 |
| dashboard 與 ApiUsageExample base URL 來自同一 helper、一致 | frontend RTL/unit | FR-005, US4 |
| admin 調整配額走 Dialog；非法輸入被擋；空白=無限額 | frontend RTL | FR-006, US5 |
| token 提示文案含自助情境 | frontend RTL | FR-007, US6 |
| 既有測試零退化（含 /me/allocations 既有欄位） | 全套 | FR-008, SC-006 |

無 NEEDS CLARIFICATION 待解（R5 認知已修正並定案）。
