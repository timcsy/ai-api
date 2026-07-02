# Feature Specification: 本地登入允許以「帳號」（非 email）登入

**Feature Branch**: `055-username-login`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "local 登入能不能不要限定 email；影響、自動 tag 是否要改、是否有 email 認證需求"

## 背景與問題

目前本地帳密登入強制使用 **email 格式**當帳號。但組織內不少使用者沒有（或不想用）email 當登入名——他們要的只是一個**帳號**。系統其實**從不寄信給成員、也沒有任何 email 驗證流程**（邀請是管理員手動交付的 token 連結，SMTP 只用於管理員通知），所以「email」在本地登入上只是一個**未驗證的識別字串**，強制它是 email 格式並無實質意義，反而擋住了「用帳號登入」這個合理需求。

本功能讓**本地帳密成員可用帳號（任意識別字串）登入**，email 型帳號與 Google 登入（OIDC）維持不變、可混用。識別碼沿用既有「成員唯一識別」欄位（不另立資料結構），故不需資料庫結構變更。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 成員以帳號登入（Priority: P1）

一位沒有 email 的成員，用管理員給他的**帳號 + 密碼**登入，流程與體驗和 email 登入完全相同（同樣的錯誤提示、速率限制、session）。

**Why this priority**: 這是本功能的核心價值——把「登入名必須是 email」的無謂限制拿掉。

**Independent Test**: 建一個帳號型本地成員並設好密碼，用帳號 + 密碼登入成功、拿到 session；用錯密碼得到與 email 登入一致的通用錯誤。

**Acceptance Scenarios**:

1. **Given** 一個帳號型本地成員（識別碼非 email 格式）已設密碼，**When** 用該帳號 + 正確密碼登入，**Then** 登入成功、建立 session、行為與 email 登入一致。
2. **Given** 同上帳號，**When** 用錯誤密碼，**Then** 回**通用**「帳號或密碼錯誤」（不透露帳號是否存在），並計入速率限制與稽核。
3. **Given** 帳號大小寫不同（如 `Alice` vs `alice`），**When** 登入，**Then** 視為同一帳號（大小寫不敏感，與 email 收斂一致）。

---

### User Story 2 - 管理員建立/邀請「帳號型」本地成員（Priority: P1）

管理員在建立本地成員時，可填入**帳號**（非 email）作為登入識別碼並發出邀請連結；不需要提供 email。

**Why this priority**: 沒有建立途徑，US1 就無從發生。與 US1 並列核心。

**Independent Test**: 用帳號建立本地成員 → 拿到邀請連結 → 成員設密碼 → 能登入。

**Acceptance Scenarios**:

1. **Given** 管理員在建立成員表單，**When** 填入一個帳號（非 email）並送出，**Then** 成員建立成功、產生邀請連結，且介面不因「非 email」而擋下。
2. **Given** 一個已存在的識別碼（email 或帳號），**When** 再用同一字串建立，**Then** 以「重複」擋下（識別碼唯一）。
3. **Given** 非法識別碼（空白、含空格、超長），**Then** 被擋下並說明。

---

### User Story 3 - 帳號型成員也能被自動分組（Priority: P2）

自動 tag 規則能套用到帳號型成員（不只是 email 網域）。

**Why this priority**: 現有自動分組多以 email 網域為條件；帳號型成員若完全無法被自動 tag，會回到「手動貼標」。屬體驗完善，依賴既有 tag 規則機制。

**Independent Test**: 設一條能匹配帳號的規則，建一個符合的帳號型成員，確認自動獲得對應 tag；網域式規則對帳號型成員不誤匹配。

**Acceptance Scenarios**:

1. **Given** 一條可匹配「帳號本身」的規則，**When** 建立符合的帳號型成員，**Then** 該成員自動獲得對應 tag。
2. **Given** 一條「email 網域」規則，**When** 帳號型成員（無網域）評估，**Then** **不匹配**（不誤判），且不造成錯誤。
3. **Given** 管理員的「測試某識別碼會吃到哪些 tag」工具，**When** 輸入一個帳號，**Then** 能正常測試（不因非 email 被擋）。

---

### User Story 4 - email 型與 OIDC 成員不受影響、可混用（Priority: P3）

既有 email 型本地成員與 Google（OIDC）成員一切照舊；帳號型與 email 型可同時存在。

**Why this priority**: 相容性保證，非新價值，但必須成立。

**Acceptance Scenarios**:

1. **Given** 既有 email 本地成員，**When** 登入，**Then** 行為與現況完全一致。
2. **Given** Google 登入（OIDC），**When** 登入，**Then** 不受影響（OIDC 仍帶真 email、email 網域式自動註冊/白名單照舊只作用於 OIDC）。
3. **Given** 帳號型與 email 型成員並存，**Then** 識別碼在同一命名空間仍唯一、彼此不衝突。

### Edge Cases

- **像 email 的帳號**：為保持「帳號 vs email」兩個空間乾淨，帳號**不得包含 `@`**（避免與 email 網域規則半匹配）；含 `@` 的識別碼一律視為 email、走 email 驗證。
- **大小寫**：識別碼一律收斂為小寫再比對（與 email 現行一致），避免 `Alice`≠`alice` 混淆。
- **無 email 的通知**：系統本就不寄信給成員，故帳號型成員不影響任何通知/驗證（沒有「驗證信」承諾要兌現）。
- **email 白名單 / 自動註冊**：僅作用於 OIDC 登入；帳號型本地成員由管理員建立 + 邀請把關，不經 email 白名單。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 本地登入 MUST 接受**任意識別字串**（含非 email 帳號），不再強制 email 格式；查詢與現行以識別碼比對一致。
- **FR-002**: 管理員 MUST 能以帳號（非 email）建立本地成員並發邀請，不需提供 email。
- **FR-003**: 識別碼 MUST 唯一（帳號與 email 共用同一命名空間、不得重複），且 MUST 收斂大小寫後比對。
- **FR-004**: 系統 MUST 擋下非法識別碼（空、含空白字元、超長）；帳號 MUST NOT 含 `@`（含 `@` 者視為 email）。
- **FR-005**: 帳號型成員的登入 MUST 沿用既有安全機制——通用錯誤（不枚舉）、每帳號 / 每來源速率鎖定、稽核、session 與 cookie 行為皆與 email 登入一致。
- **FR-006**: 自動 tag MUST 能套用於帳號型成員（至少可依「帳號本身」比對）；email 網域式規則對帳號型成員 MUST NOT 誤匹配、且 MUST NOT 出錯。
- **FR-007**: email 型本地成員與 OIDC 成員行為 MUST 與現況一致（零回歸）；email 網域式自動註冊 / email 白名單維持只作用於 OIDC。
- **FR-008**: 本功能 MUST NOT 需要資料庫結構變更（識別碼沿用既有唯一成員識別欄位）。
- **FR-009**: 管理員的「測試識別碼命中哪些 tag」工具 MUST 接受帳號（非 email）輸入。

### Key Entities *(include if feature involves data)*

- **登入識別碼（Login Identifier）**：成員的唯一登入名。沿用既有成員識別欄位；值可為 email（含 `@`）或帳號（不含 `@`）。大小寫不敏感、全域唯一。非新資料結構。
- **標籤規則（Tag Rule）**：既有；本功能確保其比對能作用於帳號型識別碼（依帳號本身比對），網域式條件對無網域者不匹配。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 沒有 email 的成員能用帳號 + 密碼登入成功，體驗（錯誤提示、鎖定、session）與 email 登入無差異。
- **SC-002**: 管理員能以帳號建立成員並邀請，全程不需填 email。
- **SC-003**: 帳號型成員可被至少一種自動 tag 規則命中；網域式規則對帳號型成員零誤判、零錯誤。
- **SC-004**: 既有 email 本地成員與 OIDC 成員行為零回歸（現有登入測試全數維持）。
- **SC-005**: 上線**不需任何資料庫結構變更（migration）**。
- **SC-006**: 帳號與 email 在同一命名空間唯一、可混用，無衝突。

## Assumptions

- **沿用既有識別欄位**：登入識別碼重用既有「成員唯一識別」欄位（原為 email），值改為可為帳號或 email——故零 migration（Option C 折衷）。不另立 username 欄位（避免雙軌與 migration）。
- **範圍界線**：只放寬**本地帳密**登入；OIDC 一律 email（其網域式自動註冊/白名單不變）。email 白名單頁維持 email 導向。
- **無 email 驗證**：系統現況不寄信給成員、無 email 驗證流程；本功能不引入、也不移除任何驗證（本就沒有）。
- **自動 tag**：優先沿用既有「比對識別碼本身（localpart/regex）」能力；如需更清楚可加一個「帳號比對」規則型別（可為字串值、不需結構變更）。網域/後綴式規則對無網域帳號自然不匹配。
- **對應原則**：**原則 6 可達性**（降低登入門檻、不強加 email）；**原則 2 可追蹤性**（識別碼仍唯一、稽核不變）；相容性守住 **零回歸**。
