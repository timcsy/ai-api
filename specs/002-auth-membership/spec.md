# Feature Specification: 階段 2 — 身份驗證與成員管理 (Auth & Membership)

**Feature Branch**: `002-auth-membership`
**Created**: 2026-05-22
**Status**: Draft
**Input**: User description: "階段 2 身份驗證與成員管理（Google OIDC + Local password）"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 組織成員以 Google Workspace 登入 (Priority: P1)

組織內擁有公司 Google Workspace 帳號的成員，使用「以 Google 登入」一鍵即可
進入平台。系統驗證該 email 在 admin 設定的白名單／自動註冊規則內，建立或
找到對應 Member、發 session cookie，使用者即可看見自己擁有的分配與用量。

**Why this priority**：這是組織內部「不要寫程式的成員也能進來」最低摩擦
的進場路徑，也是 vision 階段 2 的首要承諾。

**Independent Test**：使用組織內信箱跑完 Google OAuth flow → 回到平台時持有
有效 cookie → GET `/me` 可拿到 Member 與 active allocations 清單。

**Acceptance Scenarios**:

1. **Given** 該 email 已在白名單內 (或符合自動註冊規則)，**When** 使用者完成
   Google OAuth 並被導回平台，**Then** 系統建立 (或復用) Member、發出 session
   cookie、導向使用者首頁端點。
2. **Given** 該 email **不在**白名單也不符合任何規則，**When** Google OAuth
   完成後系統檢查身分，**Then** 拒絕登入並回覆「未授權使用本平台，請聯繫
   管理員」的結構化錯誤；過程不外洩「某 email 是否已註冊」。
3. **Given** Google IDP 簽章驗證失敗或 token 過期，**When** 回拋至 callback
   端點，**Then** 回 401 並記錄審計事件（不包含 OAuth secret）。

---

### User Story 2 - 沒有 Google 帳號的成員以 email + 密碼登入 (Priority: P1)

不是所有成員都有 Google Workspace 帳號（合作夥伴、外部協作者、無 IDP 整合
的子部門）。管理員可為這些人手動建立 Local Member 並透過邀請連結首次設密
碼；之後使用者用 email + 密碼登入。

**Why this priority**：呼應 vision「彈性身份驗證」與根公理（資源分配的對象
不應被身份來源限制）。和 US1 同列為 MVP — 缺一即排除掉一群目標使用者。

**Independent Test**：管理員建立 Local Member 並取得邀請連結 → 使用者開連
結設密碼 → 之後可以用 email + 密碼登入並取得 session。

**Acceptance Scenarios**:

1. **Given** 管理員以 email `bob@partner.com` 建立 Local Member，**When** 系統
   發行單次有效、48 小時內過期的邀請連結，**Then** 使用者可開連結並設定
   密碼，密碼存為不可逆雜湊。
2. **Given** Member 已設密碼，**When** 使用正確 email + 密碼登入，**Then**
   發出 session cookie。
3. **Given** Member 已設密碼，**When** 密碼錯誤，**Then** 回 401 並寫入失敗
   審計（含嘗試的 email 與來源 IP，**不含密碼字串**）；不可洩漏「email
   存在但密碼錯」 vs 「email 不存在」之差別。
4. **Given** 同一 email 在 60 秒內連續 5 次密碼錯誤，**When** 第 6 次嘗試，
   **Then** 拒絕並回 429，鎖定 15 分鐘；鎖定期內成功密碼也不允許登入。

---

### User Story 3 - 管理員管控誰能進來 (Priority: P1)

擁有者必須能控制哪些人有資格使用本平台：直接加 email 白名單、設定自動註冊
規則（例：`@example.com` 網域）、限制登入來源 IP/CIDR。

**Why this priority**：呼應 vision「組織內部脈絡」與原則 2（可追蹤性）—
組織必須能說「為什麼這個人能進來」。

**Independent Test**：管理員以 API 加白名單 / 規則 / 來源限制 → 立刻生效
（無需重啟服務）→ 新登入流程被新規則影響。

**Acceptance Scenarios**:

1. **Given** 管理員加 `alice@x.com` 至白名單，**When** Alice 嘗試 Google
   SSO，**Then** 允許註冊／登入。
2. **Given** 管理員設定自動註冊規則「email 網域為 `@example.com`」，
   **When** `new@example.com` 第一次 SSO，**Then** 自動建立 Member、允許登入。
3. **Given** 管理員設定登入來源限制為 `10.0.0.0/8`，**When** 從 IP
   `192.168.1.1` 嘗試登入，**Then** **不發起** OAuth flow，直接回 401
   並結構化錯誤碼 `source_not_allowed`。
4. **Given** 管理員移除某 email 的白名單條目，**When** 該使用者下次嘗試
   登入，**Then** 拒絕並回 401；已存在的 session 不受影響（撤銷 session
   為另外操作）。

---

### User Story 4 - 一般成員看自己的分配與用量 (Priority: P2)

登入後的成員應該能看到「我有哪些分配、最近用了多少、token 是什麼」。

**Why this priority**：閉環體驗。讓使用者不需要打擾管理員就能拿到自己的
憑證與用量；但功能本身不阻擋核心 SSO 與管控，故為 P2。

**Independent Test**：以登入後的 cookie 呼叫 `/me/allocations` → 回傳自己
所有 active 分配（不顯示其他人的）；呼叫 `/me/allocations/{id}/calls`
→ 回傳該分配的呼叫紀錄。

**Acceptance Scenarios**:

1. **Given** 已登入的 Member，**When** GET `/me/allocations`，**Then** 回傳
   屬於該 Member 的分配清單（token 明文僅在原本建立時回傳一次，此端點
   只回 token_prefix）。
2. **Given** 已登入的 Member，**When** 嘗試查詢別人分配的呼叫紀錄，**Then**
   回 403 — 一般成員不能跨人查詢。

---

### User Story 5 - 將既有 subject 字串平滑遷移為 Member (Priority: P2)

階段 1 的 `Allocation.subject` 是任意字串（例：`alice@example.com`、
`smoke@test`、暱稱）。階段 2 升格為 `Member` FK，必須處理既有資料而不
中斷既有授權。

**Why this priority**：避免「升級即破壞」。既有分配持有人不需重新申請、
持有的 token 持續有效。

**Independent Test**：對既有資料庫執行 migration → 所有舊分配的 subject
皆對應到一個 Member（可能是 placeholder / external service 型）→ 既有 token
呼叫成功率不變。

**Acceptance Scenarios**:

1. **Given** 階段 1 的舊分配 `subject="alice@example.com"`，**When** migration
   執行，**Then** 自動建立或對應到 email 為該值的 Member（type=`external`，
   無 provider，無法登入），分配的 FK 指向此 Member。
2. **Given** 階段 1 的舊分配 `subject="smoke@test"`（非合法 email 格式），
   **When** migration 執行，**Then** 建立 Member type=`external`、
   `external_id="smoke@test"`，分配 FK 指向此 Member。
3. **Given** migration 完成，**When** 持舊 token 呼叫 `/v1/chat/completions`，
   **Then** 與 migration 前完全相同的行為（成功 / 拒絕 / 計帳）。

---

### Edge Cases

- 同一 email 嘗試先 Google 註冊再 Local 註冊：第二次拒絕（一個 email 綁一
  個 provider）。
- 邀請連結被開啟兩次：第二次拒絕；連結作廢。
- 邀請連結過期後使用：拒絕並提示請聯繫管理員重發。
- 一般成員的 session 過期：API 回 401，前端應引導重新登入（前端不在範圍）。
- 管理員撤回某 Member 期間，該 Member 已有的 active session 應立即失效
  （呼應原則 3 即時撤回的精神）。
- Google OIDC 回傳的 email 與我們白名單 email 大小寫不同：以小寫比對。
- 自動註冊規則同時有多條時生效行為：先到先生效（OR 邏輯），第一條 match
  即成立。

## Requirements *(mandatory)*

### Functional Requirements

#### 認證抽象與多 Provider
- **FR-001**: 系統 MUST 提供 `AuthProvider` 抽象介面，至少實作兩個 provider：
  `google_oidc` 與 `local_password`。新增其他 provider（OIDC/SAML）僅需新增
  實作類別，不需修改認證流程的核心邏輯。
- **FR-002**: 同一 Member 僅綁定一個 provider；建立後不可切換。
- **FR-003**: 同一 email 在整個系統中至多存在一個 Member（不允許 Google
  與 Local 同 email 並存）。

#### Google OIDC
- **FR-004**: 系統 MUST 支援 Google Workspace OIDC（Authorization Code +
  PKCE）登入流程；callback 需驗證 `state`、`nonce`、ID token 簽章與 audience。
- **FR-005**: Google OIDC 登入時依序檢查：來源限制 → 白名單 → 自動註冊
  規則；通過則建立或復用 Member、發 session。

#### Local Password
- **FR-006**: 系統 MUST 以 **Argon2id**（或同等抗 GPU 雜湊）儲存密碼；密碼
  明文不得寫入 DB、log、回應、錯誤訊息。
- **FR-007**: 管理員建立 Local Member 時 MUST 可選「直接設初始密碼」或
  「發邀請連結」；邀請連結為單次有效、48 小時 expiry。
- **FR-008**: 密碼複雜度政策：最低 10 字元；不在常見密碼黑名單。
- **FR-009**: 登入端點 MUST 對同 email 套用 rate limit（5 次/分鐘超過即
  鎖 15 分鐘）；rate limit 訊息**不洩漏**該 email 是否存在。
- **FR-010**: 失敗登入錯誤訊息對「email 不存在」與「密碼錯誤」必須**統一**，
  避免 user enumeration。
- **FR-011**: 已登入使用者 MUST 可自行修改密碼（須驗舊密碼）。

#### 管理員管控
- **FR-012**: 管理員 API MUST 提供：email 白名單 CRUD、自動註冊規則 CRUD、
  來源 IP/CIDR 限制 CRUD；變更立即生效（不需重啟服務）。
- **FR-013**: 來源限制 MUST 在 OAuth flow 啟動前即生效——禁止 IP 連 SSO
  callback 都觸發不到。
- **FR-014**: 管理員 MUST 可建立、停用 (disable)、刪除 Member；停用後
  Member 的 active sessions 立即失效，已發行的分配 token 不受影響（撤銷
  分配是另一動作）。

#### Session
- **FR-015**: 系統 MUST 以 server-side session 表 + HTTP-only / Secure /
  SameSite cookie 管理已登入狀態（**非 stateless JWT**），以滿足「即時
  撤銷」需求。
- **FR-016**: Session 預設 expiry 24 小時、idle timeout 2 小時；登出端點
  必須讓 cookie 與 server 端 session record 同時失效。
- **FR-017**: 所有 session 紀錄 MUST 含 Member ID、建立時間、最後活動
  時間、來源 IP、user-agent，並可由管理員查詢與強制撤銷。

#### 一般成員端點
- **FR-018**: 已登入 Member MUST 可呼叫 `/me`、`/me/allocations`、
  `/me/allocations/{id}/calls`，僅看到屬於自己的資料。
- **FR-019**: 跨 Member 查詢 MUST 回 403；不揭露其他 Member 是否存在。

#### 既有資料遷移
- **FR-020**: 啟動本階段 migration 時 MUST 為每個獨特的 `Allocation.subject`
  字串建立或對應到一個 type=`external` 的 Member（無 provider、無法登入）。
- **FR-021**: Migration 完成後，所有既有 `Allocation` MUST 有有效的
  `member_id` FK；舊 token 的呼叫行為不變。

#### 審計與可觀測性
- **FR-022**: 認證相關事件（成功登入、失敗登入、白名單變更、規則變更、
  Member 停用）MUST 寫入結構化稽核紀錄，含 actor、target、來源 IP、時間。
- **FR-023**: 密碼、OAuth client secret、ID token、session token MUST 經
  redaction filter，不得出現在任何 log 或對外回應中。

#### 不在本階段範圍
- **FR-024** (NON-GOAL): 不實作完整管理員 Web UI（vision 階段 3 範圍）；
  本階段交付後端 + admin API + 必要的 OAuth callback HTML 即可。
- **FR-025** (NON-GOAL): 不實作「忘記密碼」email 重設流程（需 SMTP infra；
  延後到後續小階段）。
- **FR-026** (NON-GOAL): 不實作 MFA、裝置綁定、SAML、account linking。

### Key Entities

- **Member**（新表）：實體使用者或外部服務。
  - 屬性：`id` (ULID)、`email` (UNIQUE, lowercased)、`provider`
    (`google_oidc` / `local_password` / `external`)、`external_id`
    (provider 內部 ID，例：Google sub)、`display_name`、`status`
    (`active` / `disabled`)、`password_hash` (僅 local 有)、`created_at`、
    `disabled_at`、`created_by`。
  - 關係：1 Member ↔ N Allocation；1 Member ↔ N Session。

- **Session**（新表）：登入狀態。
  - 屬性：`id` (隨機字串作為 cookie 值的 fingerprint)、`member_id` FK、
    `created_at`、`last_seen_at`、`expires_at`、`source_ip`、`user_agent`、
    `status` (`active` / `revoked`)。

- **EmailWhitelist**（新表）：管理員手動加入的 email。
  - 屬性：`email` (lowercased, PK)、`added_at`、`added_by`、`note`。

- **AutoRegisterRule**（新表）：自動註冊規則。
  - 屬性：`id`、`rule_type`（首階段僅支援 `email_domain`）、`pattern`（例：
    `example.com`）、`enabled`、`created_at`、`created_by`。

- **SourceRestriction**（新表）：允許登入的來源 IP/CIDR。
  - 屬性：`id`、`cidr`、`enabled`、`created_at`、`created_by`、`note`。
  - 預設行為：若**無**任何啟用的 restriction，允許所有來源。

- **InvitationToken**（新表）：Local Member 首次設密碼用。
  - 屬性：`token_fingerprint` (PK)、`member_id` FK、`created_at`、
    `expires_at`、`used_at` (nullable，使用後變非 null)。

- **PasswordAttempt**（新表，rate limit 用）：登入失敗計數。
  - 屬性：`email` (lowercased)、`attempted_at`、`source_ip`、`outcome`。
  - 查詢「最近 60 秒內同 email 失敗次數」即可決定是否鎖定。

- **Allocation**（升級）：階段 1 的 `subject` 字串改為 `member_id` FK，
  並保留 `subject_snapshot` 字串欄位供稽核（避免 Member rename 抹去歷史）。

- **CallRecord**（不變）：`subject` 欄位仍存為 snapshot 字串；同上理由。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 組織內有 Google Workspace 帳號的使用者，**完整 SSO 登入**從
  點擊「Google 登入」到看見自己的分配清單，全程 ≤ 30 秒。
- **SC-002**: Local Member 從管理員建立到使用者完成首次設密碼並登入成功，
  全程 ≤ 5 分鐘（含人類在邀請連結頁面輸入密碼的時間）。
- **SC-003**: 對 100 次抽樣的失敗登入回應與審計紀錄做掃描，**0** 次出現
  密碼、OAuth secret、session token 明文。
- **SC-004**: 對於不存在的 email 與密碼錯誤兩種情境，回應內容（含時間、
  狀態碼、訊息）的可區分性 ≤ 統計顯著（reviewer 人工檢視 50 對樣本）。
- **SC-005**: 對同 email 連續 6 次失敗，第 6 次回 429；該 email 在鎖定
  15 分鐘內即使正確密碼也無法登入。
- **SC-006**: 管理員停用 Member 後，該 Member 的所有 active session 在
  ≤ 5 秒 內失效（呼應原則 3 SLO）。
- **SC-007**: 階段 1 既有資料 migration 後，舊 token 的呼叫成功／拒絕
  比例與 migration 前差異為 0%。
- **SC-008**: 至少 1 個非 Google OIDC 的第二 provider 實作（Local）通過
  完整契約測試；認證核心邏輯對 provider 數量無關（新增第三個 provider
  不需修改 service 層測試）。
- **SC-009**: 所有 FR 在 git 歷史中可見「測試 commit 早於對應實作 commit」
  （延續 SC-008 of 階段 1 的 TDD 紀律）。

## Assumptions

- **不做 UI**：本階段交付認證後端 + admin API + 必要的 OAuth callback HTML
  與邀請連結頁面（純表單），完整管理員 Web UI 延後至階段 3。
- **Session 形式為 server-side + cookie**：相較 stateless JWT，可支援
  「停用 Member 即時失效所有 session」（呼應原則 3）；scale 成本以 DB
  讀寫換取。
- **既有 Allocation.subject 一律對應到 type=`external` Member**：保守起見
  不嘗試把字串「猜」成 Google 帳號；管理員可手動 link。
- **rate limit 採同 email 維度**：簡單可審計；分散式環境下準確性可能 ±1
  次，可接受。
- **OAuth client 設定**：將在 plan 階段列出 Google Cloud Console 需設定的
  欄位清單（client_id、authorized redirect URIs for local/dev/prod 三組）。
- **邀請連結 token 形式**：隨機 32 byte，URL-safe base64；DB 僅存 SHA-256
  指紋；使用 SecretStr 等同對待密碼。
- **「停用 Member 立即失效 session」5 秒 SLO**：每次請求驗證 session
  時順帶查詢 `Member.status`，與階段 1「即時撤回 SLO 5s」同策略，不引入
  pub/sub。
