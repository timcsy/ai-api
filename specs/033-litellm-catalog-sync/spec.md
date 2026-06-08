# Feature Specification: 模型目錄 ↔ LiteLLM 登錄表對接

**Feature Branch**: `033-litellm-catalog-sync`
**Created**: 2026-06-08
**Status**: Draft
**Input**: admin 新增 model 時選 LiteLLM slug 即自動帶入 context/modality/能力與建議價（殺冷啟動）、slug 預設＝key 名可改；自訂 deployment 可指定對照基礎模型借中繼資料、價格自訂；每欄記來源（litellm vs 手改）+ 匯入快照；維護時一鍵「檢查 LiteLLM 更新」線上抓最新登錄表、逐欄列舊→新差異並標來源、admin 選擇性採納，採納價格 append 一筆價目版本帶 litellm 來源註記；線上抓 timeout + 回退隨套件固定版。**價目表仍是計費唯一真理，LiteLLM 只給建議。**

## 背景與問題

管理員把模型加進目錄時，要手打 context window、modality、能力旗標、價格——**冷啟動很痛**，且容易填錯或過時。LiteLLM（平台已用的上游抽象層）本身**內建一份涵蓋數千個模型的登錄表**，含 provider、context、能力與公開牌價，且 key 命名與我們的 `provider/model` slug 慣例一致。把它接起來，可在「新增時」一鍵帶入、在「維護時」一鍵對照更新——大幅降低管理員的手動成本。

但有條紅線：**計費的價格必須維持可稽核、反映本組織實際成本**（企業／談判價 ≠ 公開牌價），所以 LiteLLM 只能當**建議來源**，不能變成計費真理。任何採納都要留痕、可回溯，且**絕不自動覆寫管理員的手動設定**——否則就成了「兩條路徑管同一件事」的並行 drift。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 新增模型時一鍵帶入（Priority: P1）🎯 MVP

管理員新增模型時，從 LiteLLM 登錄表搜尋並選一個模型，系統自動把 context、modality、能力、建議價填進表單；slug 預設成該 key 名，可再修改。

**Why this priority**: 殺冷啟動是本功能最大、最立即的價值；其餘建立在這套帶入機制上。

**Independent Test**: 進新增模型頁 → 搜尋「gpt-4o」→ 選 `azure/gpt-4o` → context/modality/能力/建議價自動填好、slug 預設 `azure/gpt-4o` → 存檔成功。

**Acceptance Scenarios**:

1. **Given** 管理員在新增模型頁，**When** 搜尋並選一個 LiteLLM 模型，**Then** 系統帶入 context window、modality、能力旗標與**建議價**，slug 預設為該 key。
2. **Given** 已帶入的表單，**When** 管理員修改任一欄（含 slug）後存檔，**Then** 以修改後的值建立模型，且被改過的欄位標記為「手動」。
3. **Given** 帶入的建議價，**When** 管理員存檔，**Then** 建立一筆價目版本並註記來源為 LiteLLM（含版本）。

---

### User Story 2 - 自訂 deployment 借對照基礎模型（Priority: P1）

管理員為自訂部署名（如 `azure/gpt-5.4`，不在 LiteLLM 登錄表）建模型時，可指定一個 LiteLLM「對照基礎模型」來借中繼資料，價格自訂。

**Why this priority**: 我們的實際部署常用自訂名、不在登錄表（已實測 coverage 非全有）；沒有這條，自訂模型就退回純手打，殺冷啟動的價值殘缺。

**Independent Test**: 新增 slug `azure/gpt-5.4`（登錄表查無）→ 指定對照基礎模型 `azure/gpt-4o` → 借入其 context/modality/能力 → 價格自填 → 存檔。

**Acceptance Scenarios**:

1. **Given** 一個 LiteLLM 查無的 slug，**When** 管理員指定一個對照基礎模型，**Then** 系統借入該基礎模型的中繼資料（標記來源為 LiteLLM-借用），slug 維持自訂。
2. **Given** 借用中繼資料的模型，**When** 管理員未填價或自填價，**Then** 價格以管理員輸入為準（不自動帶基礎模型的價）。

---

### User Story 3 - 來源標記與匯入快照（Priority: P1）

每個被 LiteLLM 帶入的欄位都標記「來源＝LiteLLM」並保存匯入當下的 LiteLLM 值快照；管理員手改過的欄位標記「來源＝手動」。

**Why this priority**: 這是 US4「檢查更新」能正確運作、且不覆寫手動設定的前提；也是可追蹤性的落地。

**Independent Test**: 帶入後存檔的模型 → 檢視其欄位來源 → LiteLLM 帶的標 LiteLLM、手改的標手動；保存了匯入快照值。

**Acceptance Scenarios**:

1. **Given** 經 LiteLLM 帶入後存檔的模型，**When** 檢視欄位來源，**Then** 每欄標示 LiteLLM 或手動，且保存匯入時的 LiteLLM 快照值。
2. **Given** 管理員事後手改某欄，**When** 存檔，**Then** 該欄來源轉為「手動」。

---

### User Story 4 - 一鍵檢查 LiteLLM 更新並選擇性採納（Priority: P2）

管理員按「檢查 LiteLLM 更新」，系統線上抓最新登錄表、與目前值（及匯入快照）逐欄比對，列出「舊→新」差異並標示各欄來源；管理員勾選要採納的更新後套用，採納的價格以新版本附加（留 LiteLLM 來源）。

**Why this priority**: 維護面的價值；建立在 US1–US3 的帶入與來源標記之上，故排後。

**Independent Test**: 對一個 LiteLLM 帶入的模型，模擬登錄表新值（價/ context 改變）→ 按檢查 → 列出舊→新 + 來源 → 勾選採納 → 套用後值更新、價格 append 新版本帶 LiteLLM 來源。

**Acceptance Scenarios**:

1. **Given** 已對接 LiteLLM 的模型，**When** 按「檢查更新」，**Then** 系統抓最新登錄表並逐欄列出「目前值 → LiteLLM 新值」差異，並標各欄來源（LiteLLM／手動）。
2. **Given** 差異清單，**When** 管理員勾選若干欄採納並套用，**Then** 僅被勾選的欄更新；**未勾選與手動欄不動**。
3. **Given** 採納一筆價格更新，**When** 套用，**Then** **附加一筆新價目版本**（不覆寫舊版）並註記 LiteLLM 來源與版本。
4. **Given** 線上抓取失敗（網路／逾時），**When** 按檢查更新，**Then** 在逾時內回退到隨套件固定的那份登錄表並明確告知是回退結果，不卡住。

---

### Edge Cases

- **登錄表查無 slug**：新增時走 US2 對照基礎模型；檢查更新時標「LiteLLM 無此模型」、不報錯。
- **管理員全手改**：檢查更新時所有欄皆「手動」→ 只提示、無自動採納項。
- **線上抓被網路/防火牆擋**：逾時 → 回退固定版 + 明確標示。
- **建議價與現價差異極大**：照常列差異，由管理員判斷是否採納（系統不替他決定）。
- **採納後想反悔**：因價目 append-only，舊版本仍在、可再採納/手改成回舊值（留痕）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 新增模型時，系統 MUST 提供「從 LiteLLM 登錄表搜尋並選模型」的方式，選定後自動帶入 context window、modality、能力旗標與**建議價**，slug 預設為該 key 且可修改。
- **FR-002**: 對 LiteLLM 查無的自訂 slug，系統 MUST 允許指定一個「對照基礎模型」借入中繼資料（slug 維持自訂、價格由管理員決定）。
- **FR-003**: 系統 MUST 為每個模型的每個可同步欄位記錄**來源**（LiteLLM／LiteLLM-借用／手動）與**匯入時的 LiteLLM 快照值**。
- **FR-004**: 管理員手改任一同步欄位後，該欄來源 MUST 轉為「手動」。
- **FR-005**: 系統 MUST 提供「檢查 LiteLLM 更新」動作：線上抓最新登錄表，與目前值/快照逐欄比對，列出「舊→新」差異並標各欄來源。
- **FR-006**: 採納更新 MUST 為**選擇性**（逐欄勾選）；未勾選欄與「手動」欄 MUST NOT 被自動更新。
- **FR-007**: 採納一筆價格更新 MUST 以**附加一筆新價目版本**呈現（append-only、不覆寫），並註記 LiteLLM 來源與版本。
- **FR-008**: 線上抓取 MUST 有逾時；逾時/失敗 MUST 回退到隨套件固定的登錄表並明確告知為回退結果。
- **FR-009**: 計費 MUST 持續以平台自有的版本化價目表為唯一真理；LiteLLM 僅作建議，MUST NOT 直接驅動計費。
- **FR-010**: 本功能 MUST NOT 在 proxy 呼叫熱路徑線上抓登錄表（只在管理員的新增/檢查動作）。
- **FR-011**: 既有目錄、價目、計費、proxy MUST 零回歸。

### Key Entities *(include if feature involves data)*

- **模型目錄項（既有 `ModelCatalog`）**：新增「**欄位來源標記**」與「**LiteLLM 匯入快照**」的關聯資訊（記錄哪些欄來自 LiteLLM、匯入時的值、對照基礎模型 key）。
- **價目版本（既有 `PriceList`，append-only）**：沿用既有 `source_note` 標記 LiteLLM 來源與版本；採納＝新增一列。
- **LiteLLM 登錄表（外部，唯讀）**：模型 → {provider、mode、context、能力、公開牌價}；隨套件固定版 + 可線上抓最新；非本系統資料、僅作建議來源。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新增一個登錄表內的模型，管理員**不需手打** context/modality/能力/價格即可建立（全部自動帶入、可改）。
- **SC-002**: 自訂 deployment（查無 slug）可透過對照基礎模型借入中繼資料、價格自訂後建立。
- **SC-003**: 每個同步欄位可看出來源（LiteLLM／借用／手動），手改後轉手動。
- **SC-004**: 「檢查更新」能列出逐欄「舊→新」差異 + 來源；採納為選擇性、不動手動欄；採納價格產生一筆新價目版本帶 LiteLLM 來源。
- **SC-005**: 線上抓失敗時於逾時內回退固定版並明確告知，管理員不卡住。
- **SC-006**: 計費結果與本功能上線前一致（價目仍由自有版本化價目表決定）；目錄/proxy 零回歸。

## Assumptions

- **LiteLLM 已是專案相依**（library form），其內建登錄表（數千模型，含 provider/mode/context/能力/牌價）可直接讀取；key 命名與我們 `provider/model` slug 慣例一致。**不新增套件**。
- **線上抓最新**為管理員明確動作（非背景、非熱路徑）；對外連線需確認部署層 egress 放行，逾時回退固定版。
- **價格邊界**：LiteLLM 給建議價，採納寫進既有 `PriceList`（point-in-time、append-only、`source_note`）；計費引擎不動。
- **來源標記/快照**為新增的中繼資料（最小 schema 增量，傾向 JSON 欄位、避免大改）。
- **覆蓋缺口**：登錄表查無的 slug 由對照基礎模型或純手填補上；不保證全模型皆有 LiteLLM 資料。
- **不批量匯入**全部數千模型——管理員挑要加的；本功能是「帶入 + 對照」，非「鏡像整份登錄表」。
- **平台/技術棧**沿用既有（admin Web UI + 後端服務）。
