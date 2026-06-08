# Feature Specification: responses 支援判斷（實測 + 手動雙來源）

**Feature Branch**: `035-responses-support-detection`
**Created**: 2026-06-08
**Status**: Draft
**Input**: 把「這模型能否走 `/v1/responses`（Codex/Agent）」改成由**實測**或**admin 手動**判定——runtime 預設先試（打得通就支援、不通回真實錯誤）、admin 可手動覆寫；目錄顯示「Agent 相容」徽章 + 來源；與 LiteLLM 模型能力徹底分開（LiteLLM 不碰 responses、移除 mode→responses 衍生）。零 migration、零套件、計費不變。

## 背景與問題

平台對外開放 OpenAI 相容的 `/v1/responses`（Codex 等 agent 工具的事實入口），背後用 litellm `aresponses` 把各家模型**橋接**成 responses。但「某個模型到底能不能走 responses」目前是用一個靜態的 `responses` 能力旗標事前硬擋——這帶來三個問題：

1. **概念混淆**：上一階段一度把 `responses` 從 LiteLLM 的 `mode` 推導、塞進「模型能力」清單。但 responses 是「**我們 gateway 的端點可用性**」（軸③），跟「模型原生 API 型態」（軸①，LiteLLM mode）和「模型能力」（軸②，LiteLLM 旗標 vision/reasoning…）是**三條不同的軸**，不該混。
2. **靜態旗標會過時/被洗掉**：LiteLLM 同步若動到 capabilities，會把 admin 設的 `responses` 洗掉，導致 Codex 突然不能用（已發生的 latent bug）。
3. **誤擋**：模型其實打得通，但因為沒被標記 `responses` 就被事前擋下。

**核心想法**：能不能走 responses，**打一次就知道**——最準的判斷依據是「實際呼叫的結果」。再加上 admin 可手動覆寫，兩種依據都算數。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - runtime 軟化閘門：先試，不靠靜態旗標誤擋（Priority: P1）🎯 MVP

成員/agent 對某模型呼叫 `/v1/responses` 時，平台**直接嘗試**而非因缺少靜態旗標就事前擋；打得通就用，打不通回明確的真實錯誤。

**Why this priority**: 這是核心——讓「實際能不能用」由真實呼叫決定，立即解掉「誤擋」與「旗標過時」兩個痛點。

**Independent Test**: 對一個未被標記但實際支援的模型打 `/v1/responses` → 成功（不再被 `model_not_responses_capable` 事前擋）；對一個不支援的 → 回帶原因的上游錯誤。

**Acceptance Scenarios**:

1. **Given** 一個未被標記但實際可橋接的模型，**When** 呼叫 `/v1/responses`，**Then** 正常完成（不被事前擋）。
2. **Given** 一個實際不支援的模型，**When** 呼叫 `/v1/responses`，**Then** 回傳帶上游原因的錯誤（而非無資訊的事前 400）。
3. **Given** admin 已手動標記某模型「responses 不可用」，**When** 呼叫，**Then** 事前擋下並給清楚訊息（手動是唯一的事前封鎖）。

---

### User Story 2 - admin「測試 responses」實測判定（Priority: P1）

admin 可對某模型按「測試 responses」，平台打一個極小的真實呼叫，結果即答案，並記下來源為「實測」。

**Why this priority**: 讓 admin 主動、確定地知道某模型可不可用於 Codex，並把結果落為目錄顯示依據。

**Independent Test**: admin 對模型按「測試 responses」→ 看到通/不通結果；通過則該模型標記為 responses 可用、來源「實測」。

**Acceptance Scenarios**:

1. **Given** admin 在某模型，**When** 按「測試 responses」，**Then** 平台打一個極小呼叫並顯示通/不通（結果即回應，沿用既有測試連線的模式）。
2. **Given** 測試通過，**When** 完成，**Then** 該模型記為 responses 可用、來源標「實測」。
3. **Given** 測試失敗，**When** 完成，**Then** 顯示失敗原因，模型不被標為可用。

---

### User Story 3 - admin 手動覆寫（Priority: P2）

admin 可直接設某模型 responses「可用 / 不可用」，覆寫實測結果（例如已知降級不可接受時關閉）。

**Why this priority**: 給 admin 最終裁量權；手動覆寫是雙來源的第二支。

**Independent Test**: admin 手動把某模型設「不可用」→ 即使實測會通，runtime 也事前擋、目錄不顯示 Agent 相容。

**Acceptance Scenarios**:

1. **Given** admin 手動設「不可用」，**When** 成員呼叫 `/v1/responses`，**Then** 事前擋下。
2. **Given** admin 手動設「可用」，**When** 檢視來源，**Then** 標「手動」（蓋過任何實測）。

---

### User Story 4 - 目錄顯示「Agent 相容」徽章 + 成員可篩（Priority: P2）

模型目錄顯示「Agent 相容（Responses）」徽章與其來源（實測/手動），成員可據此篩選「可用於 Codex/Agent」的模型。

**Why this priority**: 把判斷結果變成成員看得懂的資訊（原則 6 可達性）。

**Independent Test**: 一個 responses 可用的模型在目錄顯示「Agent 相容」徽章；成員以該條件篩選只看到可用者。

**Acceptance Scenarios**:

1. **Given** 一個 responses 可用的模型，**When** 成員看目錄，**Then** 顯示「Agent 相容（Responses）」徽章 + 來源。
2. **Given** 目錄篩選，**When** 成員選「Agent 相容」，**Then** 只列出 responses 可用的模型。

---

### Edge Cases

- **從未測試也未手動的模型**：runtime 仍可先試（不擋）；目錄不顯示 Agent 相容徽章（未知）。
- **LiteLLM 同步**：MUST 完全不增刪 responses 狀態（採納 merge-preserve）；不再從 mode 推導。
- **實測耗用**：測試是 admin 明確動作、用極小呼叫；不在成員熱路徑反覆自動測。
- **手動 vs 實測衝突**：手動優先（覆寫實測）。
- **不支援模型在 runtime 失敗**：回帶原因的上游錯誤，而非靜默或無資訊 400。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `/v1/responses` runtime MUST **不**因缺少靜態 responses 旗標而事前擋；改為直接嘗試上游呼叫，成功即支援、失敗回帶真實原因的錯誤。
- **FR-002**: 唯一的事前封鎖 MUST 是 admin **手動標記「不可用」**；其餘一律先試。
- **FR-003**: 平台 MUST 提供 admin「測試 responses」動作：打一個極小真實呼叫，結果即答案（沿用既有測試連線的「結果即回應」模式），通過則記模型 responses 可用、來源「實測」。
- **FR-004**: admin MUST 可手動設某模型 responses「可用/不可用」，且手動 MUST 覆寫實測結果（來源標「手動」）。
- **FR-005**: 模型目錄 MUST 顯示「Agent 相容（Responses）」徽章與其來源（實測/手動）；成員 MUST 可據此篩選。
- **FR-006**: LiteLLM 同步 MUST 完全不增刪 responses 狀態；MUST NOT 從 LiteLLM `mode` 推導 responses（移除既有衍生）；採納能力更新 MUST 保留非 LiteLLM 管轄的狀態（merge-preserve）。
- **FR-007**: 計費、proxy 其餘行為、既有目錄/成員端 MUST 零回歸；**無新 migration、無新套件**。

### Key Entities *(include if feature involves data)*

- **模型目錄項（既有 `ModelCatalog`）**：responses 支援狀態（可用/不可用/未知）+ 來源（實測/手動）以既有欄位承載（capabilities 或既有 `litellm_sync` 旁的小結構），**不新增 migration**。
- **三軸（概念）**：① 模型原生 API 型態（LiteLLM `mode`，僅快照/唯讀）② 模型能力（LiteLLM 旗標）③ **gateway 端點可用性（responses）**——本功能只動 ③，且 ③ 與 ①②解耦。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 實際可橋接但未標記的模型，呼叫 `/v1/responses` 不再被誤擋；不支援者回帶原因的錯誤。
- **SC-002**: admin「測試 responses」可實測並記來源「實測」；手動可覆寫並記「手動」。
- **SC-003**: 目錄顯示「Agent 相容」徽章 + 來源，成員可篩選。
- **SC-004**: LiteLLM 同步前後，responses 狀態不被增刪/洗掉（採納 merge-preserve）。
- **SC-005**: 計費結果與上線前一致；proxy/目錄/成員端零回歸；無新 migration、無新套件。

## Assumptions

- **建立在既有 responses 管線**（litellm `aresponses` 橋接、上游錯誤已可 surface 為 `upstream_error`）+ 既有「測試連線」端點模式（1-token ping、結果即回應）之上。
- **「測試」用極小呼叫**（如 1-token），由 admin 明確觸發；不在成員熱路徑自動反覆測。
- **responses 狀態與來源**以既有欄位承載（傾向 capabilities 字串 + `litellm_sync` 旁的來源標記），**不新增 migration**。
- **手動優先**：手動覆寫實測；未測未手動＝未知（runtime 仍先試、目錄不顯示徽章）。
- **三軸分離**：LiteLLM 只管 ①②，responses（③）由實測/手動判定，兩者解耦。
- **平台/技術棧**沿用既有，不新增套件。
