# Feature Specification: 憑證 UI 術語與層級收斂（統一「應用金鑰」、單一管理處、可改名）

**Feature Branch**: `031-credential-ui-consolidation`
**Created**: 2026-06-05
**Status**: Draft
**Input**: 把「金鑰 / 應用 / 憑證 / 裝置 / token」收斂成**單一名稱「應用金鑰」**、**單一管理處**；分配詳情頁的憑證區降**唯讀**並顯示連坐範圍以消除「撤一把無聲影響其他 model」；**應用金鑰可改名**（含自動產生的「預設」）。前端為主 + 一個改名端點，不動資料模型。

## 背景與問題

階段 18→20 把憑證模型從「per-device」演進到「scoped application key（一把金鑰綁一組 model）」，但**舊框架的 UI 沒清掉**，造成使用者混亂：

1. **一物多名**：同一個物件被叫「金鑰 / 應用 / 憑證 / 裝置 / token」，使用者不知道是不是同一件事。
2. **兩層清單同物**：dashboard 成員層「我的應用金鑰」與分配詳情頁「裝置與憑證」顯示同一批金鑰；一把跨多 model 的金鑰會同時出現在它涵蓋的每個 model 的分配頁。
3. **「裝置」心智已過時**：金鑰早已不是「一台裝置一把」，而是「一把可用一組 model」；但分配詳情與 device-flow 還在講「裝置」。
4. **無聲連坐（最危險）**：在「分配 A 的裝置清單」撤回一把，其實會讓該金鑰涵蓋的**其他 model 一起失效**，但 A 的視角看不出來——**UI 表面違反原則 1「撤銷單一憑證不影響其他」的承諾**。
5. **三個建立入口、三種 UX**；安裝 Codex 後冒出的金鑰與清單沒連起來。
6. **機器名卡住**：自動產生的「預設」無法改成有意義的名字。

目標：**一物一名（應用金鑰）、一處管理、分配詳情唯讀且看得到連坐範圍、可改名**。對應原則 6 可達性（白話、降低非技術者混淆）、原則 1（讓 UI 與「隔離」承諾一致）、原則 5（管理走單一路徑）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 一物一名、一處管理（Priority: P1）🎯 MVP

成員在 dashboard 的「我的應用金鑰」一處完成所有金鑰管理（建立、改名、改可用 model、重新產生、撤回）；全站對這個物件只用「**應用金鑰**」一個詞，不再看到「裝置 / 憑證 / 應用」混用。

**Why this priority**: 消除「一物多名 + 多處管理」是混亂的根；其餘都建立在統一名稱與單一入口上。

**Independent Test**: 走訪 dashboard、分配詳情、安裝 Codex、device 授權、如何呼叫各頁 → 對金鑰物件只出現「應用金鑰」；管理動作只在 dashboard 金鑰卡可做。

**Acceptance Scenarios**:

1. **Given** 全站任一頁面，**When** 提到這個持有 token 的物件，**Then** 一律稱「應用金鑰」（不混用裝置 / 憑證）。
2. **Given** 成員想建立 / 改名 / 改 model / 撤回 / 重新產生金鑰，**When** 操作，**Then** 入口只有 dashboard 的「我的應用金鑰」一處。

---

### User Story 2 - 應用金鑰可改名（Priority: P1）

成員可把金鑰改成有意義的名字（含自動產生的「預設」），不影響其 token 與可用 model。

**Why this priority**: 使用者明確要求；「預設」這種機器名卡著很難管理多把金鑰。

**Independent Test**: 對一把名為「預設」的金鑰改名為「我的筆電」→ 清單立即顯示新名、token 與可用 model 不變。

**Acceptance Scenarios**:

1. **Given** 一把金鑰（含「預設」），**When** 成員就地改名，**Then** 名稱立即更新，token / 可用 model / 狀態不變。
2. **Given** 改名，**When** 完成，**Then** 留下稽核紀錄（誰、何時、改哪把）。
3. **Given** admin，**When** 治理某成員金鑰，**Then** 也能改名（留稽核）。

---

### User Story 3 - 分配詳情降唯讀、看得到連坐範圍（Priority: P1）

在某個 model（分配）詳情頁，成員看到的是「**能用這個 model 的應用金鑰**」**唯讀**清單；每筆顯示它涵蓋的**全部 model**、並可連到該金鑰本尊去管理。此頁**不**提供撤回 / 新增 / 重新產生。

**Why this priority**: 直接消除「無聲連坐」——撤回只發生在能看到全部涵蓋 model 的本尊處，符合原則 1。

**Independent Test**: 一把金鑰涵蓋 A+B；在 model A 的詳情頁 → 看到該金鑰（標示「也涵蓋 B」）、無撤回鍵、有「前往管理」連到 dashboard 金鑰卡。

**Acceptance Scenarios**:

1. **Given** model A 詳情頁，**When** 檢視金鑰區，**Then** 列出「能用 A 的金鑰」、每筆顯示其**所有**可用 model、且**無**撤回 / 新增 / 重新產生鍵。
2. **Given** 該唯讀清單一筆，**When** 點「前往管理」，**Then** 導到 dashboard 金鑰卡（本尊）。

---

### User Story 4 - 撤回明示連坐 + 安裝 Codex 連得起來（Priority: P2）

撤回金鑰時，確認訊息明確說「**此金鑰涵蓋的 N 個 model 會一起失效**」；安裝 Codex 後產生的金鑰，使用者能在清單認出來源。

**Why this priority**: 把「連坐」從無聲變成明示；把安裝流程與金鑰清單接起來，減少「這把哪來的」疑惑。

**Independent Test**: 撤回一把涵蓋 2 個 model 的金鑰 → 確認框寫「2 個 model 會一起失效」；跑 Codex 安裝 → 清單出現可辨識來源的新金鑰。

**Acceptance Scenarios**:

1. **Given** 一把涵蓋多 model 的金鑰，**When** 按撤回，**Then** 確認訊息列出 / 計數會一起失效的 model。
2. **Given** 完成 Codex 安裝，**When** 看金鑰清單，**Then** 能辨識那把是 Codex 安裝產生的（命名 + 來源提示）；安裝卡亦說明「會在你的應用金鑰新增一把」。

---

### Edge Cases

- 改名為空字串 / 超長 → 擋下、給白話訊息（沿用既有名稱長度上限）。
- 分配詳情唯讀清單中，某金鑰已撤回 → 標示「已撤回」、不可點管理動作。
- admin 在成員層治理：成員不能看 / 改他人金鑰（沿用既有擁有者邊界）。
- 名稱改動不得影響 token 或可用 model（純標籤）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 全站對「持有 token、可用一組 model 的物件」MUST 統一稱「**應用金鑰**」；移除主要流程中的「裝置 / 憑證」用語（device-flow / 安裝卡 / 分配詳情 / 如何呼叫）。
- **FR-002**: 金鑰的**建立 / 改名 / 改可用 model / 重新產生 / 撤回** MUST 僅有**單一入口**（dashboard 的「我的應用金鑰」）。
- **FR-003**: 系統 MUST 允許成員**改金鑰名稱**（含自動產生的「預設」）；改名**不影響** token、可用 model、狀態；MUST 留稽核。
- **FR-004**: admin MUST 能改任一成員金鑰的名稱（留稽核）；成員自助限自己的金鑰。
- **FR-005**: 分配（model）詳情頁的金鑰區 MUST 為**唯讀**——列出「能用此 model 的金鑰」、每筆顯示其**全部**可用 model、提供連到金鑰本尊的入口；MUST **不**提供撤回 / 新增 / 重新產生。
- **FR-006**: 撤回金鑰的確認 MUST 明示「此金鑰涵蓋的哪些 / 幾個 model 會一起失效」。
- **FR-007**: 安裝 Codex 卡 MUST 說明「會在你的應用金鑰新增一把」；device 授權頁 MUST 以「應用金鑰」用語、其建立的金鑰可在清單辨識來源。
- **FR-008**: 既有後端 proxy / 計費 / 領取 / 既有 token 行為 MUST 零回歸（本功能只動 UI 與「改名」端點，不改資料模型）。

### Key Entities *(include if feature involves data)*

- **應用金鑰（Application Credential）**：沿用階段 20；本階段只新增「可改名」（`name` 可更新，純標籤），不改 scope / token / 計費語意。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 走訪所有相關頁面，金鑰物件**只用「應用金鑰」一個詞**（主要流程 0 處「裝置 / 憑證」混用）。
- **SC-002**: 金鑰的建立 / 改名 / 改 model / 重新產生 / 撤回**只有 1 個入口**（dashboard）。
- **SC-003**: 成員可把「預設」改成任意有意義名稱；改名後 token / 可用 model **100% 不變**。
- **SC-004**: 分配詳情頁金鑰區**唯讀**、每筆顯示其**全部**可用 model、且**無**撤回 / 新增 / 重新產生鍵；可連到本尊。
- **SC-005**: 撤回多 model 金鑰時，確認訊息**明示**會一起失效的 model（不再無聲）。
- **SC-006**: 既有 proxy / 計費 / 領取 / token 零回歸（既有測試全綠）；桌機 + 360px 手機不溢出。

## Assumptions

- **名稱定為「應用金鑰」**（對齊業界 application credential / API key；比「裝置」準確）。device-flow / 安裝情境的金鑰仍是同一物件，只是由安裝流程代為建立。
- **分配詳情金鑰區採「降唯讀」而非整個移除**——使用者看某 model 時仍想知道「哪些金鑰能用它」；資料用既有「scope 含此分配的金鑰」清單即可，免動後端。
- **唯一需要的後端改動是「改名」**：在既有「調整金鑰」端點多收一個選填名稱（member 自助 + admin），留稽核。其餘為前端。
- **舊的 per-allocation 管理端點保留**作 API 相容，但前端不再用於「管理」（只讀取顯示）。
- **不做**：改資料模型 / scope 語意 / 額度呈現；不移除後端 endpoints；不新增 migration。
- **平台 / 前端 stack** 沿用既有（React/Vite + shadcn/ui；FastAPI 後端僅一處改名端點）。
