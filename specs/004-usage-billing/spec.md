# Feature Specification: 階段 3a — 用量觀測與費用計算

**Feature Branch**: `004-usage-billing`
**Created**: 2026-05-22
**Status**: Draft
**Input**: User description: "階段 3a 後端：用量觀測 + 費用計算（YAML 價目、月配額、不含團隊、不含 UI）"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 管理員看誰用了多少 (Priority: P1)

擁有者打開後台想知道「上個月誰用得最多」、「某個分配花了多少錢」、「某個
模型的總用量」。系統提供查詢 API，按 Member / Allocation / Model 三種維度
聚合 token 與費用。

**Why this priority**：vision 階段 3 的核心承諾；缺它無法回答「錢花到哪」。

**Independent Test**：對既有 CallRecord 跑查詢，可拿到「Alice 上月 12,500
tokens / USD 0.18」、「分配 X 上月 3,200 tokens / USD 0.04」、「gpt-4o-mini
上月 50,000 tokens / USD 0.75」。

**Acceptance Scenarios**:

1. **Given** 過去 30 天有多筆 CallRecord，**When** `GET /admin/usage?group_by=member&from=...&to=...`，
   **Then** 回傳每個 Member 的 `total_tokens`、`prompt_tokens`、`completion_tokens`、
   `total_cost_usd`、`call_count`。
2. **Given** 同上，**When** `group_by=allocation`，**Then** 同樣聚合鍵改為 allocation_id。
3. **Given** 同上，**When** `group_by=model`，**Then** 聚合鍵改為 model 字串。
4. **Given** 查詢時間區間為空，**When** 呼叫，**Then** 回 400 + 結構化錯誤
   碼 `invalid_time_range`（避免無界查詢）。
5. **Given** 區間 > 90 天，**When** 呼叫，**Then** 回 400 + `range_too_wide`，
   保護 DB 與避免 OOM。

---

### User Story 2 - 管理員看單筆分配的細節時間序列 (Priority: P1)

擁有者點開某個 allocation 想看「過去 30 天每日用量曲線」做容量規劃。

**Why this priority**：聚合數字不夠；趨勢圖才能看出「快爆配額」或「平穩」。

**Independent Test**：對單個 allocation 查詢時間序列，回傳每日 bucket。

**Acceptance Scenarios**:

1. **Given** 分配 A 過去 30 天有呼叫，**When** `GET /admin/allocations/{id}/usage-timeseries?bucket=day&from=...&to=...`，
   **Then** 回傳每日的 `tokens`、`cost_usd`、`call_count` 陣列。
2. **Given** 同上指定 `bucket=hour`，**When** 區間 ≤ 7 天，**Then** 回傳每
   小時 bucket。區間 > 7 天且 `bucket=hour` 回 400。

---

### User Story 3 - 管理員設配額限制濫用 (Priority: P1)

擁有者要能說「分配 X 每月最多 100,000 tokens」；超過自動拒絕呼叫。

**Why this priority**：成本上限是合規與預算保護的最低底線。

**Independent Test**：設 quota=100，用 50 → 通過；用 51 → 通過（總用量 101 略
超）；下一次呼叫 → 403 `quota_exceeded`。

**Acceptance Scenarios**:

1. **Given** allocation 設 `quota_tokens_per_month=100`，**When** PATCH 該分配，
   **Then** 200 + 新 quota 生效。
2. **Given** 本月用量 < quota，**When** 呼叫 `/v1/chat/completions`，**Then**
   成功；CallRecord 寫入後計算「累計總量」更新。
3. **Given** 本月用量已 ≥ quota，**When** 再呼叫，**Then** 回 403 +
   `error.code=quota_exceeded` + `error.message` 含當月用量與上限。
4. **Given** 配額為 null（unlimited），**When** 任意用量，**Then** 不擋。
5. **Given** UTC 月初到來，**When** 查當月用量，**Then** 重新從 0 計算（舊月份
   資料保留供查詢但不算入本月配額）。

---

### User Story 4 - 服務型分配可繞過 quota 但被特別標記 (Priority: P2)

行政輔助服務用的高額度分配（vision 「服務型分配」）需要 quota=unlimited，
但要在查詢時可一眼看出「這些是服務、不是個人」。

**Why this priority**：呼應 vision「不會寫程式的人透過服務間接享受 AI」；
首階段以一個 boolean 標記即可。

**Independent Test**：admin 把分配標為 `is_service_allocation=true`；列表 +
用量查詢結果都帶此標記；可單獨過濾。

**Acceptance Scenarios**:

1. **Given** 分配 X，**When** PATCH 設 `is_service_allocation=true`，**Then**
   回應包含此欄位 true；後續 GET 也包含。
2. **Given** usage 查詢，**When** `group_by=allocation`，**Then** 每筆結果
   包含 `is_service_allocation` 標記。
3. **Given** usage 查詢，**When** 加 `?service_only=true`，**Then** 只列出
   服務型分配。

---

### User Story 5 - 管理員管理價目（YAML 載入） (Priority: P1)

價目來自 YAML 檔（人工同步官方文件）。管理員透過 CLI 載入：新版價目寫入
DB，**不**回溯改寫歷史紀錄（point-in-time billing）。

**Why this priority**：費用算對 + 不被回溯改寫是會計可信度的底線。

**Independent Test**：載入 `prices_v1.yaml`，跑 100 次呼叫紀錄費用 X；載入
`prices_v2.yaml`（價格漲 2x），新呼叫費用為 2X，舊紀錄費用維持 X。

**Acceptance Scenarios**:

1. **Given** prices.yaml 含 `azure / gpt-4o-mini / input=0.00015 / output=0.0006`，
   **When** 跑 `python -m ai_api.cli.load_prices prices.yaml`，**Then** PriceList
   表新增記錄並回報「loaded 1 entry」。
2. **Given** 同模型隔日新版 yaml 把 input 改為 0.0003，**When** 再次載入，
   **Then** PriceList 表新增第二筆，`effective_from` 不同；既有 CallRecord
   的 `cost_usd` 不變。
3. **Given** 新呼叫進入，**When** 計算費用，**Then** 用「呼叫時間 ≥ effective_from」
   的最新一筆價目（找不到價目即 cost_usd=NULL，不擋呼叫）。

---

### User Story 6 - 管理員匯出 CSV / JSON (Priority: P2)

把用量資料匯出做月報或進 Excel 分析。

**Why this priority**：對小組織夠用，省去自己接 BI 工具。

**Independent Test**：`GET /admin/usage.csv?from=...&to=...&group_by=member`
回 CSV，content-type 正確、欄位齊全。

**Acceptance Scenarios**:

1. **Given** 過去 30 天資料，**When** `GET /admin/usage.csv?from=...&to=...&group_by=member`，
   **Then** 回 200、`Content-Type: text/csv`、有 CSV header、每列一個 Member。
2. **Given** 同上 `?format=json` 或 `Accept: application/json`，**Then** 回 JSON array。
3. **Given** 區間 > 90 天，**When** 匯出，**Then** 回 400（與 SC-002 同保護）。

---

### User Story 7 - 階段 3b SPA 能跨域呼叫（CORS 預備） (Priority: P2)

UI 留階段 3b，但本階段先把後端準備好 — admin endpoints 必須能被同網域或
設定中的 origin 呼叫，cookie session 跨域時帶 credentials。

**Why this priority**：避免 3b 開工後才發現後端要大改。

**Independent Test**：OPTIONS preflight 對 `GET /admin/usage` 從設定的 origin
打，回 200 + CORS headers。

**Acceptance Scenarios**:

1. **Given** `Settings.cors_origins=["http://localhost:5173"]`，**When**
   OPTIONS preflight 指定該 origin，**Then** 回 200 + `Access-Control-Allow-Origin`。
2. **Given** 未在 allowlist 的 origin，**When** preflight，**Then** 拒絕（無
   ACAO header）。
3. **Given** allowlist 內 origin，**When** GET 帶 cookie + `Origin` header，
   **Then** 回應含 `Access-Control-Allow-Credentials: true`。

### Edge Cases

- **時鐘跳越月份**：查詢「本月用量」時若跨日凌晨呼叫，需以 UTC 月初為錨點，
  不可用 local time。
- **價目找不到**：若 model 從未被載入價目，cost_usd 寫 NULL；usage 聚合時
  該筆視為 cost=0（同時在回應加 `pricing_missing: true` flag 提醒）。
- **舊 CallRecord 沒有 cost_usd**（Phase 2.5 之前的資料）：聚合時視為 0；不
  回溯計算。
- **配額剛好相等**：「累計 token ≥ quota」即拒（含當下這筆若會超過）。
- **CSV 內含「,」或換行**：標準 quoting 處理。
- **YAML 載入同 `(provider, model, effective_from)`**：違反 UNIQUE 即回錯，
  不覆寫（防誤操作）。

## Requirements *(mandatory)*

### Functional Requirements

#### 用量查詢
- **FR-001**: 系統 MUST 提供 `GET /admin/usage` 端點，必要參數 `from`、`to`
  (ISO 8601 UTC)、`group_by` (`member|allocation|model`)。
- **FR-002**: 區間 > 90 天 MUST 回 400 + `range_too_wide`。
- **FR-003**: 回應 MUST 含每組的 `total_tokens`、`prompt_tokens`、`completion_tokens`、
  `total_cost_usd`、`call_count`，以及 group key 的人類可讀名稱。
- **FR-004**: 系統 MUST 提供 `GET /admin/allocations/{id}/usage-timeseries` 端點，
  參數 `bucket=hour|day`、`from`、`to`。`bucket=hour` 時區間限制 ≤ 7 天。

#### 配額
- **FR-005**: Allocation 表 MUST 加欄位 `quota_tokens_per_month` (int | NULL)
  與 `is_service_allocation` (bool default false)。
- **FR-006**: 管理員端點 `PATCH /admin/allocations/{id}` MUST 可更新這兩個欄位。
- **FR-007**: Proxy `/v1/chat/completions` MUST 在呼叫上游**之前**檢查當月
  累計 token：若 quota 非 NULL 且 `current_month_tokens >= quota` 即回 403 +
  `quota_exceeded`，不上送 LiteLLM。
- **FR-008**: 月度週期錨點 MUST 為 UTC 月初 00:00:00；查詢「本月」即從該
  時間起到當下。

#### 費用 / 價目
- **FR-009**: 新增 `PriceList` 表，欄位：`id`、`provider`、`model`、
  `input_per_1k_tokens_usd`、`output_per_1k_tokens_usd`、`effective_from`、
  `created_at`、`created_by`、`source_note`。UNIQUE on
  (`provider`, `model`, `effective_from`)。
- **FR-010**: CallRecord 表 MUST 加欄位 `cost_usd` (numeric | NULL)。
- **FR-011**: Proxy 在寫入 CallRecord 時 MUST 依「呼叫時間 ≥ effective_from
  的最新一筆 PriceList」計算 cost：
  `(prompt_tokens / 1000 * input_rate) + (completion_tokens / 1000 * output_rate)`。
  找不到對應價目即 cost_usd=NULL。
- **FR-012**: CLI `python -m ai_api.cli.load_prices <yaml-path>` MUST 載入
  YAML 並新增 PriceList 記錄；既有記錄不更動（point-in-time 不可回溯）。
- **FR-013**: 系統 MUST 不提供「修改既有 PriceList」端點；只能新增。修改
  價目 = 載入新的 YAML 並設新的 `effective_from`。

#### 匯出
- **FR-014**: 系統 MUST 提供 `GET /admin/usage.csv` 與 `GET /admin/usage.json`，
  參數同 `/admin/usage`；CSV 必須含 header 與標準 quoting。

#### 階段 3b 準備
- **FR-015**: 系統 MUST 支援透過 `Settings.cors_origins` 設定允許的 CORS
  origins（list[str]），預設為空（不允許跨域）。
- **FR-016**: 當啟用 CORS 且請求帶 cookie，CORS preflight 回應 MUST 含
  `Access-Control-Allow-Credentials: true`；session cookie 屬性在啟用 CORS
  時 MUST 為 `SameSite=None`、`Secure=true`（dev 環境 HTTP 不支援 SameSite=None
  + Secure — 文件記入 limitation）。

#### 不在本階段範圍
- **FR-017** (NON-GOAL): 無 Web UI（階段 3b）。
- **FR-018** (NON-GOAL): 無 Team 概念。
- **FR-019** (NON-GOAL): 無自動爬 Azure 價目（YAML 人工）。
- **FR-020** (NON-GOAL): 無多幣別；首發 USD。
- **FR-021** (NON-GOAL): 無即時警報（已在 2.5 anomaly_detector 涵蓋）。

### Key Entities

- **PriceList**（新表）：
  - `id` (ULID)、`provider`、`model`、`input_per_1k_tokens_usd` (numeric)、
    `output_per_1k_tokens_usd` (numeric)、`effective_from` (timestamptz)、
    `created_at`、`created_by`、`source_note`（例 "Azure Retail price snapshot 2026-05"）。
  - UNIQUE on (`provider`, `model`, `effective_from`)。

- **Allocation**（擴充）：
  - 加 `quota_tokens_per_month` (int | NULL；NULL = unlimited)
  - 加 `is_service_allocation` (bool, default false)

- **CallRecord**（擴充）：
  - 加 `cost_usd` (numeric(10, 6) | NULL)，於寫入時即計算（point-in-time）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 對含 10,000 筆 CallRecord 的 DB 查詢「上個月用量 by Member」
  ≤ 2 秒。
- **SC-002**: 配額測試：設 quota=100、用 99→通過、用 100→通過、第 101 個
  token 觸發拒絕回 403。
- **SC-003**: Point-in-time 計費正確：載入新版價目（2x）後，舊 CallRecord 的
  cost_usd 不變；新 CallRecord 用新價。
- **SC-004**: CSV 匯出 30 天資料（≤ 10,000 列）≤ 3 秒。
- **SC-005**: CORS preflight 對 allowlist 內 origin 200；非 allowlist 不回
  Access-Control-Allow-Origin。
- **SC-006**: 所有新 admin 端點走既有 admin token 認證；無認證 401。
- **SC-007**: Phase 1+2+2.5 既有 97 tests 全綠（不能引入回歸）。
- **SC-008**: 所有 FR 在 git 歷史中可見「測試 commit 早於對應實作 commit」
  （延續 TDD 紀律）。

## Assumptions

- **價目來源為 YAML 檔（人工同步）**，存於 repo 或外部位置；CLI 載入即可。
  Azure Retail Prices API 整合留後階段。
- **單一幣別 USD**；不做匯率轉換。
- **配額週期固定為「日曆月」**，錨點 UTC 月初。
- **服務型分配以單一 boolean 標記**；未來若需要區分多種服務角色，再升級為
  enum 或 tag。
- **CSV 匯出走同步 response**，最大 90 天保護避免 OOM；超大資料集走 BI 工具
  （未來考慮）。
- **CORS 設定為環境變數**：`CORS_ORIGINS='["http://localhost:5173","https://admin.example.com"]'`。
- **舊 CallRecord (no cost_usd)** 在聚合時 cost 視為 0；vision 已記載「Phase 2.5
  之前的紀錄不回溯計費」。
