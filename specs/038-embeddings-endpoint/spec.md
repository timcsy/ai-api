# Feature Specification: 對成員開放 `/v1/embeddings` 端點

**Feature Branch**: `038-embeddings-endpoint`
**Created**: 2026-06-09
**Status**: Draft
**Input**: 對成員開放 OpenAI 相容的 `/v1/embeddings`，讓 embedding 模型真的能用——複用既有前置 pipeline（憑證/分配/狀態/配額/存取政策/計費記錄）與既有 token 計費；不動計費層、無新表、無 migration、無新套件。階段 29「多端點開放」的增量 ①。

## 背景與問題

平台對成員只開 `/v1/chat/completions` + `/v1/responses`。但模型目錄能收 embedding 模型（litellm 認得、`supported_endpoints` 標 `/v1/embeddings`），成員卻**呼叫不到**——這正是階段 29 點出的「**目錄能放、但 gateway 服務不了**」不一致。embedding（把文字轉向量，用於檢索/RAG/相似度）是最常見、且計費單位仍是 **token**（input）的非 chat 端點，所以是「多端點開放」最該先做、且最不動核心的一步。

**核心想法**：把「拿到分配的 embedding 模型」變成「真的能呼叫」——加一條 `/v1/embeddings`，沿用同一條前置 pipeline 與 token 計費，計量歸戶到分配。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 成員以分配金鑰呼叫 embedding（Priority: P1）🎯 MVP

成員用分配到的應用金鑰對 `/v1/embeddings` 送出文字，取得向量；該次呼叫被計量、計費、歸戶到對應分配。

**Why this priority**: 這是本功能的全部價值——讓 embedding 模型從「名義可見」變「實質可用」，並維持平台的計量/歸戶承諾。

**Independent Test**: 用有效金鑰 + 已授權的 embedding 模型打 `/v1/embeddings` → 回向量；查用量看到一筆 input-token 計費歸戶到該分配。

**Acceptance Scenarios**:

1. **Given** 成員有一個 embedding 模型的有效分配與金鑰，**When** 對 `/v1/embeddings` 送 `{model, input}`，**Then** 回傳 OpenAI 相容的向量結果。
2. **Given** 上述呼叫完成，**When** 查用量，**Then** 有一筆 `CallRecord`：input token 數 + 依該模型現價計算的成本 + 歸戶到該分配。
3. **Given** 金鑰範圍**不含**所請求的 embedding 模型（或模型未授權），**When** 呼叫，**Then** 比照既有 proxy 行為擋下（`model_mismatch` / `model_forbidden`），不外洩供應商金鑰。
4. **Given** 無效/已撤回金鑰，**When** 呼叫，**Then** 回 401（沿用既有憑證驗證）。

---

### User Story 2 - 上游錯誤可診斷、不無聲（Priority: P2）

embedding 上游失敗時，平台回帶上游原因的錯誤，並於記錄/日誌可見，admin 能診斷。

**Why this priority**: 沿用平台「透明 relay + 本地可觀測」承諾（原則 2/可觀測性）；新端點上線常見的就是錯誤路徑沒接好。

**Independent Test**: 讓上游回錯（如部署名錯）→ 成員看到帶原因的錯誤；admin 在記錄/日誌看得到該次失敗與上下文。

**Acceptance Scenarios**:

1. **Given** 上游對該 embedding 呼叫回錯，**When** 成員呼叫，**Then** 回傳帶上游原因的錯誤（非無資訊通用錯誤），且記一筆可辨識的失敗（沿用既有 `upstream_error` 慣例）。

---

### User Story 3 - embedding 模型詳情顯示如何呼叫（Priority: P2）

embedding 模型的目錄詳情顯示 `/v1/embeddings` 的用法，成員照做即可用（不必猜端點）。

**Why this priority**: 原則 6 可達性——開了端點還要讓成員知道怎麼用；否則仍是隱性不可達。

**Independent Test**: 看一個 embedding 模型詳情 → 有 `/v1/embeddings` 的呼叫範例（端點 + 範例請求）。

**Acceptance Scenarios**:

1. **Given** 一個 embedding 模型詳情，**When** 成員檢視「如何呼叫」，**Then** 顯示 `/v1/embeddings` 的端點與範例（而非只給 chat 範例）。

---

### Edge Cases

- **回應缺 usage**：少數 provider 的 embedding 回應沒帶 token 用量 → 成本記為「未定價/未知」（沿用既有 `has_unpriced` 模式），不讓計費炸掉。
- **大量 input（批次 embedding）**：受既有 request body 上限保護（顯示值＝執法值）；超過回 413（邊緣既有行為）。
- **非 embedding 模型打到此端點**：以該模型實際可否走 embedding 為準——上游會回錯（帶原因），不偽裝成功。
- **存取政策/憑證來源**：與 chat 同一條——需 catalog row + 該 provider 有可用憑證（env fallback 不算存取政策）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 平台 MUST 提供 OpenAI 相容的 `/v1/embeddings`（成員端），接受 `{model, input}` 並回傳向量結果。
- **FR-002**: 此端點 MUST 沿用與 `/chat/completions` **同一條前置 pipeline**：金鑰驗證、分配解析（含 scope/狀態/配額/model binding）、存取政策、provider 憑證解析；不另立一套授權邏輯。
- **FR-003**: 每次成功呼叫 MUST 記一筆用量：input token 數、依該模型**現價**（既有 point-in-time 價目）計算的成本、歸戶到對應分配；MUST NOT 產生無歸屬影子用量。
- **FR-004**: 計費 MUST 沿用既有 **token 計費**（input token × 現價）；本功能 MUST NOT 引入非 token 計費單位、MUST NOT 改動既有計費資料結構（**無 migration**）。
- **FR-005**: 上游錯誤 MUST 回帶原因的錯誤並記為可辨識的失敗（沿用既有 `upstream_error` 慣例）；底層供應商金鑰 MUST NOT 出現在回應/日誌/錯誤。
- **FR-006**: 金鑰範圍不含或未授權的模型 MUST 比照既有 proxy 擋下（`model_mismatch` / `model_forbidden`）；無效/撤回金鑰 MUST 回 401。
- **FR-007**: embedding 模型的目錄詳情 MUST 顯示 `/v1/embeddings` 的呼叫方式（端點 + 範例）。
- **FR-008**: 既有 `/chat/completions`、`/v1/responses`、計費、配額、稽核行為 MUST 零回歸；**無新表、無 migration、無新套件**。

### Key Entities *(include if feature involves data)*

- **呼叫記錄（既有 `CallRecord`）**：embedding 呼叫沿用之——記 input token、成本、分配歸戶、成功/upstream_error 結果；不新增表。
- **分配 / 應用金鑰（既有）**：embedding 呼叫的授權與計量單位仍是「分配」；金鑰 scope 決定可用哪些 embedding 模型。
- **模型目錄項（既有 `ModelCatalog`）**：embedding 模型（kind=embedding）為此端點的目標；本功能只讀。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員用分配金鑰可成功對已授權的 embedding 模型取得向量；未授權/壞金鑰被正確擋下（model_forbidden / model_mismatch / 401）。
- **SC-002**: 每次 embedding 呼叫**100%** 產生一筆歸戶到分配的計量記錄（input token + 成本）；**零**無歸屬影子用量。
- **SC-003**: 上游失敗時成員看到帶原因的錯誤、admin 在記錄/日誌看得到；**零**無資訊通用錯誤。
- **SC-004**: embedding 模型詳情顯示 `/v1/embeddings` 用法，成員不需猜端點即可呼叫。
- **SC-005**: 計費結果正確（input_per_1k × prompt_tokens）；既有 chat/responses/計費/配額零回歸；**無新 migration、無新套件**。

## Assumptions

- **建立在既有前置 pipeline（`run_preflight`，端點無關）+ token 計費（point-in-time 價目）+ Phase 26 已備的 embedding 上游橋接之上**；本功能只新增一條路由 + 用量記錄，不重寫核心。
- **embedding 計費單位＝input token**（與 chat 同；故沿用既有價目與計費，不需階段 29 的「計費一般化」——那留給非 token 端點）。
- **embedding 回應的用量 shape**（`usage.prompt_tokens` 等）以實測為準（採用前先驗證），缺 usage 時成本記未定價。
- **存取/可見性與 chat 一致**：embedding 模型需在目錄、且 provider 有可用憑證；env fallback 不算存取政策。
- **範圍邊界**：只做 embedding（非 token 端點 OCR/圖片/語音、batch、串流不在此版）；「目錄誠實：非 chat mode 不假裝 chat」為階段 29 約束、與本功能正交，不在此版（可後續）。
- **平台/技術棧沿用既有，不新增套件、不新增表、不新增 migration。**
