# Feature Specification: 成員自助用量總覽

**Feature Branch**: `018-member-usage-overview`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "Member self-service usage overview: members see their own aggregate usage (tokens, estimated cost, call count, per-model breakdown, time range) on their dashboard, strictly scoped to themselves. MVP = dashboard summary line + member-scoped /me/usage reusing aggregate_usage."

## 背景

成員目前只能在分配詳情頁逐張看「最近呼叫」與該張配額，看不到「我整體用了多少」——跨自己所有分配的 token 總量、花費、呼叫次數、各 model 佔比。用量聚合目前是管理員專屬。本功能把用量透明化延伸到使用端：成員在自己的儀表板看到個人整體用量，且嚴格只看得到自己的資料。對應願景〈階段 9〉、原則「可追蹤性」的使用端透明化。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 儀表板整體用量摘要 (Priority: P1)

成員登入後，在儀表板一眼看到「我這段期間總共用了多少」——總 token、估算花費、呼叫次數，不必逐張分配點進去加總。

**Why this priority**: 這是成員最常問的問題（我用了多少、花了多少），也是用量透明化的最小有感增量；沒有它，成員對自身消耗毫無整體概念。

**Independent Test**: 以一個有數筆呼叫紀錄的成員登入，確認儀表板顯示的總 token / 花費 / 次數等於其所有分配呼叫的加總；無呼叫的成員顯示為 0。

**Acceptance Scenarios**:

1. **Given** 成員有跨 2 張分配、共 N 筆成功呼叫，**When** 開啟儀表板，**Then** 摘要顯示的總 token、估算花費、呼叫次數等於這些呼叫的加總。
2. **Given** 成員本期間沒有任何呼叫，**When** 開啟儀表板，**Then** 摘要顯示 0 token / 0 花費 / 0 次，不報錯。
3. **Given** 成員的某些呼叫對應的 model 在呼叫當時沒有價目，**When** 看摘要，**Then** 花費不把這些誤算成 0 而無提示——明確標示「含未定價項目，花費為低估」。

---

### User Story 2 - 用量明細與拆分 (Priority: P2)

成員想知道「錢花在哪、哪個 model 用最多」，能把整體用量按 model（與按自己的分配）拆分檢視，並選擇時間區間。

**Why this priority**: 在 P1 的「總數」之上提供「分布」，回答成本歸因問題；但沒有它成員仍有整體概念，故次於 P1。

**Independent Test**: 以有跨多個 model 呼叫的成員，請求按 model 拆分，確認各列加總等於總數，且排序合理；切換時間區間時數字隨之改變。

**Acceptance Scenarios**:

1. **Given** 成員在多個 model 上有呼叫，**When** 檢視按 model 拆分，**Then** 每個 model 一列（token / 花費 / 次數），各列加總等於整體摘要。
2. **Given** 成員選擇「本月」與「近 7 天」兩種區間，**When** 切換，**Then** 顯示的數字依所選區間重新計算。
3. **Given** 成員想看每張分配的消耗，**When** 按分配拆分，**Then** 每張分配一列，且只含該成員自己的分配。

---

### User Story 3 - 配額視角 (Priority: P3)

成員在用量旁邊看到「本月已用 / 配額」，知道自己離上限還有多遠（含自適應配額池動態調整後的當期配額）。

**Why this priority**: 把「用了多少」與「還能用多少」連起來，但屬加值；P1/P2 已交付核心透明化。

**Independent Test**: 以一張有月配額的分配，產生用量後檢視，確認顯示「本月已用 / 配額」且比例正確；無限額分配顯示為無上限。

**Acceptance Scenarios**:

1. **Given** 成員某分配本月配額 50000、已用 12000，**When** 檢視，**Then** 顯示已用 12000 / 50000（含視覺比例）。
2. **Given** 成員某分配為無限額，**When** 檢視，**Then** 顯示為無上限，不顯示比例條。

---

### Edge Cases

- **資料隔離（最關鍵）**：成員 A 不得透過任何方式（含改參數、猜 ID）看到成員 B 的用量；範圍永遠由登入者身份決定，不由請求參數決定。
- **未定價呼叫**：呼叫當時 model 無價目 → 該筆花費為 0；摘要須標示「含未定價項目」，不可讓成員誤以為真的免費。
- **失敗呼叫**：用量統計只計成功呼叫（與管理員口徑一致），失敗呼叫不計入 token/花費。
- **時間區間邊界**：跨月、時區（一律 UTC 月初錨點）邊界數字正確。
- **大量呼叫**：成員有大量歷史呼叫時，摘要與拆分仍可即時回應（聚合於資料層完成，不逐筆拉回）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 讓登入成員看到自己跨所有分配的用量彙總：總 token（prompt / completion / total）、估算花費、成功呼叫次數。
- **FR-002**: 系統 MUST 將成員用量查詢嚴格限定於登入成員本人；範圍由登入身份決定，**不接受**以請求參數指定他人。
- **FR-003**: 系統 MUST 支援將成員自己的用量按 model 與按自己的分配拆分檢視。
- **FR-004**: 系統 MUST 支援選擇時間區間（至少「本月」與「近 N 天」），數字依區間重算；月度以 UTC 月初為錨點。
- **FR-005**: 花費 MUST 採用呼叫當時記錄的成本（point-in-time），與管理員計費同一口徑；用量統計只計成功呼叫。
- **FR-006**: 當彙總包含「呼叫當時無價目」的呼叫時，系統 MUST 明確標示花費為低估（含未定價項目），不得讓成員誤判為免費。
- **FR-007**: 系統 SHOULD 讓成員看到自己各分配的「本月已用 / 配額」（含自適應配額池調整後的當期配額）；無限額分配顯示為無上限。
- **FR-008**: 既有管理員用量檢視與既有成員分配明細 MUST 不受影響（行為與權限零退化）。

### Key Entities *(include if feature involves data)*

- **用量彙總 (Usage Summary)**：對某成員、某時間區間的衍生聚合——總 token、估算花費、呼叫次數；可再按 model 或分配維度分組。非新資料表，由既有呼叫紀錄與分配資料聚合而來。
- **成員 (Member)**：用量的歸屬主體；查詢範圍即此登入成員。
- **分配 (Allocation)**：成員與 model 的綁定；用量經分配歸屬到成員，配額也掛在分配上。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員在儀表板能於一個畫面看到自身整體用量（總 token、估算花費、呼叫次數），不需點進任何單張分配。
- **SC-002**: 成員看到的整體數字與其所有分配呼叫的實際加總一致（按 model / 分配拆分各列加總 = 整體）。
- **SC-003**: 100% 的資料隔離——任何成員都無法取得他人的用量資料（以測試證明 A 無法讀 B）。
- **SC-004**: 花費口徑與管理員一致（同一筆呼叫，成員看到的估算花費 = 管理員端計算值）；含未定價呼叫時有明確低估提示。
- **SC-005**: 既有測試全數通過，管理員用量與成員分配明細零退化。

## Assumptions

- 沿用既有「呼叫紀錄逐筆存 point-in-time 成本」的資料；成員花費直接由這些成本加總，不重新計價（歷史天然正確）。
- 用量聚合**複用既有管理員聚合邏輯**，僅新增「限定登入成員」的範圍，不另寫一套平行聚合（避免兩份 drift）。
- 時間區間預設為「本月」（UTC 月初錨點）；「近 N 天」的 N 取常見值（如 7 / 30），確切選項於設計階段定。
- 只計成功呼叫，與管理員用量口徑一致。
- 不在本功能範圍：跨成員比較／排行、CSV/JSON 匯出、預算告警／超額通知、即時 streaming 用量（皆願景〈階段 9〉已排除，留後續）。
