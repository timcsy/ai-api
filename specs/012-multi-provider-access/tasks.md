# Tasks: Multi-Provider Support with Admin-Managed Credentials and Tag-Based Access

**Input**: Design documents from `/specs/012-multi-provider-access/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Constitution I 強制 TDD — 每個 story 必有 failing test 先於實作。

**Organization**: 按 user story 分 Phase；P1 完即可成 MVP demo（admin 用 fixture 注入 credential，member 呼叫多 provider）。

**Branch dependency note**: 本 branch 從 main fork，假設 PR #11（011-hotfix-i18n-rotation）會**先合入 main**。若 011 未合，T012 重寫 `upstream.py` 時要從 main 當下版本（litellm-based）改回 litellm-based + 多 provider，不會比較痛；若 011 已合，T012 從 openai-SDK 版本改回 litellm-based。任一狀況都不影響 task 結構。

---

## Phase 1: Setup（共享基礎）

**目的**：相依套件 + 設定欄位

- [X] T001 在 `pyproject.toml` `dependencies` 中加入 `litellm>=1.55,<2`（**不裝 `[proxy]` extra**）；確認 `cryptography>=43` 已存在（透過 `argon2-cffi` 間接帶入則明示加為直接依賴）；`uv sync --all-extras` 後跑 `uv run pytest -q` 確認既有 213 tests 不退步
- [X] T002 [P] 在 `src/ai_api/config.py` 加入 `provider_key_enc_key: str = Field(default="", alias="PROVIDER_KEY_ENC_KEY")`；保留現有 Azure 欄位不動（US4 之後才拔）
- [X] T003 [P] 確認 `Settings.allowed_providers` 預設值含 `["azure_openai", "openai", "anthropic", "gemini"]`；若已有則擴充；寫 `tests/unit/test_config_allowed_providers.py` 驗證預設值

---

## Phase 2: Foundational（阻塞性前置）

**目的**：DB schema、加密基礎、稽核事件型別——US1~US4 全部依賴

**⚠️ CRITICAL**：本 phase 全綠之前不可開始任何 user story

### Crypto 基礎

- [X] T004 寫 `tests/unit/test_crypto_fernet.py`（紅）：
  - `encrypt_then_decrypt_roundtrip` 對任意 bytes 一致
  - `decrypt_with_wrong_key_raises`
  - `tampered_ciphertext_raises`
  - `load_fernet_from_settings_missing_key_raises`
- [X] T005 實作 `src/ai_api/services/crypto.py`（綠）：`Fernet` factory；模組層級 `_FERNET: Fernet | None = None`；`get_fernet()` 第一次呼叫時讀 settings，缺 key 或不合法 raise `CryptoConfigError`
- [X] T006 在 `src/ai_api/main.py` lifespan startup 階段呼叫 `get_fernet()` 一次以**前置驗證**；失敗 raise 讓 uvicorn 拒絕啟動；寫 `tests/integration/test_startup_crypto.py` 驗證缺 key 時 app 啟動失敗

### DB schema

- [X] T007 [P] 寫 `src/ai_api/models/provider_credential.py`：欄位對照 data-model.md §1；包含 `Mapped[bytes]` enc_key、`Mapped[str]` fingerprint、`Mapped[ProviderStatus]` status enum
- [X] T008 [P] 寫 `src/ai_api/models/member_tag.py`：composite PK `(member_id, tag)`；ON DELETE CASCADE；index on `(tag)` 與 `(member_id)`
- [X] T009 修改 `src/ai_api/models/model_catalog.py` 加 4 欄：`provider`、`default_access`（enum）、`allowed_tags`、`denied_tags`（JSON list，nullable=False default `[]`）
- [X] T010 修改 `src/ai_api/models/auth_audit.py` 的 `AuditEventType` enum，加 8 個新值：`provider_credential_{created,rotated,disabled,used_first_time}`、`member_tag_{added,removed,bulk_added}`、`model_access_policy_updated`
- [X] T011 [P] 寫 `alembic/versions/0009_phase5_multiprovider_schema.py`：建 `provider_credentials` + `member_tags` 表 + index + unique；對 `model_catalog` 加 4 欄；backfill 既有 9 row（`provider='azure_openai'`、`default_access='open'`、`allowed_tags=[]`、`denied_tags=[]`）
- [X] T012 [P] 寫 `alembic/versions/0010_phase5_audit_events.py`：沿用 0007/0008 batch_alter_table pattern 擴 enum
- [X] T013 在 `src/ai_api/models/__init__.py` 匯出 `ProviderCredential`、`MemberTag`、新 enum 值；跑 `alembic upgrade head` 在 sqlite + postgres 雙環境驗證

**Checkpoint**：T001-T013 完成；`uv run pytest tests/unit/test_crypto_fernet.py tests/integration/test_startup_crypto.py tests/unit/test_config_allowed_providers.py -v` 全綠；schema migration 雙環境 OK

---

## Phase 3: User Story 1 — 多 Provider 代理可用 (Priority: P1) 🎯 MVP

**Goal**：admin 注入 ≥2 家 provider credential（fixture）+ catalog 含對應 model → member 用同一 token 呼叫不同 provider 都成功

**Independent Test**：跑 `tests/integration/test_us1_multiprovider.py` — 在 fixture 中建 Azure + Anthropic credential，建 1 筆 allocation，依序呼叫 `gpt-4o-mini` 與 `claude-3-5-sonnet`，兩次都回 200 + OpenAI 相容 schema

### US1 Tests（先紅）

- [ ] T014 (deferred from MVP) [P] [US1] 寫 `tests/contract/test_proxy_multiprovider.py`：
  - happy path × 4 provider（Azure/OpenAI/Anthropic/Gemini）各 1 個 model；用 `respx` 或 fixture `_client()` 攔截 litellm 底層 HTTP
  - `provider_unavailable_when_no_credential`：model 對應 provider 無 active credential → 503 `provider_unavailable`
  - `model_not_in_catalog_404`：不認識 model → 404
- [X] T015 [P] [US1] 寫 `tests/integration/test_us1_multiprovider.py`：US1 Acceptance Scenarios 1-3 完整流程
- [ ] T016 (deferred from MVP) [P] [US1] 寫 `tests/unit/test_provider_rr.py`：round-robin 邏輯（建 3 個 active credential → 連續呼叫 3 次拿到不同 id；先記 last_used_at 的排序行為）

### US1 Implementation

- [X] T017 [US1] 實作 `src/ai_api/services/provider_credentials.py` 最小可用版（讓 T014/T015 綠）：
  - `get_next_for(provider) -> ProviderCredential | None`：`ORDER BY last_used_at ASC NULLS FIRST LIMIT 1` + update `last_used_at`
  - `decrypt(cred) -> str`：用 `crypto.get_fernet().decrypt(cred.enc_key).decode()`
  - 不含 admin CRUD（留 US2）
- [X] T018 [US1] 重寫 `src/ai_api/proxy/upstream.py`：改用 `litellm.acompletion`，依 catalog model 的 `provider` 欄查 credential → decrypt → 組 model id（如 `azure/<deployment>`、`openai/<model>`、`anthropic/<model>`、`gemini/<model>`）+ 必要參數（Azure 加 `api_version`、Gemini 加 `vertex_project/location`）；找不到 credential 拋 `ProviderUnavailableError`
- [X] T019 [US1] 修改 `src/ai_api/proxy/router.py`：catch `ProviderUnavailableError` → 503 `{"error":{"code":"provider_unavailable",...}}`
- [ ] T020 (deferred from MVP) [US1] 修改 `src/ai_api/cli/load_models.py`（YAML loader）：強制 `provider` / `default_access` 必填；缺欄列出明確錯誤；接受 `allowed_tags` / `denied_tags`（缺則 default `[]`）
- [ ] T021 (deferred from MVP) [P] [US1] 擴充 `models/catalog.yaml`（或對應檔名）：加入 `gpt-4o`（openai）、`claude-3-5-sonnet`（anthropic）、`gemini-1.5-pro`（gemini）至少各 1 個示範 model；既有 9 個 Azure model 補 `provider: azure_openai` + `default_access: open`
- [X] T022 [US1] 在 `tests/conftest.py` 加 `provider_credential_fixture` helper：方便 US1/US2/US3 整合測試注入加密 credential
- [X] T023 [US1] 跑 `uv run pytest tests/contract/test_proxy_multiprovider.py tests/integration/test_us1_multiprovider.py tests/unit/test_provider_rr.py -v` 全綠；檢查既有 213 tests 不退步

**Checkpoint**：MVP 達成——admin 在 DB 直接 insert credential（或測試用 fixture），member 已能跨 provider 呼叫

---

## Phase 4: User Story 2 — Admin 在 UI 管理 Provider Credential (Priority: P2)

**Goal**：admin 透過 web UI 做 credential CRUD + rotate + disable；明文 key 一次性顯示

**Independent Test**：US2 Acceptance Scenarios 1-4；跑 `tests/contract/test_admin_providers.py` + `tests/integration/test_us2_credential_ui.py` + 前端 `frontend/src/__tests__/admin-providers.test.tsx`

### US2 Backend Tests（先紅）

- [X] T024 [P] [US2] 寫 `tests/contract/test_admin_providers.py`：對 `contracts/providers.yaml` 中每個 endpoint × 每個 response 至少 1 個 test（含 401 / 403 / 404 / 409 / 422）；特別涵蓋：
  - 建立 → 201 含 `api_key` 欄位（plaintext）
  - 重新 GET → 不含 `api_key`，含 `fingerprint`
  - 同 (provider, label) 重複建立 → 409
  - provider 不在 allowlist → 422 `provider_not_allowed`
  - rotate → 200 含新 `api_key`、fingerprint 變
  - disable → 200 status=disabled；再 disable → 409
- [X] T025 [P] [US2] 寫 `tests/integration/test_us2_credential_ui.py`：完整 lifecycle（建立 → 列表 → rotate → 用新 key 呼叫 proxy 成功、舊 key 呼叫 503 → disable → 呼叫 503）
- [ ] T026 (deferred to next session) [P] [US2] 寫 `tests/contract/test_no_key_leak_global.py` 加 scenario `provider_credential_in_logs`：建立 + rotate + 觸發 upstream 錯誤 → grep stdout/stderr/audit log 完全找不到 plaintext key（沿用既有 framework）

### US2 Backend Implementation

- [X] T027 [US2] 擴充 `src/ai_api/services/provider_credentials.py`：補齊 `create`、`list`、`get`、`rotate`、`disable`；建立 / rotate 內含 `Fernet.encrypt` + `fingerprint = sha256(plain).hex()[:16]`；寫對應稽核事件
- [X] T028 [US2] 寫 `src/ai_api/api/admin_providers.py`：實作 `contracts/providers.yaml` 所有路由；套 `require_admin` dep；CSRF 套既有 dep
- [X] T029 [US2] 在 `src/ai_api/main.py` 註冊 `admin_providers.router` 到 `/admin` prefix
- [X] T030 [US2] 觸發 first-use 稽核：在 `provider_credentials.get_next_for` 內，若該 credential 首次被選用（`last_used_at IS NULL`）則寫 `provider_credential_used_first_time`

### US2 Frontend Tests（先紅）

- [ ] T031 (deferred to next session) [P] [US2] 寫 `frontend/src/__tests__/admin-providers.test.tsx`：列表 render、open create dialog、submit 後出現 plaintext banner、refresh 後 banner 消失 + fingerprint 仍可見、rotate 流程、disable 確認

### US2 Frontend Implementation

- [ ] T032 (deferred to next session) [US2] 寫 `frontend/src/routes/admin/providers.tsx`：TanStack Query useQuery + 4 mutations（create / rotate / disable / 移除無）；create / rotate 後彈 `Dialog` 一次性顯示 plaintext + `copyToClipboard`；列表用 `Table` 顯示 provider / label / fingerprint / status / last_used / created_at
- [ ] T033 (deferred to next session) [US2] 在 `frontend/src/components/app-shell.tsx` admin nav 加入「Provider 憑證」連結，連到 `/admin/providers`
- [ ] T034 (deferred to next session) [US2] 跑 backend pytest 與 frontend `npm test` 全綠；手動跑 quickstart 場景 A

**Checkpoint**：admin 可在 UI 完整管 credential；US1 既有測試仍綠

---

## Phase 5: User Story 3 — Tag-based 存取規則 (Priority: P3)

**Goal**：admin 為 member 打 tag、為 model 設定 access policy；catalog 與 proxy 雙處過濾立即生效

**Independent Test**：US3 Acceptance Scenarios 1-6；跑 `tests/integration/test_us3_tag_access.py`

### US3 Backend Tests（先紅）

- [ ] T035 [P] [US3] 寫 `tests/contract/test_admin_tags.py`：對 `contracts/tags.yaml` 所有 endpoint；特別：tag 格式 regex `^[a-z][a-z0-9_-]{0,63}$`；非 admin 403；無此 member 404；重複加 idempotent；bulk-apply 回 `applied_count` / `skipped_count`
- [ ] T036 [P] [US3] 寫 `tests/contract/test_admin_model_access.py`：PATCH `/admin/catalog/models/{slug}/access` 全欄位；無此 slug 404；tag 格式錯誤 422；寫稽核 `model_access_policy_updated`
- [ ] T037 [P] [US3] 寫 `tests/contract/test_catalog_filtering.py`：
  - 兩段過濾的 truth table（4×4 至少）：credential ∈ {present, absent} × policy ∈ {open, restricted+allow_hit, restricted+no_allow_hit, deny_hit}
  - alice 有 `eng` tag、bob 無 → claude `allowed=["eng"]` → alice 看到、bob 看不到
  - deny 優先於 allow（alice 有 eng + contractor、claude `allowed=["eng"]` `denied=["contractor"]` → 拒絕）
- [ ] T038 [P] [US3] 寫 `tests/unit/test_model_access_policy.py`：純邏輯 unit test on `visible_to_member(model, tags)`，純函式無 DB
- [ ] T039 [P] [US3] 寫 `tests/integration/test_us3_tag_access.py`：完整 6 個 acceptance scenarios，包含 bulk apply + proxy 二次檢查 + tag 變更立即生效

### US3 Backend Implementation

- [ ] T040 [US3] 寫 `src/ai_api/services/member_tags.py`：`list_for_member`、`add`、`remove`、`bulk_apply(tag, member_ids)`、`list_distinct() -> [{tag, member_count}]`、`delete_tag(tag)`；含 audit 寫入
- [ ] T041 [US3] 寫 `src/ai_api/services/model_access.py`：
  - `visible_to_member(member: Member, models: list[ModelCatalog], session) -> list[ModelCatalog]` — pre-loads member tags + active providers，套兩段過濾
  - `is_accessible(member, model, session) -> bool` — proxy 用
- [ ] T042 [US3] 寫 `src/ai_api/api/admin_tags.py`：對應 `contracts/tags.yaml`
- [ ] T043 [US3] 寫 `src/ai_api/api/admin_model_access.py`：PATCH endpoint；寫稽核
- [ ] T044 [US3] 修改 `src/ai_api/api/catalog.py` 的 list / detail：套用 `model_access.visible_to_member`；detail 對不可見 model 回 404（**不**回 403，避免洩漏存在性）
- [ ] T045 [US3] 修改 `src/ai_api/proxy/router.py`：在 model lookup 後、upstream 前呼叫 `model_access.is_accessible`；False 則 403 `{"error":{"code":"model_forbidden",...}}` + 寫稽核 `rejected_forbidden_model`
- [ ] T046 [US3] 在 main.py 註冊 `admin_tags.router` 與 `admin_model_access.router`

### US3 Frontend Tests（先紅）

- [ ] T047 [P] [US3] 寫 `frontend/src/__tests__/admin-tags.test.tsx`：tag 列表、為 member 加/移除 tag、bulk apply 多選確認流程
- [ ] T048 [P] [US3] 寫 `frontend/src/__tests__/admin-model-access.test.tsx`：選 model → 改 `default_access` + tag 列表 → submit → 確認 UI 立即反映

### US3 Frontend Implementation

- [ ] T049 [US3] 寫 `frontend/src/routes/admin/tags.tsx`：tag 列表（含 member_count）+ delete 全域 + 在「members」視圖加 inline tag chips（小改）+ bulk-apply 對話框（多選 member checkbox + 選 tag）
- [ ] T050 [US3] 修改 `frontend/src/routes/admin/members.tsx` 加 tag chips 顯示與「批次貼標」按鈕（多選後啟用）
- [ ] T051 [US3] 寫 `frontend/src/routes/admin/model-access.tsx`：選 model（從 catalog 抓） → 表單編 default_access (radio) + allowed_tags (multi-select) + denied_tags (multi-select)；submit 後 toast
- [ ] T052 [US3] 在 `app-shell.tsx` admin nav 加「Tag 管理」與「Model 存取」兩個連結
- [ ] T053 [US3] 跑 backend + frontend 全套 test 綠；手動跑 quickstart 場景 B

**Checkpoint**：tag 機制全功能；6 個 acceptance scenarios 自動化驗證

---

## Phase 6: User Story 4 — 既有 Azure env 遷移 (Priority: P4)

**Goal**：提供 CLI 把 env 灌入 DB；過渡期程式碼 DB 優先 + env fallback；final release 拔 fallback

**Independent Test**：US4 Acceptance Scenarios 1-3；跑 `tests/integration/test_us4_azure_env_migration.py`

### US4 Tests（先紅）

- [ ] T054 [P] [US4] 寫 `tests/integration/test_us4_azure_env_migration.py`：
  - given env 設了 Azure key + DB 無對應 credential，跑 migration CLI → DB 出現 `provider='azure_openai'`、`label='migrated-from-env'`、稽核 metadata `source=env_migration`
  - 再跑一次 → 印 skip + DB 不重複建立
  - migration 完成後 proxy 呼叫優先用 DB credential（透過監看 last_used_at 變化驗證）
- [ ] T055 [P] [US4] 寫 `tests/unit/test_upstream_env_fallback.py`：模擬 transitional 行為——DB 無 credential 時 fallback 讀 `Settings.azure_openai_api_key`；DB 有時無視 env

### US4 Implementation（transitional release N+1）

- [ ] T056 [US4] 寫 `src/ai_api/cli/migrate_azure_env.py`：argparse + 連 DB；讀 `Settings.azure_openai_api_key/_api_base/_api_version`；任一為空 → 拒絕並印「nothing to migrate」；存在則 `provider_credentials_service.create(provider='azure_openai', label='migrated-from-env', api_key=key, base_url=base, extra_config={'api_version':ver})`；audit metadata 加 `source=env_migration`；idempotent
- [ ] T057 [US4] 修改 `src/ai_api/proxy/upstream.py`：在 `get_next_for('azure_openai')` 回 None 時 fallback 用 env 設定組臨時 credential 物件（不寫 DB）；補 log（INFO 等級）「using env fallback for azure_openai」每 5 分鐘最多 1 次（避免噪音）
- [ ] T058 [US4] 跑 T054 / T055 全綠

### US4 Final release N+2（separate PR 或本 phase 後段）

- [ ] T059 [US4] 在合適時機（quickstart 場景 D 完成後）開新 commit：從 `upstream.py` 移除 env fallback 路徑；移除 `Settings.azure_openai_api_key/_api_base/_api_version` 三個欄位；對應 helm `values.yaml` 與 `secret.yaml` 移除 `AZURE_OPENAI_API_KEY` env entry；新增 release notes 標 BREAKING
- [ ] T060 [US4] 更新對應 contract / integration test：把「env fallback」案例改成「無 fallback → 503 provider_unavailable」

**Checkpoint**：兩 release 路徑可驗證；docs 記載升級 SOP

---

## Phase 7: Helm + Deployment（橫切，跨 US2/US4）

- [ ] T061 修改 `deploy/helm/ai-api/templates/secret.yaml`：加 `PROVIDER_KEY_ENC_KEY` entry；標為必要（`required` Helm function 對 `values.providerKeyEncKey` 缺則 fail template）
- [ ] T062 修改 `deploy/helm/ai-api/templates/deployment.yaml`：env 區段加 `secretKeyRef` 引用上述 secret entry
- [ ] T063 修改 `deploy/helm/ai-api/values.yaml`：加 `providerKeyEncKey: ""`（佔位 + 註解標必填）
- [ ] T064 [P] 寫 `tests/integration/test_helm_template.py` 新案例：缺 `providerKeyEncKey` 時 helm template 失敗 + 完整檔有效

---

## Phase 8: Polish & 橫切

- [ ] T065 [P] 更新 `knowledge/vision.md` 階段 5 SC checkboxes（將完成項打勾）
- [ ] T066 [P] 寫 `knowledge/experience.md` 加一條教訓：「ProviderCredential 加密 - K8s Secret 啟動時前置驗證」（pod 失敗啟動比 runtime 出包好）
- [ ] T067 [P] 寫 `docs/phase5-multiprovider.md`：admin 操作手冊（新增 provider、rotate、tag 管理）；連結 quickstart.md
- [ ] T068 [P] CHANGELOG.md 或 `release-notes/0.2.0.md` 加 entry：features + breaking changes + migration SOP
- [ ] T069 跑全套 gate：`uv run pytest -q && uv run ruff check . && uv run mypy src/ai_api && cd frontend && npm run lint && npm run typecheck && npm test -- --run`；提交前確認 zero regression

---

## Dependencies

```text
Setup (T001-T003)
    ↓
Foundational (T004-T013) ← 必須全綠
    ↓
US1 (T014-T023) ────────────────┐
    ↓                           │
US2 (T024-T034) — needs US1 ──┐ │
    ↓                         │ │
US3 (T035-T053) ─────────────┐│ │  ← 可與 US2 部分並行
    ↓                       ↓↓ ↓
US4 (T054-T060) ────────── 全部需要 US1 完成
    ↓
Helm (T061-T064) — 可與 US2/US4 並行
    ↓
Polish (T065-T069)
```

**並行機會**：
- T002 / T003 可並行
- T007 / T008 / T011 / T012 可並行（不同檔）
- US1 內 T014 / T015 / T016 test 可並行
- US2 內 T024 / T025 / T026 / T031 可並行
- US3 內 T035-T039、T047 / T048 大量可並行
- US4 內 T054 / T055 可並行
- Polish 內 T065-T068 全部可並行
- Helm Phase 7 可與 US2 backend / US4 並行

## Implementation Strategy

**MVP scope = US1 完成**：T001-T023 共 23 task；admin 用 fixture / SQL 直接 insert credential，member 已能跨 provider 呼叫。約 2-3 日工。

**穩定 release = US1 + US2 完成**：再加 11 task；admin 可在 UI 管 credential。約 +2 日。

**Phase 5 full = 全部完成**：再加 35 task（US3 含 frontend）+ migration（US4）+ Helm + polish。約 +3-4 日。

**總估**：69 task，依 TDD 節奏 ~7-9 個工作日（單一全職 dev；可並行的話更快）

## Task 總覽

| Phase | Tasks | 並行潛力 |
|---|---|---|
| Setup | T001-T003 (3) | T002/T003 並行 |
| Foundational | T004-T013 (10) | T007/T008/T011/T012 並行 |
| US1 (P1, MVP) | T014-T023 (10) | tests + T021 並行 |
| US2 (P2) | T024-T034 (11) | tests 並行；frontend 與 backend 序列 |
| US3 (P3) | T035-T053 (19) | tests 大量並行；UI/Backend 序列 |
| US4 (P4) | T054-T060 (7) | tests 並行 |
| Helm | T061-T064 (4) | T064 與其他並行 |
| Polish | T065-T069 (5) | T065-T068 全並行 |
| **Total** | **69 tasks** | |
