# Feature Specification: Responses API / Agent 工具（Codex）相容

**Feature Branch**: `021-responses-api`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "開放 `/v1/responses` 端點，讓 OpenAI Codex 等 agent CLI 用平台憑證即可使用；所有 provider 可用、精確分項計費（reasoning / cached token）、支援 server-side 對話狀態（store / previous_response_id）。第一版即交付完整能力，不留半成品。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 開發者用平台憑證跑 Codex agent 任務 (Priority: P1)

組織的開發者拿到一張平台分配的憑證後，把 Codex CLI 的 base URL 指向本平台、
填入該憑證，就能像連 OpenAI 官方一樣使用 Codex——包含多輪對話、工具呼叫、
以及推理（reasoning）模型。整段過程即時串流回應，使用者不需等待整段生成完成。
這次使用的 token 與花費，照常歸戶到他那張憑證所屬的分配。

**Why this priority**: 這是整個功能的核心動機與最小可交付價值——讓主流 agent
工具「開箱即用」並維持「單一入口、統一歸戶」。沒有這條，其餘都失去意義。

**Independent Test**: 用一張有效憑證設定 Codex（base URL + 憑證），執行一個需要
讀寫檔案（工具呼叫）且觸發推理的多輪任務，確認任務完成、回應即時逐步顯示、
且該次用量出現在對應分配的用量記錄中。

**Acceptance Scenarios**:

1. **Given** 一張有效且未被撤回的憑證、已設定好的 Codex CLI，**When** 使用者
   下達一個含工具呼叫的多輪指令，**Then** Codex 完成任務、回應以串流方式逐步
   呈現，且該次呼叫被歸戶到該分配並計入用量。
2. **Given** 一個推理模型，**When** Codex 發起需要推理的請求並在後續輪次帶回
   前一輪的推理脈絡，**Then** 跨輪推理脈絡被完整保留、任務連貫完成。
3. **Given** 一張已被撤回的憑證，**When** Codex 發起新請求，**Then** 請求立即
   被拒絕（不依賴憑證自然過期），且該拒絕被記錄並歸戶到該分配。
4. **Given** 一張本月用量已達配額上限的憑證，**When** 發起新請求，**Then**
   請求被拒絕並回傳清楚的配額已滿訊息。

---

### User Story 2 - 用量精確分項計費（含推理 / 快取 token） (Priority: P2)

成員與管理員在用量總覽中，能看到 Responses 呼叫的花費，且花費精確反映推理
token（推理模型的成本大宗）與快取輸入 token（命中快取應享折扣）。讓「帳目
清楚」延伸到 Responses 這條新管道，不會因 token 類別不同而少算或多算。

**Why this priority**: 對應領域原則「可追蹤性」——每次呼叫都要帳目清楚。推理
模型若把推理 token 漏算或快取不折扣，成本歸戶會失真，影響配額與費用判斷。

**Independent Test**: 對一個會產生推理 token 與快取命中的請求發一次呼叫，確認
用量記錄分別記載輸入、輸出、推理、快取 token，且計算出的花費符合對應價目
（推理計入輸出、快取套折扣）。

**Acceptance Scenarios**:

1. **Given** 一次觸發推理的呼叫，**When** 呼叫完成，**Then** 用量記錄包含推理
   token 數，且花費已涵蓋推理部分（不漏算）。
2. **Given** 一次有快取輸入命中的呼叫，**When** 呼叫完成，**Then** 用量記錄
   標示快取 token 數，且該部分以折扣價計費（而非全價）。
3. **Given** 某模型缺對應價目，**When** 呼叫完成，**Then** 用量仍被記錄、花費
   標為「未定價」，與既有計費行為一致。

---

### User Story 3 - 所有 provider 皆可經 Responses 呼叫 (Priority: P3)

成員可對平台上架、且被授權給自己的任何 provider 模型（Azure / OpenAI /
Anthropic / Gemini）發起 Responses 呼叫。OpenAI 家族模型完整保留其專屬進階
能力；其他家以等效方式回應，基本對話與工具呼叫照常可用。

**Why this priority**: 對齊願景「多 provider 統一以 OpenAI 相容介面開放」。先有
P1（OpenAI 家族）即可讓 Codex 可用；跨 provider 是價值擴張而非 MVP 前提。

**Independent Test**: 分別對一個 OpenAI/Azure 模型與一個非 OpenAI 模型發起
Responses 呼叫，確認兩者都成功回應並計費；OpenAI 家族的進階能力可用，非
OpenAI 家族以等效降級回應但不報錯。

**Acceptance Scenarios**:

1. **Given** 一個 OpenAI/Azure 模型，**When** 發起含進階能力的 Responses 呼叫，
   **Then** 進階能力完整生效。
2. **Given** 一個非 OpenAI 模型，**When** 發起 Responses 呼叫，**Then** 基本
   對話／工具呼叫成功，OpenAI 專屬進階能力等效降級但不致呼叫失敗。
3. **Given** 一個未標記支援 Responses 的模型，**When** 發起 Responses 呼叫，
   **Then** 回傳清楚的「此模型不支援此端點」訊息。

---

### User Story 4 - Server-side 對話狀態（store / previous_response_id） (Priority: P4)

不自帶完整對話脈絡的第三方 client，可要求平台保存其回應，並在後續請求以前一次
回應的識別碼接續對話。平台保存的回應嚴格歸屬到發起它的分配——任何人都無法以
他人分配產生的回應識別碼來接續或讀取對話。

**Why this priority**: 讓平台能服務 Codex 以外、依賴 server-side 狀態的 client，
功能完整。優先序最低是因 Codex 本身自帶脈絡、不走此路徑，故不阻擋 P1。

**Independent Test**: 以開啟「保存」的請求取得一個回應識別碼，於下一次請求帶入
該識別碼接續對話，確認脈絡延續；再以另一張分配的識別碼嘗試接續，確認被拒絕。

**Acceptance Scenarios**:

1. **Given** 一次要求保存的呼叫，**When** 完成後以回傳的回應識別碼發起下一次
   呼叫，**Then** 對話脈絡正確延續。
2. **Given** 分配 A 產生的回應識別碼，**When** 持分配 B 憑證的請求嘗試以該識別碼
   接續，**Then** 請求被拒絕（歸屬隔離）。
3. **Given** 一個已超過保存期限的回應識別碼，**When** 以它接續，**Then** 回傳
   清楚的「找不到 / 已過期」訊息。

### Edge Cases

- **串流中途斷線**：使用者端在回應串流途中斷線時，已產生的用量仍須被記錄並
  歸戶；不可因未走完而漏記。
- **串流進行中憑證被撤回**：撤回對「新」請求立即生效；已開始的串流不被強制
  中斷（與既有呼叫一致），此邊界須在驗收中明列。
- **底層供應商錯誤**：上游回錯時，回給使用者的錯誤訊息與日誌絕不可包含底層
  供應商的 API key 或其他憑密。
- **推理 token 但無快取 / 有快取但無推理**：各種 token 類別的組合都要正確
  分項記錄，缺某類別以 0 或空計，不可整筆漏記。
- **模型支援 Responses 但成員無權存取該模型**：須在歸屬與計費前，沿用既有
  存取政策拒絕。

## Requirements *(mandatory)*

### Functional Requirements

**端點與相容性**
- **FR-001**: 系統 MUST 提供一個與 OpenAI Responses API 相容的呼叫端點，接受
  Responses 形態的請求（以 `input` 為主，含工具、推理、include 等選項）。
- **FR-002**: 系統 MUST 以串流方式即時回傳回應，讓使用者端逐步收到內容而非
  等待整段生成完成。
- **FR-003**: 系統 MUST 完整保留 agent 工具（function calling）的請求與回應，
  使 Codex 等 agent 工具能完成含工具呼叫的多輪任務。
- **FR-004**: 對 OpenAI 家族模型，系統 MUST 完整保留其專屬進階能力（含推理
  脈絡跨輪接續）；對非 OpenAI 模型 MUST 以等效方式回應，基本對話與工具呼叫
  不因進階能力缺位而失敗。
- **FR-005**: 系統 MUST 僅對被標記為支援 Responses 的模型開放此端點；對不支援
  的模型回傳清楚的不支援訊息。

**身份、歸屬與安全（領域原則）**
- **FR-006**: 系統 MUST 對每一次 Responses 呼叫套用與既有對話補全相同的前置
  檢查：憑證驗證、分配狀態、配額、模型綁定、模型存取政策。
- **FR-007**: 系統 MUST 將每一次 Responses 呼叫（成功與被拒）歸戶到具體分配，
  不存在匿名或無歸屬的呼叫。
- **FR-008**: 系統 MUST 確保底層供應商憑密（API key 等）絕不出現於 API 回應、
  串流內容、錯誤訊息或日誌。
- **FR-009**: 憑證被撤回後，系統 MUST 立即拒絕該憑證的新 Responses 請求，
  不依賴憑證自然過期。

**計費（可追蹤性）**
- **FR-010**: 系統 MUST 針對每次 Responses 呼叫，分項記錄輸入、輸出、推理、
  快取輸入 token 數。
- **FR-011**: 系統 MUST 在計費時將推理 token 計入成本（不漏算），並對快取
  輸入 token 套用對應的折扣價（若該模型有定義快取價）。
- **FR-012**: 當模型缺對應價目時，系統 MUST 仍記錄用量並將花費標為未定價，
  與既有行為一致。

**Server-side 對話狀態**
- **FR-013**: 系統 MUST 支援「要求平台保存回應」的請求選項，並回傳可供後續
  接續的回應識別碼。
- **FR-014**: 系統 MUST 支援以前一次回應識別碼接續對話，並延續對話脈絡。
- **FR-015**: 系統 MUST 嚴格將已保存的回應歸屬到產生它的分配；任何請求 MUST
  無法以非自身分配產生的回應識別碼接續或讀取。
- **FR-016**: 系統 MUST 對已保存的回應設定保存期限，逾期後以「找不到 / 已過期」
  回應接續請求，並可清理逾期資料。

**可靠性**
- **FR-017**: 當回應串流中途因使用者端斷線而未走完時，系統 MUST 仍記錄並歸戶
  已產生的用量。
- **FR-018**: 系統 MUST 確保串流端到端不被中介緩衝，使用者端能即時收到增量
  內容、不因緩衝造成逾時。

### Key Entities *(include if feature involves data)*

- **Responses 呼叫記錄**：一次 Responses 呼叫的稽核與計費單位。延伸既有呼叫
  記錄的概念，額外涵蓋推理 token 與快取輸入 token 的分項；綁定到分配與身份，
  記載結果（成功 / 各類拒絕）、token 各類別數量與花費。
- **已保存的回應（Stored Response）**：當請求要求保存時產生，供後續以識別碼
  接續。關鍵屬性：回應識別碼、所屬分配、對話脈絡內容、建立時間、保存期限。
  嚴格歸屬於單一分配。
- **模型的 Responses 支援標記**：模型目錄上用以判定該模型是否可經 Responses
  端點呼叫的能力標記；決定 FR-005 的開放與否。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 開發者把 Codex 指向平台並填入分配憑證後，能完成一個含工具呼叫
  與推理的多輪 agent 任務，無需任何 OpenAI 官方帳號。
- **SC-002**: 上述任務的用量 100% 歸戶到對應分配，且花費分項涵蓋輸入 / 輸出 /
  推理 / 快取四類 token，無漏算。
- **SC-003**: 平台上架的四家 provider（Azure / OpenAI / Anthropic / Gemini）
  模型皆可經 Responses 端點成功呼叫並計費。
- **SC-004**: 以「保存」取得的回應識別碼可在後續請求成功接續對話；且以他人
  分配的識別碼接續的嘗試 100% 被拒絕（歸屬隔離無漏洞）。
- **SC-005**: 回應內容以串流方式即時、逐步抵達使用者端（非整段一次抵達），
  且在正式部署環境下不發生因緩衝造成的逾時或閘道錯誤。
- **SC-006**: 被撤回憑證的新請求即時被拒；串流中途斷線的呼叫其已產生用量
  仍被記錄。
- **SC-007**: 底層供應商憑密在回應、串流、錯誤訊息與日誌中皆不可見（以負向
  測試驗證）。

## Assumptions

- **沿用既有前置 pipeline**：Responses 端點重用既有對話補全的憑證 / 分配 /
  配額 / 模型綁定 / 存取政策邏輯，不另建一套平行授權。
- **混合相容策略屬範圍內的明確假設**：OpenAI 家族模型以最高保真方式對外
  （完整保留專屬進階能力），非 OpenAI 家族以等效方式對外（進階能力等效降級）。
  非 OpenAI 模型「完全對等模擬 OpenAI 專屬語意」明確排除於本功能之外（屬協定
  物理限制）。
- **Codex 自帶脈絡**：Codex 預設不依賴 server-side 保存（自帶完整對話脈絡），
  故 P1 不依賴 P4；P4 是為其他依賴 server-side 狀態的 client 而備。
- **計費資料模型擴充**：分項記錄推理 / 快取 token 需擴充用量記錄與價目資料，
  屬本功能範圍。
- **部署沿用既有形態**：以既有 Kubernetes / 反向代理部署形態交付，串流不緩衝
  屬部署層需驗證的前提。
- **現狀前置已具備**：多 provider 上游、計費 pipeline、憑證 / 分配 / 部署皆已
  上線（階段 5 / 3a / 8），本功能在其上擴充。
