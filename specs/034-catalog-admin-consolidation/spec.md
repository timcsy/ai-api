# Feature Specification: 模型目錄 admin 體驗整合 + 充分利用 LiteLLM

**Feature Branch**: `034-catalog-admin-consolidation`
**Created**: 2026-06-08
**Status**: Draft
**Input**: 三畫面（加入 Model / 編輯基本資訊 / 編輯價格）收斂到模型詳情頁單一中樞；每欄顯示來源徽章；「檢查 LiteLLM 更新」前移到詳情頁；退役價格「常見範本」改用 LiteLLM 建議價；充分利用 LiteLLM（能力旗標 2→~10、補 max_output_tokens、完整 entry 存 snapshot、詳情頁唯讀「LiteLLM 原始資訊」面板）。不升 mode 為可篩選一等公民、零 migration、不改計費引擎。

## 背景與問題

階段 23 把 LiteLLM 接進了模型目錄，但管理員的編輯體驗散在**三個世代疊出來的畫面**，彼此重疊又不一致：

- **加入 Model**（階段 23）：有 LiteLLM 帶入。
- **編輯基本資訊**（階段 4/5）：純手打逗號分隔欄，完全沒接 LiteLLM，也沒顯示我們已經存的「欄位來源」。
- **編輯價格**（階段 7）：自帶一套「從常見範本帶入」的硬編價格範本，與 LiteLLM 建議價打架。

而且「檢查更新」埋在列表列、不在管理員實際在編輯的詳情頁。同一件事（這個模型的中繼資料與價格從哪來、怎麼更新）有多條重疊路徑，違反「集中管理」。

另一面，LiteLLM 本身就是為了**幫人整理好這些模型資訊**而存在——實測每個模型有 ~150 個欄位、十幾種模型型態、三十幾個能力旗標——但目前只用到極少數。把資訊吃乾抹淨地帶入，管理員幾乎可以零手打，且這些資訊也能餵養成員端模型目錄的篩選。

**計費紅線不變**：價目表仍是計費唯一真理，LiteLLM 只給建議。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 詳情頁單一中樞 + 來源徽章（Priority: P1）🎯 MVP

管理員在模型詳情頁一處，就能看到每個欄位的**來源**（LiteLLM / 借用 / 手動），不必猜哪些值是自動帶的、哪些是自己改的。

**Why this priority**: 把「這個值從哪來」攤在眼前，是整個整合的基礎；其餘建立在這個可視性上。

**Independent Test**: 開一個由 LiteLLM 帶入建立的模型詳情頁 → 每個可同步欄位旁有來源徽章；手改過的欄顯示「手動」。

**Acceptance Scenarios**:

1. **Given** 一個經 LiteLLM 帶入的模型，**When** 檢視詳情頁，**Then** 每個可同步欄位顯示來源徽章（LiteLLM / 借用 / 手動）。
2. **Given** 管理員手改某欄後，**When** 重看詳情頁，**Then** 該欄徽章為「手動」。
3. **Given** 純手動建立（無 LiteLLM）的模型，**When** 檢視詳情頁，**Then** 不顯示誤導徽章（標示為手動或無來源）。

---

### User Story 2 - 檢查更新前移到詳情頁（Priority: P1）

「檢查 LiteLLM 更新」從列表列移到管理員實際編輯的詳情頁顯眼處；它本就同時呈現中繼資料與價格的差異，管理員一處檢視、選擇性採納。

**Why this priority**: 維護動作要在「編輯的地方」，不該埋在別處；與 US1 的可視性同屬集中管理。

**Independent Test**: 詳情頁有「檢查 LiteLLM 更新」入口 → 點開列出中繼資料 + 價格的逐欄差異 → 勾選採納生效。

**Acceptance Scenarios**:

1. **Given** 模型詳情頁，**When** 檢視，**Then** 有「檢查 LiteLLM 更新」入口（不需回列表）。
2. **Given** 點「檢查更新」，**When** 有差異，**Then** 一處同時列出中繼資料與價格的「舊→新 + 來源」，管理員勾選採納；手動欄不被採納。

---

### User Story 3 - 退役價格「常見範本」改用 LiteLLM 建議（Priority: P1）

價格新增/編輯的「從常見範本帶入」改為 LiteLLM 建議價（與其他帶入同源），不再維護一份各走各的硬編範本。

**Why this priority**: 兩套帶入並存正是混亂源；統一到 LiteLLM 一個來源。

**Independent Test**: 價格新增畫面的「常見範本」入口已換成 LiteLLM 建議；選用後填入建議價、仍可手改。

**Acceptance Scenarios**:

1. **Given** 價格新增/編輯畫面，**When** 檢視帶入入口，**Then** 是 LiteLLM 建議價（非舊硬編範本清單）。
2. **Given** 帶入 LiteLLM 建議價後，**When** 管理員手改數字並儲存，**Then** 以手改值新增一筆價目版本（append-only 不變）。

---

### User Story 4 - 充分利用 LiteLLM 資訊（Priority: P2）

帶入時把 LiteLLM 的決策相關資訊吃進來（能力旗標擴充、max_output_tokens），其餘完整資訊以唯讀面板呈現，管理員幾乎零手打。

**Why this priority**: 提升帶入的完整度與價值；建立在 US1–US3 的整合之上。

**Independent Test**: 帶入一個 LiteLLM 模型 → 能力旗標涵蓋約 10 個（非僅 2 個）、有 max_output_tokens；詳情頁有唯讀「LiteLLM 原始資訊」面板顯示完整欄位。

**Acceptance Scenarios**:

1. **Given** 帶入一個 LiteLLM 模型，**When** 檢視能力，**Then** 涵蓋約 10 個決策相關旗標（如 reasoning / pdf / prompt_caching / web_search / audio / video / structured_output…），而非僅 chat/vision/function_calling。
2. **Given** 帶入的模型，**When** 檢視詳情頁，**Then** 有唯讀「LiteLLM 原始資訊」面板，顯示其完整登錄表欄位（含未映射的），不污染主欄位。
3. **Given** 成員端模型目錄，**When** 以能力/型態篩選，**Then** 反映擴充後的資訊（零回歸於既有篩選）。

---

### Edge Cases

- **純手動模型（無 litellm 對應）**：來源徽章標手動、無 LiteLLM 面板、檢查更新顯示「無對照」。
- **舊範本使用者習慣**：LiteLLM 建議價覆蓋面更廣（數千模型）且仍可手填；範本本就硬編少數。
- **LiteLLM 無此模型的能力資訊**：帶入缺的旗標就不帶（不臆造）；唯讀面板顯示「無」。
- **能力旗標擴充影響既有顯示/篩選**：既有 capabilities 的所有讀取點需一併涵蓋，避免破圖或篩選失準。
- **mode 為非 chat（embedding/image/audio/rerank…）**：帶入時 modality 正確反映；不另開可篩選 mode 欄。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 模型詳情頁 MUST 在每個可同步欄位顯示**來源**（LiteLLM / 借用 / 手動）。
- **FR-002**: 詳情頁 MUST 提供「檢查 LiteLLM 更新」入口（不需回列表），且一處同時呈現中繼資料與價格的逐欄「舊→新 + 來源」差異、選擇性採納；**手動欄 MUST NOT 被採納覆寫**。
- **FR-003**: 價格新增/編輯的「常見範本」入口 MUST 改為 LiteLLM 建議價（同一來源）；帶入後仍可手改，採納/儲存 MUST 維持 append-only 價目版本。
- **FR-004**: 帶入 MUST 把 LiteLLM 的決策相關能力資訊映射進既有欄位——能力旗標擴充至約 10 個常用旗標、補 `max_output_tokens`。
- **FR-005**: 系統 MUST 保存 LiteLLM 模型的**完整登錄表 entry**（含未映射欄位）於既有來源快照，並在詳情頁以**唯讀面板**呈現。
- **FR-006**: 帶入/採納 MUST NOT 改變計費邏輯；價目表仍為計費唯一真理，LiteLLM 僅作建議。
- **FR-007**: 既有模型目錄（admin + 成員端）、價目、計費、proxy MUST 零回歸；純手動模型行為不變。
- **FR-008**: 本功能 MUST NOT 新增 migration、MUST NOT 新增套件、MUST NOT 把 `mode` 升為可篩選的第一公民欄位。

### Key Entities *(include if feature involves data)*

- **模型目錄項（既有 `ModelCatalog` + 階段 23 `litellm_sync`）**：沿用既有來源標記與快照；本階段把快照擴存為**完整 LiteLLM entry**、把更多能力映射進既有 `capabilities` 與 `max_output_tokens`（若無對應欄則納入既有中繼）。**無新欄。**
- **價目版本（既有 `PriceList`）**：不變；帶入/採納價走既有 append-only + `source_note`。
- **LiteLLM 登錄表（外部唯讀）**：~150 欄/模型、十幾種型態、三十幾能力旗標；本階段挑決策相關子集映射、其餘唯讀呈現。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 模型詳情頁一處可見：每欄來源徽章 + 檢查更新入口 + 唯讀 LiteLLM 原始資訊面板（三畫面收斂）。
- **SC-002**: 「檢查更新」在詳情頁即可完成，逐欄（中繼資料 + 價格）old→new + 來源、選擇性採納、手動欄不被覆寫。
- **SC-003**: 價格帶入入口已從硬編範本換成 LiteLLM 建議價。
- **SC-004**: 帶入的能力旗標涵蓋約 10 個決策相關項 + max_output_tokens；唯讀面板含完整 entry。
- **SC-005**: 計費結果與本功能上線前一致；目錄/proxy/成員端篩選零回歸。
- **SC-006**: 無新 migration、無新套件、未新增可篩選 mode 欄。

## Assumptions

- **建立在階段 23** 的 LiteLLM adapter（lookup/suggest/search/check/apply）+ `litellm_sync`（來源標記 + 快照）+ check/apply diff 元件之上；本階段是整合與擴充，非從零。
- **價格「常見範本」為前端硬編清單**——退役屬前端改動、無後端端點要拆。
- **能力旗標子集**取決策相關的約 10 個（reasoning / pdf / prompt_caching / web_search / audio / video / structured_output / computer_use / vision / function_calling），非鏡像全部三十幾個。
- **完整 entry 存快照**體積為 JSON 欄、單模型 KB 級，可接受；唯讀面板按需展開。
- **不升 mode 為可篩選欄**（零 migration）；日後真要篩選再評估。
- **平台/技術棧**沿用既有（admin Web UI + 後端服務），不新增套件。
