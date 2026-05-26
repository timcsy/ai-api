# Feature Specification: 自助領取憑證 (Self-Service Allocation)

**Feature Branch**: `015-self-service-allocation`
**Created**: 2026-05-26
**Status**: Draft
**Input**: User description: "access policy 允許的成員可在 member dashboard 對 admin 已開放自助領取的 model 一鍵領取 allocation；每 model admin opt-in 並設預設配額上限；走既有 quota pool 與撤回機制；撤回後需 admin 解鎖才能重領；每成員每 model 最多一張有效自助 allocation"

## 問題陳述

目前要讓一個成員能呼叫某 model，**admin 必須手動建一筆 allocation**（`POST /admin/allocations`，`require_admin_token`）。成員登入後只能「看」自己的憑證（`GET /me/allocations`），不能自己開。量大時 admin 是瓶頸——每個人、每個 model 都要 admin 經手。

同時，存取控制已經有完整的兩層（credential gate ∩ access policy + tag），admin 其實已經宣告了「誰可以用哪些 model」。既然如此，**被允許的成員應該能自己領一張憑證開始用**，不必再等 admin 逐筆建立。

本 feature 讓 admin **逐 model 開放自助領取**（並設該 model 的自助預設配額上限）；被 access policy 允許的成員即可在 dashboard 一鍵領取一張綁定自己的 allocation。領到的憑證與 admin 手動建立的完全等價（可追蹤、有配額、走 quota pool、可撤回）。撤回保持止血意義：被撤回後該成員在 admin 解鎖前不能自己重領。

本 feature **不改既有 access policy / credential gate / quota pool / 撤回機制**——自助領取只是 allocation 的另一個**發起入口**，多了「逐 model 開關」「撤回後鎖定重領」兩個控制。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin 逐 model 開放自助領取並設配額 (Priority: P1)

Admin 想對某些 model（例如已穩定、低成本的 `gpt-5.4-mini`）開放讓成員自己領憑證，省去逐筆建立；同時要能限制每張自助憑證的月配額上限，避免失控。

**Why this priority**：沒有 admin 先開放，成員就無從自助領取；這是整個 feature 的前置開關與安全閥。

**Independent Test**：admin 對某 model 開啟「允許自助領取」並設預設配額（如 50,000 tokens/月），查該 model 設定已反映；對另一個 model 維持關閉。不需任何成員動作即可驗證。

**Acceptance Scenarios**：
1. **Given** admin 在某 model 的設定，**When** 開啟「允許自助領取」並填預設月配額，**Then** 設定儲存，該 model 標記為可自助領取且帶該配額上限
2. **Given** 某 model 未開放自助領取，**When** 查詢其設定，**Then** 顯示為關閉（預設關閉）
3. **Given** admin 關閉某已開放 model 的自助領取，**When** 儲存，**Then** 之後成員不能再自助領取該 model（但**已領到的** allocation 不受影響、仍可用）

### User Story 2 — 成員一鍵自助領取憑證 (Priority: P1)

被 access policy 允許看到某 model、且該 model 已開放自助領取的成員，想在 dashboard 直接領一張可呼叫的憑證，不必找 admin。

**Why this priority**：這是 feature 的核心價值——把「取得可用憑證」從 admin 手動變成成員自助。

**Independent Test**：對一個已開放自助領取的 model，用一個被 access policy 允許的成員按「領取憑證」，得到一張綁定該成員、帶該 model 預設配額的 active allocation 與一次性 token，且該 token 可成功呼叫 `/v1`。

**Acceptance Scenarios**：
1. **Given** model 已開放自助領取且成員被 access policy 允許，**When** 成員按「領取憑證」，**Then** 系統建立一張綁定該成員、`origin=self_service`、配額=該 model 自助預設值的 allocation，並一次性顯示 token
2. **Given** 成員不被該 model 的 access policy 允許（tag 不符 / 被 deny / model restricted），**When** 嘗試領取，**Then** 拒絕，不建立 allocation
3. **Given** model **未**開放自助領取（即使成員看得到），**When** 嘗試領取，**Then** 拒絕並提示此 model 不開放自助領取
4. **Given** 成員已對某 model 有一張**有效（active）**自助 allocation，**When** 再次領取同一 model，**Then** 不重複發新的（回既有那張或提示已持有）
5. **Given** 成員領到自助憑證，**When** 用該 token 呼叫 `/v1` 且在配額內，**Then** 呼叫成功且可溯源到該 allocation（與手動建立的 allocation 行為一致）

### User Story 3 — 撤回後鎖定重領，需 admin 解鎖 (Priority: P2)

Admin 撤回某成員某 model 的自助憑證，意思是「現在不信任他用這個 model」。若成員能立刻自己再領一張，撤回就形同虛設。所以撤回後該成員對該 model 的自助領取需被鎖定，直到 admin 明確解鎖。

**Why this priority**：保住根公理的「即時撤回」止血意義；沒有它，自助領取會架空撤回。屬安全強化，排在核心流程之後。

**Acceptance Scenarios**：
1. **Given** 成員有一張某 model 的自助 allocation，**When** admin 撤回它，**Then** 該 allocation 立即失效，且該（成員, model）被標記為「鎖定重領」
2. **Given** 某（成員, model）處於鎖定重領，**When** 該成員嘗試再自助領取該 model，**Then** 拒絕並提示需 admin 解鎖
3. **Given** 某（成員, model）處於鎖定重領，**When** admin 執行「解鎖」，**Then** 該成員之後可再次自助領取（前提仍需 access policy 允許且 model 仍開放）
4. **Given** 鎖定重領狀態，**When** 查稽核，**Then** 撤回、解鎖、領取事件都有紀錄（誰、何時、哪個 model）

### Edge Cases

- **成員被 access policy 允許但 model 未開放自助**：看得到 model，但沒有「領取」入口 / 領取被拒（兩道獨立條件都要滿足）
- **領取後成員 tag 改變失去存取**：已領到的 allocation 不自動撤回（沿用現有行為）；但失去存取後不能再領（access policy 即時生效）
- **disabled 成員**：不能自助領取
- **model 自助開放後又關閉**：已領的不受影響；新領被拒
- **配額預設值未設（null）**：開放自助時必須填預設配額，不允許「開放但無上限」
- **同一 model 已有 admin 手動建的 allocation**：自助「每 model 最多一張有效」只計 `origin=self_service`；admin 手動建的另計
- **撤回的是 admin 手動建的 allocation（非自助）**：不觸發自助鎖定（鎖定只針對自助領取路徑）
- **領到的自助 allocation 進 quota pool**：月初 rebalance 比照一般非服務型 allocation（初始配額為該 model 自助預設值）

## Requirements *(mandatory)*

### Functional Requirements

**Admin 開放與配額**
- **FR-001**: 系統 MUST 讓 admin **逐 model** 開關「允許自助領取」（預設關閉）
- **FR-002**: admin 開啟某 model 自助領取時 MUST 同時設定該 model 的「自助領取預設月配額」；不允許「開放但未設配額」
- **FR-003**: admin 關閉某 model 自助領取 MUST 不影響該 model **已領出**的 allocation（只擋新領取）
- **FR-004**: 自助領取的開關與預設配額 MUST 可由 admin 查詢與修改，並寫稽核

**成員自助領取**
- **FR-005**: 成員 MUST 能透過 `POST /me/allocations`（或等義端點）對指定 model 自助領取一張 allocation
- **FR-006**: 系統 MUST 在領取時驗證全部條件，任一不符即拒絕且不建立 allocation：
  - 該 model `self_service_enabled = true`
  - 該成員通過該 model 的 credential gate ∩ access policy（與既有可見性判定一致）
  - 該成員對該 model 尚無**有效（active）**的自助 allocation
  - 該（成員, model）未處於「鎖定重領」
  - 成員為 active 狀態
- **FR-007**: 自助領取成功 MUST 建立一張 `origin=self_service`、綁定該成員、配額=該 model 自助預設值的 allocation，並**一次性**回傳 token
- **FR-008**: 自助領取的 allocation MUST 與 admin 手動建立的 allocation 在呼叫驗證、用量計量、quota pool、撤回上**完全等價**
- **FR-009**: 系統 MUST 限制每個（成員, model）最多一張**有效**自助 allocation

**撤回與鎖定**
- **FR-010**: admin 撤回一張**自助** allocation MUST 將該（成員, model）標記為「鎖定重領」
- **FR-011**: 處於「鎖定重領」時，該成員 MUST 不能自助領取該 model（直到解鎖）
- **FR-012**: admin MUST 能對某（成員, model）執行「解鎖」，解除鎖定重領
- **FR-013**: 領取、撤回、鎖定、解鎖 MUST 寫稽核事件（含成員、model、時間）

**可見性與相容性**
- **FR-014**: member dashboard MUST 顯示「可自助領取」的 model（access policy 允許 ∩ self_service_enabled），並提供「領取憑證」動作；已鎖定者顯示需 admin 解鎖
- **FR-015**: 既有 access policy / credential gate / quota pool / 撤回 / `GET /me/allocations` MUST 不因本 feature 改變行為
- **FR-016**: admin 手動建立 allocation 的既有流程（Phase 5.1 內嵌於成員詳情）MUST 不受影響

### Key Entities

- **ModelCatalog（既有，擴充）**：加「是否開放自助領取」與「自助領取預設月配額」兩個屬性
- **Allocation（既有，擴充）**：加「來源」標記（admin 手動 / 自助領取），讓「每 model 一張有效自助」與「撤回鎖定」能只作用於自助路徑
- **自助重領鎖定（新概念）**：表達某（成員, model）在自助 allocation 被撤回後、admin 解鎖前不可重領的狀態。屬性：成員、model、鎖定時間、解鎖資訊

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 被允許的成員對已開放 model 自助領取，**3 次點擊內、30 秒內**取得可用憑證，全程**不需 admin 介入**
- **SC-002**: 自助領取對 access policy 的遵守率 **100%**——不被允許的（成員, model）永遠領不到，即使該 model 已開放自助
- **SC-003**: 未開放自助領取的 model **100%** 無法被自助領取
- **SC-004**: 自助 allocation 被撤回後，該成員在 admin 解鎖前**重領成功率 0%**
- **SC-005**: 自助領取的 allocation 在呼叫 / 計量 / quota pool / 撤回的行為與手動建立**完全一致**（既有測試零回歸）
- **SC-006**: admin 開放/關閉某 model 自助領取、設定配額的操作可在 **1 分鐘內**完成

## Assumptions

- 「被 access policy 允許」沿用既有 `evaluate_visibility`（credential gate ∩ default_access ∩ deny/allow tags），不另立判定
- 自助領取的配額由**該 model 的自助預設值**決定（admin 每 model 設）；領到後比照一般非服務型 allocation 進 quota pool，月初 rebalance（初始值為該預設）
- 「每 model 最多一張有效自助 allocation」只計 `origin=self_service` 且 status=active；admin 手動建的不受此限
- 撤回鎖定只針對自助路徑；admin 手動建的 allocation 被撤回不會鎖定成員的自助領取
- 開放自助領取**必須**設配額上限（不提供「開放但無限額」），避免失控
- 不做「自助調整自己配額」「自助升級 model」（YAGNI；成員只能領 admin 已開放的、按 admin 設的配額）
- 不做 email 通知 / 審批流程（首版即時領取，靠 access policy + 逐 model 開關控管）
