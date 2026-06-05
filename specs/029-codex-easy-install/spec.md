# Feature Specification: 成員一鍵安裝 Codex + device-flow 免貼 token（零參數、不脫鉤）

**Feature Branch**: `029-codex-easy-install`
**Created**: 2026-06-04
**Status**: Draft
**Input**: User description: "全做" — 階段 19 一次到位：(1) 從 dashboard 複製**一行指令**裝好 Codex 並指向本平台、日常純 `codex` 零參數零環境變數、切 model 不脫鉤；(2) 以 **device-flow（RFC 8628 瀏覽器授權）**免去複製貼上長 token——成員在瀏覽器一鍵授權，安裝腳本自動拿到一把**新 mint 的 per-device 憑證**灌進 Codex；(3) 支援 **Windows + macOS + Linux**。

## 背景與問題

平台是 OpenAI 相容 gateway，成員可用 OpenAI Codex CLI 連上來。階段 18 已讓「一筆分配可掛多把獨立 per-device 憑證、每台一把、撤一把不連坐、可就地 rotate」。但要實際把 Codex 裝起來、連上平台，對非技術成員仍有四個真實痛點：

1. **步驟多**：要裝 Node、`npm i -g @openai/codex`、建資料夾、搬 config、設 token 才能跑。
2. **手動設環境變數最雷**：編輯 shell profile / `setx`，session 觀念非技術者不懂、易出錯。
3. **切 model 會脫鉤**（使用者經驗）：Codex 內切 model 時會重寫 `config.toml`，把自訂 gateway provider 綁定弄丟 → 之後打到 `api.openai.com` → 401。
4. **複製貼上長 token 易錯、不安全**：token 很長、容易貼漏；且貼上後散落在終端機歷史。

目標：成員**一次性**用最少步驟裝好（理想是「複製一行 + 在瀏覽器按一個授權鍵」），之後**日常只打 `codex`（零參數）**，**切 model 不會壞**，而且**全程不需複製貼上 token、不需設環境變數**。對應原則 6 可達性（成員自助、不依賴工程師）與原則 1 憑證隔離（每台一把 per-device 憑證、可單獨撤回）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 一行指令裝好、瀏覽器一鍵授權（Priority: P1）🎯 MVP

成員從自己的 dashboard 複製一行安裝指令，貼進終端機按 Enter。腳本下載並設定好 Codex 指向本平台後，會打開（或顯示）一個授權連結與一組短代碼；成員在已登入的瀏覽器點「授權這台裝置」、選擇要用哪個分配（model），按確認。腳本隨即**自動取得一把新 mint 的 per-device 憑證**並寫入 Codex，結尾跑一次測試呼叫顯示「✓ 連線成功」。**全程成員未複製貼上任何 token、未手動建資料夾或搬檔案、未設環境變數。**

**Why this priority**: 把「裝 + 設定 + 拿憑證」整段降成「複製一行 + 瀏覽器按一下」，是整個階段的核心價值與其餘體驗的前提。

**Independent Test**: 在乾淨機器上，從 dashboard 複製該 OS 的一行指令執行 → 終端機出現授權連結/代碼 → 在瀏覽器授權並選分配 → 腳本顯示連線成功 → 之後打 `codex` 可正常對話；全程未貼 token、未設環境變數。

**Acceptance Scenarios**:

1. **Given** 成員在 dashboard 取得自己 OS 的安裝指令，**When** 在終端機貼上執行並於瀏覽器完成授權，**Then** Codex 被安裝、設定指向本平台、憑證就緒，並印出測試呼叫成功訊息。
2. **Given** 安裝過程需要憑證，**When** 成員在瀏覽器授權，**Then** 平台**新 mint 一把 per-device 憑證**交給腳本（明文僅這一次、只進 Codex 設定檔），成員**不需複製貼上 token**。
3. **Given** 安裝失敗（無網路、權限不足、授權逾時等），**When** 發生，**Then** 顯示清楚、白話的失敗原因與下一步。

---

### User Story 2 - 日常只打 `codex`、零參數零環境變數（Priority: P1）

裝好之後，成員日常使用就是在終端機打 `codex`（不加任何旗標、不加任何參數、不需先設環境變數），即可正常使用。

**Why this priority**: 使用者明確要求的核心體驗；沒有它，安裝再簡單也不算「好用」。

**Independent Test**: 安裝完成後**重開一個全新的終端機視窗**，直接打 `codex` 無任何參數 → 能正常連到本平台對話。

**Acceptance Scenarios**:

1. **Given** 已完成安裝，**When** 開新終端機只打 `codex`，**Then** 正常連線（不需任何旗標、參數或預先 export 環境變數）。
2. **Given** 日常使用，**When** 成員從不需記得或輸入 base URL / token / provider 名稱，**Then** 一切由安裝時寫好的設定承擔。

---

### User Story 3 - 切換 model 後仍正常（不脫鉤）（Priority: P1）

成員在 Codex 內切換 model（例如 `/model`）後，仍能正常呼叫本平台，不會因設定被重寫而打到 OpenAI 官方端點而失敗。

**Why this priority**: 使用者實際踩到的 bug；不解掉，「裝好了卻一切 model 就壞」會直接勸退。

**Independent Test**: 裝好後在 Codex 內切 model，再發一次請求 → 仍走本平台、成功（或在平台未開該 model 時回清楚的「此 model 未開放」而非 401）。

**Acceptance Scenarios**:

1. **Given** 已安裝且運作正常，**When** 在 Codex 內切 model（觸發 Codex 重寫 config.toml），**Then** 後續請求**仍指向本平台**、不會打到 `api.openai.com`。
2. **Given** 成員切到平台未開放的 model，**When** 呼叫，**Then** 得到清楚的「此 model 未開放」訊息，而非令人困惑的 401。
3. **Given** 此防護機制，**When** 檢視，**Then** **不依賴**把 config.toml 設唯讀、**不依賴** wrapper/別名或啟動旗標。

---

### User Story 4 - 授權後憑證可見、可單獨撤回（Priority: P2）

device-flow 授權後 mint 的那把憑證，會出現在成員既有的「裝置與憑證」清單（階段 18），有可辨識的裝置名（如「Codex on <主機名>」），成員可單獨撤回或就地重新產生；撤回後該台 Codex 即失效，其他裝置不受影響。

**Why this priority**: 讓「自動拿到的憑證」仍受成員掌控、符合原則 1（每把可單獨撤回、不連坐）；非 MVP 阻斷項，但缺了會讓自動 mint 的憑證變黑箱。

**Independent Test**: 完成一次 device-flow 安裝 → 在 dashboard「裝置與憑證」看到新出現的具名憑證 → 撤回它 → 該台 `codex` 呼叫被拒、同分配其他憑證仍可用。

**Acceptance Scenarios**:

1. **Given** 完成 device-flow 安裝，**When** 檢視「裝置與憑證」清單，**Then** 看到一把具名（含裝置識別）的 active 憑證、有建立/最後使用時間。
2. **Given** 成員撤回該憑證，**When** 該台 Codex 再呼叫，**Then** 被拒（鑑權失敗），同分配其他憑證仍正常。
3. **Given** device-flow，**When** 成員授權他人分配或未登入，**Then** 不得 mint（擁有者邊界、需登入）。

---

### Edge Cases

- **未裝前置（Node 等）**：腳本自行處理（抓獨立 binary、免 Node），成員不需先自行安裝任何東西。
- **Windows / macOS / Linux 差異**：執行原則、PATH、防毒/Gatekeeper 對下載腳本的攔截——各 OS 需有可行路徑與白話指引。
- **授權逾時 / 未授權 / 被拒**：device code 有短 TTL；逾時顯示「請重跑指令」；輪詢遵守標準節流（pending / slow_down / expired）。
- **成員尚無任何分配**：授權頁引導先領取一個 model 分配（自助），再繼續。
- **重複執行安裝指令**：idempotent；再跑一次不弄壞既有設定（可選擇沿用既有憑證或換新）。
- **憑證撤銷／更換**：成員重跑安裝（或就地 rotate）即可更新，不需工程師。
- **平台未開該 model**：回清楚訊息，不是 401。
- **同一台重裝**：可重新授權拿新憑證；舊的留在清單供成員自行撤回（或安裝時提示）。

## Requirements *(mandatory)*

### Functional Requirements

**安裝與設定（US1–US3）**

- **FR-001**: dashboard MUST 針對成員的 OS 顯示**一行安裝指令**（Windows / macOS / Linux 各一），可一鍵複製。
- **FR-002**: 安裝指令 MUST 取得並安裝 Codex CLI **不需成員預裝 Node**（採獨立可執行檔）。
- **FR-003**: 安裝 MUST 設定 Codex 以**自訂 provider** 指向本平台（Responses 介面、需平台鑑權、停用 WebSocket），使日常 `codex` 零參數即連到本平台。
- **FR-004**: 安裝 MUST 把憑證寫入 Codex 的鑑權設定，使日常使用**不需任何環境變數**。
- **FR-005**: 系統 MUST 確保在 Codex 內**切換 model 重寫設定後仍指向本平台**（不脫鉤）；**不得**依賴唯讀 config、wrapper/別名或啟動旗標。
- **FR-006**: 安裝結尾 MUST 跑一次測試呼叫並以白話顯示成功/失敗；失敗 MUST 給清楚原因與下一步。
- **FR-007**: 安裝 MUST idempotent——重跑不破壞既有可用設定。

**device-flow 免貼 token（US1、US4）**

- **FR-008**: 系統 MUST 提供 device-flow：安裝腳本取得一組**裝置碼 + 使用者短碼 + 授權網址**，成員在**已登入的瀏覽器**確認授權，腳本以裝置碼**輪詢**取得結果——**全程不需複製貼上 token**。
- **FR-009**: 授權步驟 MUST 讓成員**選擇要綁定的分配（model）**；若成員尚無分配，MUST 引導其先自助領取。
- **FR-010**: 授權核可時，系統 MUST **新 mint 一把 per-device 憑證**（綁定該分配、具可辨識裝置名），明文**僅交給該次輪詢一次**、其後只存雜湊（沿用階段 18 show-once + hash-only）。
- **FR-011**: 裝置碼/短碼 MUST 有**短時效**（逾時失效）、**單次使用**；輪詢 MUST 遵循標準節流回應（授權中 / 放慢 / 已逾時 / 已拒絕），不可被當作開放輪詢濫用。
- **FR-012**: 授權 MUST 受**擁有者邊界**約束——只有**已登入且為該分配擁有者**的成員能核可；未登入或非擁有者不得 mint。
- **FR-013**: device-flow mint 的憑證 MUST 出現在成員既有「裝置與憑證」清單，可**單獨撤回 / 就地 rotate**（階段 18 能力），撤一把不連坐。
- **FR-014**: device-flow 授權與核可/拒絕 MUST 留稽核紀錄（誰、何時、綁哪個分配）。

**跨平台與相容（US1–US3）**

- **FR-015**: 安裝流程 MUST 在 **Windows、macOS、Linux** 皆可行，並對各 OS 的攔截（防毒 / Gatekeeper / PATH）給白話指引。
- **FR-016**: 既有 `/v1/responses`、`/v1/chat/completions`、計費、配額、proxy 行為 MUST 零回歸（本功能不改上游協定）。

### Key Entities *(include if feature involves data)*

- **裝置授權請求（Device Authorization Request）**：device-flow 的一次授權嘗試。屬性：裝置碼、使用者短碼、狀態（待授權 / 已核可 / 已拒絕 / 已逾時）、建立與到期時間、核可後綁定的成員與分配、核可後對應 mint 的憑證參照。單次使用、短時效。
- **per-device 憑證（Credential）**：沿用階段 18；device-flow 核可時新建一筆，綁該分配、具裝置名、可單獨撤回/rotate。
- **安裝指令（Install Command）**：dashboard 針對成員 + OS 呈現的一行指令（呈現層；指向平台提供的安裝腳本與該成員的授權起點）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 全新成員從 dashboard 複製一行指令、在瀏覽器授權一次，即可在 **5 分鐘內**得到可用的零參數 `codex`，**全程未複製貼上 token、未手動設定任何環境變數**。
- **SC-002**: 安裝完成後於**全新終端機**直接打 `codex`（無參數）→ 100% 正常連到本平台。
- **SC-003**: 在 Codex 內切 model 後再次呼叫 → 仍走本平台（不打到 `api.openai.com`）；平台未開的 model 回清楚訊息而非 401。
- **SC-004**: device-flow 核可後 mint 的憑證 100% 出現在「裝置與憑證」清單、可單獨撤回；撤回後該台 Codex 立即失效、同分配其他憑證仍可用。
- **SC-005**: 裝置碼逾時後無法再被兌換；非擁有者 / 未登入者無法核可他人的裝置授權（0 例外）。
- **SC-006**: Windows、macOS、Linux 三平台各至少一次**真機驗收**通過 SC-001~SC-003。
- **SC-007**: 既有 proxy / 計費 / 配額 / 領取憑證行為零回歸（既有測試全綠）。

## Assumptions

- **採 RFC 8628 Device Authorization Grant 的精神**（裝置碼 + 使用者短碼 + 輪詢），但本平台以既有 session 登入作為「使用者已認證」來源；不引入完整 OAuth server。
- **授權時綁分配**：一次 device-flow 對應**一個分配（model）**；成員在授權頁選定。日後同台要連別的 model，可再跑一次（或在清單管理）。
- **裝置名預設**取自安裝腳本可得的主機名/平台（如「Codex on <hostname>」），成員之後可在清單辨識；命名衝突不阻擋（憑證以 id 唯一）。
- **Codex 設定不脫鉤**沿用真機已驗的「merge-style 寫入 + 自訂 provider（`requires_openai_auth=true`、`supports_websockets=false`、`wire_api=responses`、base_url 指平台）+ `codex login --with-api-key`（auth.json）」原則；不採唯讀/wrapper。
- **保留手動 fallback**：device-flow 為主；若某環境無法開瀏覽器，dashboard 仍提供「手動貼一次憑證」的退路（沿用階段 18 已有的建立憑證 + 一次性複製）。
- **不需新增對外 egress**：安裝腳本在成員機器上下載 Codex binary（GitHub Releases）；平台後端不需新增外連。device-flow 全在平台內部（dashboard ↔ 後端）。
- **不做**：每日上限（願景已 descope）；不改 Codex 上游 Responses 協定（已上線）；不提供 GUI 安裝程式（以終端機一行指令為準）。
- **平台與部署**沿用既有（FastAPI + SQLAlchemy async + Alembic；React/Vite 前端；K8s/Helm 部署）。device-flow 的裝置授權請求需**新表 + migration**，依經驗「改/加 schema 的 migration 必在 Postgres 整合測試驗」。
