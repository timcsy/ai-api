# Feature Specification: Scoped application credentials（憑證綁一組分配，M:N）

**Feature Branch**: `030-scoped-app-credentials`
**Created**: 2026-06-05
**Status**: Draft
**Input**: 階段 20 — 把憑證從「綁一筆分配」升級為「**成員建立、可命名的應用 key，指定它能用哪一組分配（model）**」；一把 key 跨多 model、呼叫依 request 的 model 歸戶到對應分配；admin 治理、成員在自己分配內自助打包；既有單分配 token 零回歸。

## 背景與問題

目前（階段 18）一把憑證綁**單一**分配 = 單一 model。但一個應用常要用多個 model：Codex 切 `/model`、agent 同時要 chat + embedding。在現行模型下，使用者得為每個 model 各建一把 token、各自貼設定；Codex 的 `auth.json` 只放一把 key，於是切到別的 model 就 403 `model_mismatch`。

把它收斂回**業界主流的「scoped application credential」**（GitHub fine-grained PAT 選一組 repo、cloud service account 被授予一組資源、Azure APIM subscription→product、OAuth scopes）：**一把可命名的應用 key，指定它能用哪一組分配；每次呼叫依 model 歸戶到對應分配（per-call metered to the matching allocation）**。額度/歸戶仍綁在**分配**層（原則 1，措辭一般化為 N:M）；key 的 scope 只能含**擁有者已被授予**的分配（capability 的 attenuation，不提權）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 一把應用 key 用多個 model（Priority: P1）🎯 MVP

成員建立一把具名的應用 key（如「我的筆電 Codex」），勾選它可用的**多筆分配**（多個 model），取得一次性明文 token。之後該 token 可呼叫 scope 內的**任一個 model**，不必每個 model 各一把。

**Why this priority**: 這是整個重構的核心價值——「一個應用一把 key、跨多 model」；其餘都圍繞它。

**Independent Test**: 建一把 key 綁兩筆分配（model A、model B）→ 用該 token 分別打 A 與 B → 兩者皆成功。

**Acceptance Scenarios**:

1. **Given** 成員有 model A、B 兩筆 active 分配，**When** 建立一把 key 勾選 A+B，**Then** 回一次性明文 token（之後只存雜湊），該 token 打 A 與 B 皆成功。
2. **Given** 一把 key 的 scope，**When** 檢視清單，**Then** 看到 key 名稱、可用的 model（那組分配）、建立/最後使用時間、狀態，且**不含明文**。

---

### User Story 2 - 依 model 歸戶；scope 外的 model 被拒（Priority: P1）

用該 token 呼叫時，平台依 request 的 model 找到 scope 內對應的分配，**用量與額度記到那筆分配**；若 model 不在 scope 內，回清楚的拒絕（非 401/500）。

**Why this priority**: 沒有正確歸戶與邊界，多 model key 會破壞計費與配額隔離——是 P1 的正確性底線。

**Independent Test**: key 綁 A+B；打 A → A 的用量+1、額度從 A 扣；打**不在 scope 的 C** → 403 model_mismatch、不計費。

**Acceptance Scenarios**:

1. **Given** key 綁 A+B，**When** 用該 token 打 model A，**Then** 該次用量/花費記到分配 A、扣 A 的額度（不影響 B）。
2. **Given** key 綁 A+B，**When** 打不在 scope 的 model C，**Then** 回 403（model 不在此 key 的可用範圍），不計費、不扣任何分配。
3. **Given** 一把 key 不得綁兩筆相同 model 的分配，**When** 建立/編輯，**Then** 系統拒絕重複 model（避免歸戶歧義）。

---

### User Story 3 - 既有單分配 token 零回歸（Priority: P1）

模型重構（憑證 1:N → 應用 key M:N）後，**所有既有的單分配 token 仍可正常呼叫、歸戶不變**，使用者完全無感。

**Why this priority**: 線上已有大量單分配 token（含 Codex device-flow 發的）；任何回歸都是直接事故。最高優先固化。

**Independent Test**: migration 後，既有一把舊 token（綁單一分配）打它的 model → 成功、歸戶到原分配；打別的 model → 仍 403。

**Acceptance Scenarios**:

1. **Given** migration 前已存在的單分配 token，**When** migration 後用它呼叫原 model，**Then** 成功、用量歸原分配（與重構前一致）。
2. **Given** 既有 token，**When** 檢視，**Then** 它等同「scope 只含一筆分配的應用 key」，行為不變。

---

### User Story 4 - 調整應用 key 的可用分配 + 撤回/rotate（Priority: P2）

成員（對自己的）或 admin 可對既有 key **增加 / 移除可用分配**（即調整它能用哪些 model）、撤回整把、或就地 rotate token；變更留稽核。

**Why this priority**: key 的生命週期管理；非 MVP 阻斷，但缺了就無法演進一把既有 key（只能砍掉重建）。

**Independent Test**: 對一把綁 A 的 key 加上 B → 該 token 立刻也能打 B；移除 A → 立刻不能打 A、仍能打 B；撤回整把 → 全失效。

**Acceptance Scenarios**:

1. **Given** 一把綁 A 的 key，**When** 加入分配 B，**Then** 同一 token 立即可打 B（不需換 token）。
2. **Given** 一把綁 A+B 的 key，**When** 移除 A，**Then** 該 token 立即不能打 A、仍能打 B；變更留稽核。
3. **Given** 一把 key，**When** 撤回，**Then** 其**所有** model 立即失效，**其他 key 不受影響**。

---

### User Story 5 - admin 治理；成員自助只限自己的分配（Priority: P2）

admin 可檢視/管理**任一成員**的應用 key 與其 scope；成員自助時，只能把**自己已被授予的分配**放進 key（不得綁他人分配、不創造新權限）。

**Why this priority**: 守住治理邊界與不提權（原則 5 + capability attenuation）；是安全正確性，但建在 US1 的 CRUD 之上。

**Independent Test**: 成員嘗試把**他人**的分配加進自己的 key → 拒絕；admin 對某成員的 key 增刪 scope → 成功且留稽核。

**Acceptance Scenarios**:

1. **Given** 成員 X，**When** 試圖把成員 Y 的分配放進自己的 key，**Then** 被拒（403），不得綁定。
2. **Given** admin，**When** 檢視/調整任一成員的 key scope 或撤回，**Then** 成功、留稽核（誰、何時、動了哪把 key 的哪筆分配）。

---

### User Story 6 - Codex 一次安裝勾選多 model；單一 Codex 說明（Priority: P2）

Codex 的瀏覽器授權（device-flow，階段 19）改為**勾選多筆分配**，建立的應用 key 即涵蓋那些 model → 裝一次、Codex 內 `/model` 跨那些 model 不再 403。同時**移除舊「如何呼叫」裡過時且矛盾的 Codex 分頁**，全站只剩一處 Codex 安裝說明。

**Why this priority**: 把階段 19 接到新模型、並收掉「兩套 Codex 說明」的混亂（收尾 A）。依賴 US1 的 M:N。

**Independent Test**: 跑 Codex device-flow → 勾選 A+B → 裝完在 Codex 內切 A、B 皆通；dashboard 只有一處 Codex 安裝入口。

**Acceptance Scenarios**:

1. **Given** Codex device-flow 授權頁，**When** 成員勾選多筆分配核可，**Then** mint 一把涵蓋那些 model 的應用 key，Codex 安裝後 `/model` 跨那些 model 不 403。
2. **Given** 全站，**When** 找 Codex 安裝說明，**Then** 只有一處（一行指令卡），舊的手動 config.toml Codex 分頁已移除。

---

### Edge Cases

- **空 scope**：建立 key 至少要勾一筆分配；移除到 0 筆 → 拒絕（或等同撤回，需明確）。
- **scope 內某分配被停用/撤銷/暫停**：該 model 暫時不可用、其餘照常；分配恢復後又可用（歸戶仍到該分配）。
- **同 model 兩分配**：建立/編輯時拒絕（歸戶歧義）。
- **request 沒帶 model 或帶未知 model**：回清楚訊息（非 500）。
- **rotate**：換 token、scope 不變、舊 token 立即失效。
- **device-flow 勾選後某分配被 admin 撤掉**：mint 時或呼叫時依當下 scope 判定。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 憑證 MUST 為**成員擁有、可命名**的應用 key，其 **scope = 一組分配（≥1）**；一把 token 對應一個 scope。
- **FR-002**: 呼叫驗證 MUST 依 request 的 model 在該 token 的 scope 內找到對應分配；**用量/額度/歸戶記到那筆分配**（不變的分配層計費）。
- **FR-003**: 同一把 key 的 scope 內，分配的 model **MUST 唯一**（不得重複），以避免歸戶歧義。
- **FR-004**: request 的 model **不在** scope 內 MUST 被拒（model 不在可用範圍），且**不計費、不扣額度**。
- **FR-005**: key 的 scope **MUST 只能含擁有者已被授予的分配**（attenuation）；不得綁他人分配、不創造新權限。
- **FR-006**: 系統 MUST 提供應用 key 管理：建立（命名 + 勾選分配，回明文一次）、列出（不含明文）、撤回、rotate、**增刪 scope 內分配**；清單呈現在**成員層**（一 key = 一組 model）。
- **FR-007**: **admin** MUST 能檢視/管理任一成員的應用 key 與 scope；**成員自助** MUST 限於自己的分配。
- **FR-008**: scope 變更（增/刪分配）、撤回 MUST 留稽核（誰、何時、哪把 key、哪筆分配）。
- **FR-009**: **既有單分配 token MUST 零回歸**——migration 後仍解析、呼叫、歸戶與重構前一致（等同 scope 只含一筆分配的 key）。
- **FR-010**: 額度、用量、可追蹤性 MUST 仍綁在**分配**層（不把額度移到 token；token 數不繞過配額/異常偵測）。
- **FR-011**: token 仍 **show-once + 只存雜湊**；撤一把 key 不影響其他 key（不連坐）。
- **FR-012**: Codex device-flow（階段 19）授權 MUST 支援**勾選多筆分配**建立應用 key；**舊「如何呼叫」的 Codex 設定分頁 MUST 移除**，Codex 安裝說明全站單一來源。

### Key Entities *(include if feature involves data)*

- **應用憑證（Application Credential）**：成員擁有、具名的 key。屬性：id、擁有成員、名稱、token 雜湊/前綴、建立/最後使用/撤回時間。**scope = 一組分配**（M:N）。
- **憑證-分配 範圍（Credential–Allocation scope）**：多對多關係（哪把 key 能用哪些分配）。約束：同一 key 內分配 model 不重複。
- **分配（Allocation）**：不變（成員→model + 額度）；計費/歸戶單位。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 一把應用 key 能呼叫 scope 內 **≥2 個 model**，每次呼叫各自**歸戶/扣對應分配的額度**（100% 正確、互不影響）。
- **SC-002**: request 的 model 不在 scope → **被拒（model_mismatch）且 0 計費**。
- **SC-003**: 撤回某把 key → 其**所有** model 立即失效；其他 key **100% 不受影響**。
- **SC-004**: migration 後**既有單分配 token 100% 可用**、歸戶不變（零回歸）。
- **SC-005**: 對既有 key 增/刪分配後，**該 token 立即**可用/不可用對應 model（無需換 token）；變更皆留稽核。
- **SC-006**: 成員**無法**把他人分配放進自己的 key（0 例外）；admin 可管理任一成員的 key。
- **SC-007**: Codex 一次安裝（勾多分配）後，Codex 內 `/model` 跨 scope 的 model **不再 403**；全站 Codex 安裝說明僅一處。

## Assumptions

- **分配仍 = 一個 model**、**額度仍 per-allocation**；本階段只改「憑證 ↔ 分配」的基數（1:N → M:N），不動分配本身語意。
- **歸戶以 (token, request model) 唯一決定分配**——靠 FR-003 的「key 內 model 不重複」保證。
- **治理**：admin 是權威（決定成員有哪些分配 = model 可用性，且能管理任一成員的 key）；成員自助打包僅限自己已被授予的分配（無提權，capability attenuation）。沿用既有 session + 擁有者把關 + admin token。
- **不為 Codex 特別過濾**：device-flow 勾選清單就列出可選分配，不依 model 能力分類（能不能用由「有沒有那筆分配」決定，分配由 admin 授予）。
- **重構而非新功能**：沿用 show-once + hash-only、per-allocation 計費、device-flow（階段 19）。
- **資料模型變更需 migration**（憑證表去掉單一 `allocation_id`、加 `member_id` + 憑證-分配 join 表，既有列搬成 scope 一列）；**migration 必在 Postgres 整合測試驗**（經驗鐵則），且新增關係**無循環 FK**。
- **平台/部署**沿用既有（FastAPI + SQLAlchemy async + Alembic；React/Vite；K8s/Helm）。
- **不做**：跨成員共用 token；把額度移到 token 層；改 Codex 上游協定；空 scope 的 key。
