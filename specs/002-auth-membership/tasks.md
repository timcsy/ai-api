# Tasks: 階段 2 — 身份驗證與成員管理 (Auth & Membership)

**Input**: Design documents from `/specs/002-auth-membership/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: TDD enforced（constitution Principle I + spec SC-009）— 所有測試
任務必須在對應實作任務之前完成並失敗，再進入實作令其通過。

**Organization**: 按 spec.md User Story 與優先序組織。

## Format

`- [ ] T### [P?] [Story?] description with file path`

- 路徑均相對 repo root：`<repo-root>`

---

## Phase 1: Setup

**Purpose**：相依套件、設定範本、CI 對 Phase 2 的擴充。

- [ ] T001 在 `pyproject.toml` 新增依賴：`authlib>=1.3.0`、`argon2-cffi>=23.1.0`、`itsdangerous>=2.2.0`、`email-validator>=2.2.0`；dev 加 `respx>=0.21.0`（已在 Phase 1 dev 中可確認）
- [ ] T002 [P] 更新 `.env.example`：加入 `BASE_URL`、`COOKIE_SECURE`、`GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET`、`GOOGLE_DISCOVERY_URL`、`COOKIE_DOMAIN`（可選）
- [ ] T003 [P] 更新 `src/ai_api/config.py`：Settings 新增上述欄位（Pydantic `Field` + alias）

---

## Phase 2: Foundational (Blocking)

**Purpose**：所有 User Story 共用的基礎建設。

### Models（每個檔案獨立，可並行）

- [ ] T004 [P] 建立 Member ORM 模型於 `src/ai_api/models/member.py`（依 data-model.md，含 provider/status enum、`lower(email)` UNIQUE 索引）
- [ ] T005 [P] 建立 Session ORM 模型於 `src/ai_api/models/session.py`
- [ ] T006 [P] 建立 EmailWhitelist / AutoRegisterRule / SourceRestriction ORM 模型於 `src/ai_api/models/access_control.py`
- [ ] T007 [P] 建立 InvitationToken ORM 模型於 `src/ai_api/models/invitation.py`
- [ ] T008 [P] 建立 PasswordAttempt ORM 模型於 `src/ai_api/models/password_attempt.py`
- [ ] T009 [P] 建立 AuthAuditLog ORM 模型於 `src/ai_api/models/auth_audit.py`
- [ ] T010 [P] 建立 OidcState（短期）ORM 模型於 `src/ai_api/models/oidc_state.py`
- [ ] T011 在 `src/ai_api/models/__init__.py` re-export 所有新模型；確保 `from ai_api import models` 能註冊所有表

### Allocation 升級

- [ ] T012 [US5] 修改 `src/ai_api/models/allocation.py`：新增 `member_id` (FK NOT NULL with RESTRICT) + `subject_snapshot`；DROP `subject`（在 migration 中處理）
- [ ] T013 [US5] 建立 Alembic migration `alembic/versions/0002_auth_membership.py`：
   1. 建所有新表（T004–T010）
   2. 在 `allocations` 加 `member_id` (nullable) + `subject_snapshot`
   3. **Data migration**：DISTINCT subject → 建立 type=`external` Member → UPDATE allocations
   4. 加 `NOT NULL` 約束於 `member_id`
   5. DROP `allocations.subject`
- [ ] T014 [P] [US5] 撰寫整合測試 `tests/integration/test_us5_subject_migration.py`：
   - 種入若干 Phase 1 格式的 Allocation+Credential
   - 跑 migration
   - 驗證 Member 存在、allocation.member_id 已綁定、Phase 1 token 仍可呼叫 `/v1/chat/completions`

### Auth 核心抽象

- [ ] T015 [P] 建立 `AuthProvider` 抽象介面 + `AuthResult` / `AuthError` dataclass 於 `src/ai_api/auth/base.py`
- [ ] T016 [P] 建立 policy 評估服務（whitelist + auto-register rule + source restriction）於 `src/ai_api/auth/policy.py`
- [ ] T017 [P] 建立 Session 服務（cookie token 生成 + 指紋驗證 + 撤銷 + 觸發 `Member.disabled` → revoke）於 `src/ai_api/auth/sessions.py`
- [ ] T018 [P] 建立 auth audit 服務於 `src/ai_api/auth/audit.py`（含 redaction 包裝）

### 觀測 / 安全擴充

- [ ] T019 [P] 擴充 `src/ai_api/observability/logging.py` 的 `RedactionFilter`：加入「password 明文 pattern」、「OIDC client secret」、「cookie 值（session token）」的遮蔽
- [ ] T020 [P] 建立 CSRF dependency（double-submit cookie）於 `src/ai_api/api/deps.py`：`require_csrf`
- [ ] T021 [P] 建立 cookie session dependency 於 `src/ai_api/api/deps.py`：`current_member`（從 `aiapi_session` 解析 → Session → Member；無/失效則 401）
- [ ] T022 [P] 把 `require_admin_token` 升級為 `require_admin`：支援 X-Admin-Token **或** admin Member session（admin Member 暫定 by `Member.created_by='bootstrap-admin'` 或設定 admin flag — 留 plan 階段確認）

### Foundational 測試 harness 擴充

- [ ] T023 在 `tests/contract/conftest.py` 與 `tests/integration/conftest.py` 加入 `respx` fixture（mock Google OIDC discovery + token endpoint），並提供 `login_as(client, email)` helper（直接建立 session 跳過 OIDC flow）

**Checkpoint**：Phase 2 完成後，Phase 1 測試套件全部仍綠（基底沒打破），且
資料 migration 通過。

---

## Phase 3: US1 — Google SSO 登入 (P1)

**Goal**：組織信箱使用者可一鍵 SSO 登入並取得 session。
**Independent Test**：依 quickstart §2+§3 設管控後跑 Google OIDC flow，
拿到 cookie、能 GET `/me`。

### Tests for US1 (TDD red)

- [ ] T024 [P] [US1] 契約測試 `tests/contract/test_auth_oidc.py`：`GET /auth/oidc/start` 觸發 redirect、含 state；`GET /auth/oidc/callback` 設 cookie 並 302
- [ ] T025 [P] [US1] 整合測試 `tests/integration/test_us1_google_sso.py`：
   - whitelist 內 email → 通過
   - 不在 whitelist + 符合 rule → 通過
   - 都不符 → 401 + 不洩漏 enumeration
   - 來源不允許 → /auth/oidc/start 直接 401（OAuth flow 不啟動）

### Implementation for US1

- [ ] T026 [P] [US1] 實作 `GoogleOidcProvider` 於 `src/ai_api/auth/google_oidc.py`：authlib + PKCE；發出 authorize URL；驗 callback；回 `AuthResult`
- [ ] T027 [US1] 實作 `/auth/oidc/start` 與 `/auth/oidc/callback` 於 `src/ai_api/api/auth.py`：先 policy.evaluate(source/whitelist/rule) → provider.authenticate → 建立或復用 Member → Session.create → 設 cookie → 302 `next`
- [ ] T028 [US1] 註冊 auth router 於 `src/ai_api/main.py`，並在 lifespan 載入 OAuth discovery（authlib `OAuth.register`）

**Checkpoint**：MVP P1-A 達成 — 組織成員可 Google 登入。

---

## Phase 4: US2 — Local password 登入 (P1)

**Goal**：Local Member 經邀請設密碼後可 email+密碼登入。

### Tests for US2 (TDD red)

- [ ] T029 [P] [US2] 契約測試 `tests/contract/test_auth_local.py`：
   - `POST /auth/local/login` 200/401/429
   - `GET /auth/invitation/{token}` 200 HTML / 404
   - `POST /auth/invitation/{token}` 200 設密碼成功 / 400 違反政策 / 404 失效
   - `PUT /me/password` 204 / 400 / 403（OIDC member 不能改）
- [ ] T030 [P] [US2] 整合測試 `tests/integration/test_us2_local_password.py`：
   - 管理員建立 Local Member（send_invitation=true）→ 取得 url → POST 設密碼 → 自動登入
   - 直接設 initial_password → email+password 直接登入
   - 6 次密碼錯誤 → 第 6 次 429；鎖定 15 分鐘內正確密碼亦拒
   - 不存在的 email 與密碼錯誤回應「無法區分」（內容、status、訊息相同）
- [ ] T031 [P] [US2] 整合測試 `tests/integration/test_redaction_for_passwords.py`：
   登入失敗、設密碼、改密碼三路徑全程 grep request body 中的密碼明文於回應/log = 0

### Implementation for US2

- [ ] T032 [P] [US2] 實作 `LocalPasswordProvider` 於 `src/ai_api/auth/local.py`：argon2-cffi 雜湊／驗證、密碼複雜度政策（最低 10 字 + 黑名單）
- [ ] T033 [P] [US2] 實作 invitation 服務於 `src/ai_api/auth/invitations.py`：建立 token、SHA-256 指紋、48h expiry、單次有效
- [ ] T034 [P] [US2] 實作 ratelimit 服務於 `src/ai_api/auth/ratelimit.py`：寫入 PasswordAttempt、查詢 60s 內失敗次數、lock 邏輯
- [ ] T035 [US2] 實作 `/auth/local/login` 端點於 `src/ai_api/api/auth.py`：
   - source restriction 檢查
   - rate limit 預查
   - lookup_by_email → bad_password / unknown_email **都回統一 401 訊息**（避免 enumeration）
   - 成功則 Session.create + 設 cookie
- [ ] T036 [US2] 實作 `/auth/invitation/{token}` GET + POST 於 `src/ai_api/api/auth.py`（POST 設密碼 + 立即建立 session）
- [ ] T037 [US2] 實作 `/me/password` PUT 於 `src/ai_api/api/me.py`：驗舊密碼 → 換新密碼；OIDC/external Member 回 403
- [ ] T038 [US2] 實作 `/auth/logout` POST 於 `src/ai_api/api/auth.py`：revoke session 並清 cookie

**Checkpoint**：MVP P1-B 達成 — 沒 Google 帳號的人也能用。

---

## Phase 5: US3 — 管理員管控 (P1)

**Goal**：白名單 / 自動註冊規則 / 來源限制 / Member CRUD + session 撤銷。

### Tests for US3 (TDD red)

- [ ] T039 [P] [US3] 契約測試 `tests/contract/test_admin_access.py`：
   - whitelist CRUD（含未授權 401）
   - rule CRUD
   - source restriction CRUD
- [ ] T040 [P] [US3] 契約測試 `tests/contract/test_admin_members.py`：
   - create / list / get / patch / delete Member
   - 帶 `provider=local_password` + `send_invitation=true` 回 `invitation_url`
   - email 已存在 → 409
   - delete 仍有未撤回分配 → 409
   - 列出/撤銷 Member 的 session
- [ ] T041 [P] [US3] 整合測試 `tests/integration/test_us3_admin_controls.py`：
   - 加 whitelist → 下次登入通過
   - 移除 whitelist → 下次登入被擋；既有 session 保留
   - 加 source restriction → 不允許 IP 連 OIDC start 都 401
   - rule 異動立即生效（不重啟）
- [ ] T042 [P] [US3] 整合測試 `tests/integration/test_session_disable_slo.py`：
   - 停用 Member 後 ≤ 5 秒內，該 Member 的所有 session 對任何端點呼叫均 401

### Implementation for US3

- [ ] T043 [P] [US3] 實作 access control 服務於 `src/ai_api/services/access_control.py`（whitelist/rule/restriction CRUD + 查詢）
- [ ] T044 [P] [US3] 實作 members 服務於 `src/ai_api/services/members.py`（create with provider + initial_password / invitation；list/get/patch/delete；session 連帶撤銷）
- [ ] T045 [US3] 實作 `/admin/whitelist`、`/admin/rules`、`/admin/source-restrictions` 端點於 `src/ai_api/api/admin_access.py`
- [ ] T046 [US3] 實作 `/admin/members*` 端點於 `src/ai_api/api/admin_members.py`，含 sessions 列表/撤銷
- [ ] T047 [US3] 在 Session middleware 中加入「每次驗證 session 時同時檢查 Member.status」邏輯（呼應 SC-006）— 修改 `src/ai_api/auth/sessions.py`
- [ ] T048 [US3] 把現有 `src/ai_api/api/allocations.py` 的 POST `/admin/allocations` 改為接受 `member_id`（取代 `subject`）；同步更新 schema 與 Phase 1 contract test
- [ ] T049 [US3] 升級 `AllocationService.create` 於 `src/ai_api/services/allocations.py`：以 member_id 為參數；自動把 `Member.email` 寫入 `subject_snapshot`

**Checkpoint**：管控全功能可用；admin 可以從零到分配憑證給某個 Member 全程操作。

---

## Phase 6: US4 — 一般成員自助 (P2)

**Goal**：成員可看自己分配與用量；不可跨人查。

### Tests for US4 (TDD red)

- [ ] T050 [P] [US4] 契約測試 `tests/contract/test_me_endpoints.py`：
   - `GET /me` 200（含 MemberPublic schema）/ 401
   - `GET /me/allocations` 200（陣列）／ 401
   - `GET /me/allocations/{id}/calls` 200 / 403（跨人）／ 401
- [ ] T051 [P] [US4] 整合測試 `tests/integration/test_us4_member_self_service.py`：
   - Alice 建分配 X、Bob 建分配 Y；Alice 登入只看到 X；嘗試查 Y/calls → 403

### Implementation for US4

- [ ] T052 [P] [US4] 實作 `/me` GET 於 `src/ai_api/api/me.py`
- [ ] T053 [US4] 實作 `/me/allocations` GET 於 `src/ai_api/api/me.py`（內部委派 `AllocationService.list(member_id=current)`）
- [ ] T054 [US4] 實作 `/me/allocations/{id}/calls` GET 於 `src/ai_api/api/me.py`，加 ownership 檢查

---

## Phase 7: Polish & Cross-Cutting

- [ ] T055 [P] 全域 key/secret 洩漏掃描契約測試擴充：在 `tests/contract/test_no_key_leak_global.py` 加入密碼、cookie 值、OIDC client secret、ID token 等情境（呼應 SC-003）
- [ ] T056 [P] 更新 `specs/001-gateway-core/contracts/openapi.yaml` 反映 `Allocation.member_id` 與 `subject_snapshot`，避免兩份契約不一致
- [ ] T057 [P] 更新 `README.md`：加入「Phase 2 已上線」段落與 quickstart 連結
- [ ] T058 [P] 為 Helm chart 加入新 Secret 鍵 `GOOGLE_OAUTH_CLIENT_ID/SECRET`、`BASE_URL`、`COOKIE_SECURE` 於 `deploy/helm/ai-api/templates/secret.yaml` + `values.yaml`
- [ ] T059 [P] 在 `tests/unit/` 加 `test_argon2_hashing.py`、`test_invitation_token.py`、`test_policy_evaluation.py`、`test_session_cookie.py` 純單元測試
- [ ] T060 跑完整測試套件 `uv run pytest -q`，確認全綠
- [ ] T061 按 `specs/002-auth-membership/quickstart.md` 步驟逐項手動驗證，把實測結果寫入 `specs/002-auth-membership/quickstart-run-notes.md`
- [ ] T062 在 `specs/002-auth-membership/quickstart-run-notes.md` 對應 SC-001~SC-009 勾選；對未通過者標明原因
- [ ] T063 把 `knowledge/vision.md` 階段 2 各 checkbox 由 `[ ]` → `[x]`

---

## Dependencies

```
Phase 1 Setup
   │
   ▼
Phase 2 Foundational (包含 US5 subject migration)
   │
   ├─→ Phase 3 (US1 Google SSO)
   ├─→ Phase 4 (US2 Local Password)
   ├─→ Phase 5 (US3 Admin Controls)
   └─→ Phase 6 (US4 Self-service)
                                    │
                                    ▼
                              Phase 7 Polish
```

**Story dependencies**：
- **US5**（subject migration）併入 Foundational（T012–T014），因所有後續
  story 都依賴正確的 Member ↔ Allocation 關係。
- **US1 / US2 / US3 / US4** 之間**相對獨立**：可分四個工作流並行進行；
  但 US3 的 T048/T049（Allocation API 改 member_id）需要 US3 完成才能讓
  Phase 1 端點正常運作 — 建議 US3 為第二優先（US1+US2 也可先用 service
  層 mock member_id）。

---

## Parallel Execution Opportunities

- **Phase 2 Models**：T004–T010 並行（不同檔案），T011 收尾匯入
- **Phase 2 Auth 核心**：T015–T018 並行
- **Phase 2 觀測/CSRF**：T019–T022 並行
- **Phase 3 US1**：T024+T025 測試並行；T026 與 T027 順序執行；T028 收尾
- **Phase 4 US2**：T029–T031 測試並行；T032/T033/T034 服務並行；T035–T038
  端點循序（共用 router 檔案）
- **Phase 5 US3**：T039–T042 測試並行；T043/T044 服務並行；T045/T046 路由
  並行；T047–T049 涉及既有檔案需循序
- **Phase 6 US4**：T050/T051 測試並行；T052/T053/T054 因共用 `me.py` 循序
- **Phase 7**：T055–T059 並行；T060–T063 循序

---

## Implementation Strategy

### MVP 建議優先序

1. **Foundational + US5（migration）** — 不可跳過
2. **US3 Admin Members** — 後續測試都需要先 create Member
3. **US2 Local Password** — 最容易端到端驗證（不需 Google Console）
4. **US1 Google SSO** — Console 設定就緒後再做
5. **US4 自助端點** — 最後上

### TDD 紀律

每個 story 的測試任務應**先**完成並提交一個失敗的 commit，再執行對應的
實作任務（讓 git log 在 `tests/` vs `src/` 的時間戳上呈現 test-before-impl
順序，對應 SC-009）。

### Risk Hot Spots

1. **migration 0002 data step**：對 Phase 1 既有 prod 資料來說是 one-shot；
   建議在 staging 跑一次完整 dump → load → migrate 流程，並把 `subject_snapshot`
   與既有 audit 對得上。
2. **Google OIDC redirect URI 與 BASE_URL 不一致**：開發中最常見的 401。
   plan 階段已列出三組環境的 URL 對照，必須**先在 Console 全部加好**。
3. **Session middleware 對既有 Phase 1 端點的影響**：`/v1/*` 仍以 Bearer
   token 認證，**不**該被 cookie session 攔住；T021/T022 dependency 設計
   需保留兩條認證軸線並存。
4. **Argon2 預設參數在 K8s 小資源叢集可能太慢**：plan 標註 ~50ms。CI 與
   本機 OK；若叢集 CPU limit 嚴格，登入會慢。先量測再考慮降階。

---

## Format Validation

✅ 全部 63 個任務符合 checklist 格式：`- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3–6 任務皆帶對應 [USx] 標籤；US5 任務於 Foundational
✅ 所有任務含明確檔案路徑
