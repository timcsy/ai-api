# Feature Specification: Rule-Based Auto-Tagging

**Feature Branch**: `014-auto-tag-rules`
**Created**: 2026-05-25
**Status**: Draft
**Input**: User description: "Admin-managed ordered rules that auto-assign tags at first registration (matcher: email_localpart_regex / email_suffix / email_domain), tags marked source=auto, regex guarded, admin UI CRUD + ordering + email test preview"

## 問題陳述

目前成員的 tag 全靠手動指派（inline 或批次貼標）。組織常見的分類其實能從 email 自動推導——例如教育機構用同一網域，但**學生的 email local-part 是學號格式（字母+數字）、老師不是**。每來一個新成員都要 admin 手動判斷並貼 tag，量大時不可行、且容易漏。

需求：admin 能定義**有序規則**，新成員**首次註冊**時系統自動依規則貼上對應 tag。tag 照常進入既有的存取控制（credential gate ∩ access policy）；自動貼的 tag 標記 `source=auto` 以利辨識與稽核。

本 feature **不改既有 tag / 診斷 / access policy 機制**——auto tag 就是普通 tag，只是多了來源標記與「誰貼的」差異。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin 定義學生/老師自動分類規則 (Priority: P1)

教育機構 admin 想讓 `b10901234@school.edu`（學號格式）自動貼 `student`、其他（如 `prof.wang@school.edu`）自動貼 `teacher`。

**Why this priority**：這是整個 feature 的核心價值；沒有規則定義就沒有自動標籤。

**Independent Test**：admin 建立 2 條規則（規則1：local-part 符合學號 regex → student；規則2：fallback → teacher），用「測試 email」功能輸入 `b10901234@school.edu` 得 `student`、輸入 `prof.wang@school.edu` 得 `teacher`，不需實際建立成員。

**Acceptance Scenarios**：
1. **Given** admin 在規則管理頁，**When** 新增一條 `email_localpart_regex` 規則 pattern `[a-z]{0,2}\d{6,}` → tag `student`，**Then** 規則儲存且顯示在列表，標明 order
2. **Given** 已有多條規則，**When** admin 調整順序，**Then** 規則依新順序評估（first-match-wins）
3. **Given** admin 輸入一個惡意 regex（如巢狀量詞 `(a+)+$`），**When** 儲存，**Then** 系統拒絕並提示 regex 不安全 / 過於複雜
4. **Given** admin 在規則管理頁，**When** 用「測試 email」輸入一個 email，**Then** 立即顯示「會貼哪些 tag、命中哪條規則」而不需建立成員

### User Story 2 — 新成員首次註冊自動貼 tag (Priority: P1)

新成員透過 SSO / 白名單 / 自動註冊條件首次進入系統時，規則引擎自動評估其 email 並貼上對應 tag。

**Why this priority**：規則沒有在註冊時實際執行就毫無作用。

**Independent Test**：設好規則後，用學號格式 email 完成首次註冊，查該成員的 tag 應含 `student` 且 `source=auto`。

**Acceptance Scenarios**：
1. **Given** 規則「學號→student」「fallback→teacher」已啟用，**When** `b10901234@school.edu` 首次註冊，**Then** 該成員自動獲得 `student` tag，標記 `source=auto`
2. **Given** 同上，**When** `prof.wang@school.edu` 首次註冊，**Then** 自動獲得 `teacher` tag（fallback 命中）
3. **Given** 規則有多條都可能命中，**When** 成員註冊，**Then** 只套用**第一條命中**的規則（first-match-wins），不疊加
4. **Given** 自動貼 tag 後，**When** 該 model 的 access policy 用到此 tag，**Then** 該成員的可見性立即依此 tag 計算（與手動 tag 行為一致）
5. **Given** 成員已存在（非首次），**When** 再次登入，**Then** 規則**不重跑**（只在首次註冊觸發）

### User Story 3 — Auto tag 的辨識與稽核 (Priority: P2)

Admin 需要分辨某 tag 是「規則自動貼的」還是「手動貼的」，並能在需要時手動覆蓋。

**Why this priority**：避免 admin 困惑「這 tag 哪來的」，也讓手動調整有依據。

**Acceptance Scenarios**：
1. **Given** 成員有 auto tag + manual tag，**When** admin 看該成員 tag，**Then** auto tag 有視覺標記（如「自動」小標）區別於 manual
2. **Given** admin 手動移除一個 auto tag，**When** 該成員再次登入，**Then** tag **不會**被重新貼回（因規則只在首次註冊跑）
3. **Given** 自動貼 tag 發生，**When** 查稽核紀錄，**Then** 有 `member_tag_added` 事件，details 標明 `source=auto` 與命中的 rule id

### Edge Cases

- **無規則命中且無 fallback**：成員不獲任何 auto tag（正常，非錯誤）
- **規則 pattern 在建立後變無效**（理論上不會，因建立時驗證）：載入時跳過該規則並記錄警告，不可讓整個註冊流程崩潰
- **同一 tag 被多條規則指向**：first-match 後不重複貼
- **email local-part 超長**（>64）：regex 比對前先截斷或拒絕，避免 ReDoS 放大
- **規則停用（enabled=false）**：評估時跳過
- **手動已有某 tag、規則又要貼同一 tag**：不重複（既有 add idempotent）
- **disabled 成員**：規則只在首次註冊跑，與後續狀態無關

## Requirements *(mandatory)*

### Functional Requirements

**規則定義**
- **FR-001**: 系統 MUST 讓 admin 建立、編輯、刪除、停用 tag 規則
- **FR-002**: 每條規則 MUST 有：order（評估順序）、matcher_type、pattern、目標 tag、enabled 旗標
- **FR-003**: 系統 MUST 支援三種 matcher_type：
  - `email_localpart_regex`：對 email `@` 前段做 regex 比對（學號用）
  - `email_suffix`：email 結尾字串比對（單位/網域用）
  - `email_domain`：email `@` 後段完全比對
- **FR-004**: 系統 MUST 支援「fallback 規則」概念（一條永遠命中的規則，作為都不中時的預設）—— 可用一個特殊 matcher 或排在最後的 catch-all 表達
- **FR-005**: 系統 MUST 允許 admin 調整規則順序；評估採 **first-match-wins**

**Regex 安全**
- **FR-006**: 建立 / 編輯 `email_localpart_regex` 規則時，系統 MUST 驗證 pattern：
  - 可被成功 compile
  - 自動 anchor（`^...$`）或要求 admin 已 anchor
  - 拒絕明顯的 ReDoS 高風險 pattern（如巢狀量詞）
- **FR-007**: 評估 regex 前，系統 MUST 限制輸入長度（local-part ≤ 64 字元）

**自動貼標執行**
- **FR-008**: 系統 MUST 在成員**首次註冊**時（不論 SSO / local / 白名單 / 自動註冊路徑）執行規則評估
- **FR-009**: 規則評估 MUST 是 first-match-wins：只套用第一條命中的規則對應的 tag
- **FR-010**: 自動貼的 tag MUST 標記來源 `source=auto`（含命中的 rule 識別）；手動貼的維持 `source=manual`
- **FR-011**: 規則評估 MUST **不**在後續登入重跑（只首次註冊）
- **FR-012**: 自動貼 tag MUST 寫稽核事件，details 標明 source=auto 與 rule id

**辨識與覆蓋**
- **FR-013**: 成員 tag 顯示 MUST 區分 auto 與 manual（視覺標記）
- **FR-014**: Admin MUST 能手動移除 auto tag；移除後不會因登入被重貼（呼應 FR-011）

**測試工具**
- **FR-015**: 規則管理頁 MUST 提供「測試 email」功能：輸入任意 email，回傳「會命中哪條規則、貼哪個 tag」，不建立成員、不寫 DB

**相容性**
- **FR-016**: Auto tag MUST 與既有 tag 完全等價地進入 access policy（credential gate ∩ access policy）、診斷工具、tag 詳情頁——不需修改這些既有功能
- **FR-017**: 既有手動 tag 機制（inline 編輯 / 批次貼標）MUST 不受影響

### Key Entities

- **TagRule**：admin 定義的自動標籤規則。屬性：id、order（整數，決定評估順序）、matcher_type（`email_localpart_regex` / `email_suffix` / `email_domain`）、pattern（比對字串 / regex）、tag（命中時要貼的 tag 名稱）、enabled、建立資訊
- **MemberTag（既有，擴充）**：加 `source` 欄位（`manual` / `auto`）+ 選填「來源 rule 識別」，讓 auto tag 可辨識與稽核

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Admin 能在 **3 分鐘內**建立「學生/老師」兩條規則並用測試 email 驗證正確
- **SC-002**: 設好規則後，新成員首次註冊後 **100%** 依規則獲得正確 tag（學號→student、其他→teacher）
- **SC-003**: 惡意 / 高風險 regex 在儲存時 **100% 被拒絕**，不會進入 DB
- **SC-004**: 規則評估在註冊流程中增加的延遲 **< 100ms**（首次註冊，非每次登入）
- **SC-005**: Auto tag 與 manual tag 在 access policy / 診斷 / tag 詳情的行為**完全一致**（既有測試零回歸）
- **SC-006**: Admin 在成員 tag 顯示處能一眼分辨 auto vs manual

## Assumptions

- 學生/老師**同網域**（所以需要 local-part regex 分辨；若不同網域則 suffix 即可，本 feature 仍支援）
- 規則由 admin 在 UI 管理（CRUD + 排序 + 測試），非 YAML
- 規則只在**首次註冊**觸發；不做「定期重算」「email 變更時重算」（YAGNI，可後續加）
- regex 使用 Python 標準 `re`，靠 anchor + 長度限制 + 複雜度檢查防 ReDoS；不引入 `re2`（首版判斷風險可控，因只在 cold path 跑一次）
- fallback 規則用「排最後的 catch-all matcher」表達，不另設特殊 schema
- 自動貼 tag 數量上限沿用既有 member tag 限制
- 規則數量預期 < 20 條（組織分類規則不多）
