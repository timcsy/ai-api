# Feature Specification: Codex 安裝腳本硬化——既有登入/設定殘留處理 + 桌面版關閉提醒

**Feature Branch**: `052-codex-install-hardening`
**Created**: 2026-06-29
**Status**: Draft
**Input**: User description: "Codex 安裝腳本硬化：處理既有 Codex 登入/設定殘留（先備份 auth.json 與 config.toml 再重設成乾淨可用狀態）+ 提醒先關閉預裝的 Codex 桌面版（含 Windows 工作列常駐）才能正常運作"

## 背景與問題

一鍵安裝 Codex 並指向本平台，原本設計成「合併式、不脫鉤、可與既有設定共存」。但真機（Windows）暴露兩個會讓**裝了卻不能用**的破口——正是原則 6 可達性的反面（能力發了、使用者卻被無聲卡住、得求工程師）：

1. **既有 Codex 登入/設定殘留**：使用者若先前已登入 Codex（用 ChatGPT 帳號 / 別的 API key）或有舊的設定，殘留的登入會「搶優先權」、或舊設定與本平台衝突，導致安裝後仍連不上本平台、且錯誤難懂。
2. **預裝桌面版在執行中**：若使用者已裝 Codex 桌面版且**還開著**（含 Windows 工作列／系統匣常駐圖示），執行中的 App 會把共用設定握在手上（退出時回寫／鎖檔），使腳本寫入的設定被覆寫或忽略，直到關閉桌面版重開才生效。

本功能讓一鍵安裝**對「已經有 Codex」的使用者也能可靠成功**：動既有設定前先安全備份、把連線狀態重設成乾淨可用、並在動手前提醒關閉執行中的桌面版；任何無法達成的情況明確告知，不留「看似成功、實際連不上」。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 既有 Codex 使用者一鍵安裝後直接可用（Priority: P1）

一位先前已用 ChatGPT 帳號（或別的 API key）登入過 Codex 的成員，跑一鍵安裝後，**不必自己手動清任何檔案**，Codex 就以本平台憑證連線、可正常呼叫。

**Why this priority**: 這是本功能的核心價值；「已經有 Codex 的人裝不起來」是目前最痛的破口，直接擋住可達性。

**Independent Test**: 在一台「Codex 已登入既有帳號」的機器跑一鍵安裝，事後不手動清檔，直接用 Codex 對本平台跑一次對話成功。

**Acceptance Scenarios**:

1. **Given** 一台 Codex 已用 ChatGPT 帳號登入的機器，**When** 跑一鍵安裝，**Then** 安裝後 Codex 預設以本平台憑證連線、可成功對話（殘留登入不再搶優先權）。
2. **Given** 一台 config.toml 已有舊設定（含舊的預設模型/登入偏好）的機器，**When** 跑一鍵安裝，**Then** 與本平台連線相關的設定被重設為可用值、Codex 連得上本平台。
3. **Given** 重複跑第二次一鍵安裝，**When** 完成，**Then** 結果與第一次一致（冪等、不疊加重複設定、不破壊已可用狀態）。

---

### User Story 2 - 動既有設定前先備份、且可一行復原（Priority: P2）

安裝在修改使用者既有的 `auth.json` / `config.toml` 之前先備份，並在完成時清楚告知備份位置與復原方式；**不無聲破壞**使用者原本的設定。

**Why this priority**: 重設既有設定本質上是動使用者的資料；可復原是安全網。沒有它，重設會嚇跑（或實際傷到）已在用 Codex 的人。

**Independent Test**: 在有既有 auth.json/config.toml 的機器跑安裝，確認產生帶時間戳的備份、輸出明示備份路徑與一行復原指令，且依該指令可還原。

**Acceptance Scenarios**:

1. **Given** 既有 `config.toml` 與 `auth.json`，**When** 安裝即將修改它們，**Then** 先各產生一份**帶時間戳**的備份（重跑不覆蓋舊備份）。
2. **Given** 安裝完成，**When** 看安裝輸出/安裝卡，**Then** 明確顯示備份在哪、以及一行如何復原。
3. **Given** 使用者於 `config.toml` 有與本平台無關的設定（其他 provider / MCP / 專案設定），**When** 安裝執行，**Then** 這些設定要嘛被保留、要嘛（若採整檔重置）已被備份且明確告知會被取代——**絕不無聲消失**。

---

### User Story 3 - 預裝桌面版需先關閉的提醒（Priority: P2）

若使用者已安裝 Codex 桌面版，安裝流程在動手前提醒「請先完全關閉桌面版（含 Windows 工作列／系統匣常駐），裝好再開」，避免設定被執行中的 App 吃掉。

**Why this priority**: 不提醒就會出現「照做了卻沒生效」的沉默失敗；一句提醒成本極低、避坑效果大。

**Independent Test**: 檢視安裝卡與腳本輸出，確認在執行前出現明確的「先關閉桌面版（含工作列常駐）」提醒（Windows 尤其顯眼）。

**Acceptance Scenarios**:

1. **Given** 安裝卡（Windows 分頁），**When** 使用者閱讀，**Then** 看到「若已裝 Codex 桌面版，請先完全關閉（含工作列／系統匣常駐）再執行，裝好再開」的明確提醒。
2. **Given** 執行安裝腳本，**When** 腳本開始，**Then** 在動既有設定前先輸出同一則提醒。

---

### Edge Cases

- **從未裝過 Codex / 無既有設定**：無檔可備份時不應報錯，照常走乾淨安裝（備份步驟優雅略過）。
- **備份目錄不可寫**：應明確告知（fail loud），不要在沒備份的情況下硬改既有檔。
- **桌面版偵測**（若實作自動偵測）：偵測不到行程不代表沒裝；偵測為輔，提醒為主。
- **三平台差異**：Windows（ps1）/ macOS / Linux（sh）皆須有備份、重設、提醒；路徑與常駐關閉方式依平台。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 一鍵安裝 MUST 在「使用者先前已登入過 Codex（ChatGPT/OAuth 或他人 API key）」的情況下，仍使 Codex 最終以本平台憑證連線並可正常呼叫——殘留登入不得搶走優先權。
- **FR-002**: 安裝 MUST 在修改 `auth.json` / `config.toml` 前，先建立**帶時間戳的備份**；重複執行不得覆蓋先前備份。
- **FR-003**: 安裝 MUST NOT **無聲**移除使用者於 `config.toml` 中與本平台無關的既有設定；若需重置衝突項，僅重置與本平台連線相關者、其餘保留——**或**（若採整檔重置）必以備份 + 明確告知補償。
- **FR-004**: 安裝完成 MUST 告知使用者備份位置與**一行復原**方式。
- **FR-005**: 安裝卡與安裝腳本 MUST 提醒：若已裝 Codex 桌面版，需先**完全關閉**（含 Windows 工作列／系統匣常駐）再執行、裝好再開。
- **FR-006**: 若安裝無法達成「乾淨可用」狀態（衝突無法安全處理、備份失敗等），MUST 明確告知（fail loud），不得留下「看似成功、實際連不上」。
- **FR-007**: 重複執行 MUST 冪等——不疊加重複的本平台設定、不破壞已可用狀態。
- **FR-008**: 三平台（Windows / macOS / Linux）行為一致：備份、重置、提醒皆於對應腳本（sh / ps1）實現。

### Key Entities

*(本功能不涉及伺服器資料模型——只動使用者本機的 `~/.codex/auth.json`、`~/.codex/config.toml` 與安裝腳本/安裝卡文案；無新增/變更平台資料或 schema。)*

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 一位先前用 ChatGPT 帳號登入過 Codex 的使用者，跑一鍵安裝後**不手動清任何檔**，即可用本平台成功跑一次對話。
- **SC-002**: 安裝後，使用者原本的 `auth.json` / `config.toml` 可在備份找到，並依輸出的一行指令成功復原。
- **SC-003**: 安裝不會讓使用者 `config.toml` 中與本平台無關的設定無聲消失（保留，或已備份+告知後取代）。
- **SC-004**: 安裝卡與腳本輸出皆明確出現「先關閉桌面版（含工作列常駐）」提醒。
- **SC-005**: 重複執行兩次，最終狀態一致且皆可用（冪等）。
- **SC-006**: Windows / macOS / Linux 三平台各真機驗一次「既有登入 → 安裝 → 可用」。

## Assumptions

- **待真機校正（實作前以真機探測確認，別照文件/臆測硬編）**：Codex 的登入優先權機制與確切設定鍵（如是否有 `preferred_auth_method` 之類）、以及 `codex logout` 是否足以清除殘留登入而不需手寫 `auth.json`。呼應經驗「採用前先驗證能力邊界 / 別硬編外部工具的檔案格式、用它的 CLI」。
- **auth.json 重置優先用 Codex 自身指令**（`codex logout` → `codex login --with-api-key`）而非手寫其內部格式（跨版本較穩）。
- **config.toml 重置策略**（外科手術式合併 vs 整檔覆寫）於 plan/research 階段定案；**無論何者都先備份 + 告知**，且不得無聲破壞無關設定。
- **桌面版自動偵測**（偵測行程在跑就暫停提示）列為**可選加分**；第一版以「提醒」為主（YAGNI）。
- **install 模板為後端檔**（`src/ai_api/install/codex.{sh,ps1}.tmpl`，由 `install.py` 提供）→ 改它需重建 backend image；安裝卡為前端。
- **真機驗收為門檻**（SC-006），非自動化測試可完全涵蓋——沿用階段 19 三平台真機驗收模式。
- 對應願景：Codex 接入體驗打磨（延續階段 19 一鍵安裝 / 29 多端點接入），階段歸屬於 plan 時定（可記為階段 38 或階段 37 後續）。
