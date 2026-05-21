# Tasks: 階段 1 — 分流核心 (Gateway Core MVP)

**Input**: Design documents from `/specs/001-gateway-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: 本專案啟用 TDD（Constitution Principle I 不可妥協 + spec FR-015）。
**所有測試任務必須在對應實作任務之前完成並失敗**，再進入實作令其通過。

**Organization**: 按 spec.md 的 User Story 與優先序組織；每個 story 都可獨立交付。

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**：可與同階段其他 [P] 任務並行（不同檔案、無互相依賴）
- **[Story]**：US1 / US2 / US3 / US4，對應 spec.md User Stories
- 所有路徑相對於 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

## Path Conventions

Single project layout per plan.md：
- 原始碼：`src/ai_api/`
- 測試：`tests/contract/`、`tests/integration/`、`tests/unit/`
- 部署：`deploy/`
- CI：`.github/workflows/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**：專案骨架、相依套件、本機依賴。

- [ ] T001 建立目錄結構（`src/ai_api/{api,proxy,models,services,observability}/`、`tests/{contract,integration,unit}/`、`deploy/{helm/ai-api,docker}/`、`.github/workflows/`、`alembic/versions/`）per plan.md
- [ ] T002 建立 `pyproject.toml`：Python 3.11、依賴 `litellm[proxy]`、`fastapi`、`uvicorn`、`sqlalchemy[asyncio]>=2`、`alembic`、`asyncpg`、`aiosqlite`、`pydantic>=2`、`pydantic-settings`、`httpx`，dev 依賴 `pytest`、`pytest-asyncio`、`schemathesis`、`testcontainers[postgres]`、`ruff`、`mypy`
- [ ] T003 [P] 設定 lint/format/type 工具於 `pyproject.toml`（ruff、mypy 規則）並建立 `.pre-commit-config.yaml`
- [ ] T004 [P] 建立 `deploy/docker-compose.yml`：本機 PostgreSQL 15（資料卷）與選用的 pgadmin
- [ ] T005 [P] 建立 `.env.example` 範本（DATABASE_URL、ADMIN_BOOTSTRAP_TOKEN、AZURE_OPENAI_API_BASE/KEY/VERSION）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**：在任何 User Story 動工前必須完成的底層基建。

- [ ] T006 實作 SQLAlchemy 2 async engine + session factory 於 `src/ai_api/db.py`
- [ ] T007 初始化 Alembic：`alembic.ini`、`alembic/env.py`、`alembic/script.py.mako`
- [ ] T008 [P] 建立 FastAPI app 骨架於 `src/ai_api/main.py`（含 lifespan、CORS 預留、routers 註冊點）
- [ ] T009 [P] 實作結構化 JSON logger 於 `src/ai_api/observability/logging.py`（含 `setup_logging()`）
- [ ] T010 [P] 在 `src/ai_api/observability/logging.py` 增加 redaction filter：比對 `AZURE_OPENAI_API_KEY` 環境值並替換為 `***`
- [ ] T011 [P] 實作 request_id middleware 於 `src/ai_api/observability/request_id.py`（從 header `X-Request-Id` 讀取或生成 UUID v4）
- [ ] T012 [P] 實作設定載入於 `src/ai_api/config.py`（Pydantic Settings：DATABASE_URL、ADMIN_BOOTSTRAP_TOKEN、AZURE_OPENAI_*）
- [ ] T013 [P] 實作 admin token 驗證 dependency 於 `src/ai_api/api/deps.py`：比對 header `X-Admin-Token` 與設定值
- [ ] T014 [P] 實作 `/healthz` 端點於 `src/ai_api/api/health.py`
- [ ] T015 [P] 建立 contract test harness 於 `tests/contract/conftest.py`：用 schemathesis 載入 `specs/001-gateway-core/contracts/openapi.yaml`
- [ ] T016 [P] 建立 integration test harness 於 `tests/integration/conftest.py`：以 testcontainers 啟動 Postgres、fixture 提供 app + httpx client + DB migration
- [ ] T017 [P] 建立 unit test harness 與 `tests/conftest.py`、`pytest.ini`

**Checkpoint**：Phase 2 完成後，`curl localhost:8000/healthz` 可回 200；空 DB 已準備好；測試 harness 可跑。

---

## Phase 3: User Story 1 — 建立分配並代理呼叫 (P1) 🎯 MVP

**Goal**：管理員可建立一筆分配並取得獨立憑證；持有該憑證者可透過閘道
成功代理呼叫 Azure OpenAI；底層 Azure OpenAI key 不出現於任何外露位置。

**Independent Test**：依 quickstart.md §2 步驟，建立分配 → 取得 token → 用 token 對
`/v1/chat/completions` 呼叫成功 → grep 所有回應與日誌找不到 Azure OpenAI key。

### Tests for US1 (TDD — write first, must fail)

- [ ] T018 [P] [US1] Contract test：POST `/admin/allocations` 於 `tests/contract/test_create_allocation.py`（含 201 happy path、400 validation、401 無 admin token）
- [ ] T019 [P] [US1] Contract test：POST `/v1/chat/completions` 於 `tests/contract/test_proxy_chat.py`（含 200 happy path 結構、401 無 token、403 model mismatch）
- [ ] T020 [P] [US1] Integration test：「建立 → 代理呼叫成功」於 `tests/integration/test_us1_happy_path.py`（需 Azure OpenAI sandbox 或 mock 上游）
- [ ] T021 [P] [US1] Integration test：「底層 key 不出現於回應/header/日誌」於 `tests/integration/test_us1_no_key_leak.py`（對成功 + 各種錯誤路徑共 ≥10 個情境掃描）

### Implementation for US1

- [ ] T022 [P] [US1] 建立 Allocation SQLAlchemy 模型於 `src/ai_api/models/allocation.py`（依 data-model.md）
- [ ] T023 [P] [US1] 建立 Credential SQLAlchemy 模型於 `src/ai_api/models/credential.py`
- [ ] T024 [US1] 建立初版 Alembic migration `alembic/versions/0001_init_allocations_credentials.py`（含索引）
- [ ] T025 [P] [US1] 實作 credential token 生成 + SHA-256 fingerprint 於 `src/ai_api/services/credentials.py`
- [ ] T026 [US1] 實作 `AllocationService.create()` 於 `src/ai_api/services/allocations.py`（建立 Allocation + Credential，回傳明文 token）
- [ ] T027 [US1] 實作 POST `/admin/allocations` 與 GET `/admin/allocations` 端點於 `src/ai_api/api/allocations.py`
- [ ] T028 [P] [US1] 實作 LiteLLM proxy 設定生成於 `src/ai_api/proxy/config.py`（Azure OpenAI 模型 routing、底層 key 注入）
- [ ] T029 [US1] 實作代理憑證驗證 middleware 於 `src/ai_api/proxy/auth.py`：解析 Bearer → 查 fingerprint → 取得 allocation
- [ ] T030 [US1] 實作 model binding guard 於 `src/ai_api/proxy/guard.py`：請求 body `model` 必須等於 allocation.resource_model
- [ ] T031 [US1] 將 LiteLLM proxy 掛載到 `/v1/*` 並插入 auth + guard middlewares 於 `src/ai_api/main.py`
- [ ] T032 [US1] 驗證 US1 全部測試由 fail → pass；提交時確保 git 歷史中測試 commit 早於對應實作 commit（對應 SC-008）

**Checkpoint**：MVP 達成。Quickstart §2 全部可走通。可獨立交付給使用者試用。

---

## Phase 4: User Story 2 — 撤回分配，後續呼叫即刻遭拒 (P1)

**Goal**：擁有者撤回分配後 5 秒內，原憑證的呼叫必須被拒；撤回為冪等操作；
不影響其他分配。

**Independent Test**：依 quickstart.md §3 步驟，撤回後在 5 秒內以原 token 呼叫，
應收到 `error.code = allocation_revoked`；對同一 ID 再次 DELETE 應為冪等成功。

### Tests for US2

- [ ] T033 [P] [US2] Contract test：DELETE `/admin/allocations/{id}` 於 `tests/contract/test_revoke_allocation.py`（含 200 撤回、200 冪等再撤、404 不存在、401 無 admin token）
- [ ] T034 [P] [US2] Integration test：「撤回後 5 秒內呼叫遭拒」於 `tests/integration/test_us2_revocation_slo.py`（量測 wall-clock，斷言 ≤ 5s）
- [ ] T035 [P] [US2] Integration test：「撤回 A 不影響 B」於 `tests/integration/test_us2_isolation.py`

### Implementation for US2

- [ ] T036 [US2] 實作 `AllocationService.revoke()` 於 `src/ai_api/services/allocations.py`（冪等：對 revoked 狀態直接回現況）
- [ ] T037 [US2] 實作 DELETE `/admin/allocations/{id}` 端點於 `src/ai_api/api/allocations.py`
- [ ] T038 [US2] 擴充 `src/ai_api/proxy/auth.py` 驗證流程：每次呼叫必查 DB allocation.status，狀態 `revoked` 即拒並回應 `error.code = allocation_revoked`（403）
- [ ] T039 [US2] 驗證 US2 全部測試由 fail → pass

**Checkpoint**：可撤回。Quickstart §3 可走通。

---

## Phase 5: User Story 3 — 呼叫可追溯到分配 (P1)

**Goal**：每次呼叫（含拒絕）皆寫入結構化紀錄；可依分配 ID 查詢；匿名拒絕
不歸屬任何分配。

**Independent Test**：依 quickstart.md §4 步驟，查詢 `/admin/allocations/{id}/calls`
應回傳成功與失敗兩類紀錄；以無效 token 呼叫產生的紀錄 `allocation_id == null`。

### Tests for US3

- [ ] T040 [P] [US3] Contract test：GET `/admin/allocations/{id}/calls` 於 `tests/contract/test_list_calls.py`（含 200、limit/before cursor、404）
- [ ] T041 [P] [US3] Integration test：「成功與拒絕呼叫皆可追溯到分配」於 `tests/integration/test_us3_attribution.py`
- [ ] T042 [P] [US3] Integration test：「匿名拒絕 allocation_id 為 null」於 `tests/integration/test_us3_anonymous.py`
- [ ] T043 [P] [US3] Integration test：「error_message 經 redaction，不含底層 key」於 `tests/integration/test_us3_redacted_error.py`

### Implementation for US3

- [ ] T044 [P] [US3] 建立 CallRecord SQLAlchemy 模型於 `src/ai_api/models/call_record.py`
- [ ] T045 [US3] 建立 Alembic migration `alembic/versions/0002_call_records.py`（含 outcome 列舉與索引）
- [ ] T046 [P] [US3] 實作 `RecordsService` 於 `src/ai_api/services/records.py`（persist + 查詢 + cursor 分頁）
- [ ] T047 [US3] 在 proxy success 路徑中持久化 CallRecord（含 token 用量）於 `src/ai_api/proxy/auth.py`
- [ ] T048 [US3] 在 proxy reject 路徑中持久化 CallRecord（含各種 outcome）於 `src/ai_api/proxy/auth.py` + `guard.py`
- [ ] T049 [US3] 實作 GET `/admin/allocations/{id}/calls` 端點於 `src/ai_api/api/records.py`
- [ ] T050 [US3] 將 `error_message` 寫入 DB 前通過 redaction（呼叫 logging filter 函式）於 `src/ai_api/services/records.py`
- [ ] T051 [US3] 驗證 US3 全部測試由 fail → pass

**Checkpoint**：完整 P1 三條 user story 完成。Quickstart §2~§4 全部可走通。

---

## Phase 6: User Story 4 — 宣告式部署與安全更新 (P2)

**Goal**：可用 Helm 部署到 K8s；LiteLLM 鏡像自動追蹤上游；失敗更新可在 5
分鐘內回滾。

**Independent Test**：依 quickstart.md §5 步驟，`helm install` 後 healthz 通過；
故意升級至不存在 tag → readiness 失敗 → `helm rollback` 恢復。

### Tests for US4

- [ ] T052 [P] [US4] 撰寫 helm chart 結構驗證測試於 `tests/integration/test_us4_helm_template.py`（執行 `helm template` 並斷言關鍵欄位存在）

### Implementation for US4

- [ ] T053 [P] [US4] 建立 `deploy/docker/Dockerfile`（多階段 build，distroless 或 slim base，non-root user）
- [ ] T054 [P] [US4] 建立 Helm chart 骨架 `deploy/helm/ai-api/Chart.yaml`、`values.yaml`
- [ ] T055 [P] [US4] 建立 Deployment 模板 `deploy/helm/ai-api/templates/deployment.yaml`（含 readiness/liveness probe 指向 `/healthz`、resources、image tag from values）
- [ ] T056 [P] [US4] 建立 Service 模板 `deploy/helm/ai-api/templates/service.yaml`
- [ ] T057 [P] [US4] 建立 Ingress 模板 `deploy/helm/ai-api/templates/ingress.yaml`（可由 values 啟用/停用）
- [ ] T058 [P] [US4] 建立 Secret 模板 `deploy/helm/ai-api/templates/secret.yaml`（admin token + Azure OpenAI key）
- [ ] T059 [P] [US4] 建立 ConfigMap / migration Job 模板 `deploy/helm/ai-api/templates/migration-job.yaml`（部署前跑 alembic upgrade）
- [ ] T060 [P] [US4] 建立 Renovate 設定 `renovate.json`（監看 `values.yaml` 的 LiteLLM image tag、每週開 PR）
- [ ] T061 [P] [US4] 建立 CI workflow `.github/workflows/ci.yml`（lint + unit + contract + integration with Postgres service）
- [ ] T062 [P] [US4] 建立 image build workflow `.github/workflows/image.yml`（push image 至 registry）
- [ ] T063 [US4] 撰寫回滾 runbook 於 `deploy/ROLLBACK.md`（含 `helm rollback` 步驟、健康檢查指令）
- [ ] T064 [US4] 在開發叢集驗證 quickstart §5（install → 模擬失敗升級 → rollback ≤ 5 分鐘），結果寫入 `specs/001-gateway-core/quickstart-run-notes.md`

**Checkpoint**：階段 1 vision 全部成功標準達成。可發佈至內部開發叢集。

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T065 [P] 撰寫專案 `README.md`：簡介 + 連結到 `knowledge/`、`specs/001-gateway-core/`、quickstart
- [ ] T066 [P] 量測撤回 SLO 並紀錄於 `specs/001-gateway-core/quickstart-run-notes.md`（對應 SC-002）
- [ ] T067 [P] 在 `tests/contract/` 加上「對所有對外端點掃描底層 key」的契約測試 `test_no_key_leak_global.py`（對應 SC-003 全覆蓋）
- [ ] T068 跑全套測試（unit + contract + integration），確認全綠
- [ ] T069 逐項勾選 spec.md §Success Criteria SC-001~SC-008，把結果寫入 `quickstart-run-notes.md`
- [ ] T070 更新 `knowledge/vision.md` 階段 1 各 checkbox 由 `[ ]` → `[x]`；確認與專案實況一致

---

## Dependencies

```
Phase 1 (Setup) ──┐
                  ▼
Phase 2 (Foundational) ──┐
                          ▼
                    ┌─ Phase 3 (US1) ─┐
                    │  (MVP — P1)      │
                    │                  ▼
                    ├─ Phase 4 (US2) ──┤  US2 依賴 US1 的代理路徑與 Allocation
                    │  (P1)            │  model；同檔案修改順序進行
                    │                  ▼
                    ├─ Phase 5 (US3) ──┤  US3 依賴 US1 的代理路徑掛載點
                    │  (P1)            │
                    │                  ▼
                    └─ Phase 6 (US4) ──┘  US4 大部分檔案在 deploy/，與 US1~3
                       (P2)              並行可行；T064 需 US1~3 完成才能驗證
                                         功能正確性
                                         ▼
                                  Phase 7 (Polish)
```

**Story dependencies**：
- **US1**：依 Phase 1 + 2
- **US2**：依 US1（共用 `proxy/auth.py`、`api/allocations.py`、Allocation model）
- **US3**：依 US1（hook 進 proxy 既有路徑）
- **US4**：可與 US1~3 並行起步；最終驗證任務 T064 需 US1~3 完成

---

## Parallel Execution Opportunities

**Phase 1**：T003 / T004 / T005 可並行。

**Phase 2**：T008 / T009 / T010 / T011 / T012 / T013 / T014 / T015 / T016 / T017
可並行（不同檔案）；T006 → T007 需循序。

**Phase 3（US1）**：
- 測試先寫：T018 / T019 / T020 / T021 並行
- 模型：T022 / T023 / T025 / T028 並行（不同檔案）
- T024（migration）需 T022 + T023 完成
- T026 → T027 循序（同檔依賴）
- T029 → T030 → T031 循序（同檔案修改且邏輯依賴）

**Phase 4（US2）**：T033 / T034 / T035 測試並行；T036~T038 循序（與 US1 共用檔案）。

**Phase 5（US3）**：T040 / T041 / T042 / T043 測試並行；T044 / T046 並行；
T047 / T048 同檔案需循序；T049 / T050 並行。

**Phase 6（US4）**：T053~T062 幾乎全部並行（不同檔案）；T063 / T064 循序。

**Phase 7**：T065 / T066 / T067 並行。

---

## Implementation Strategy

### MVP First（建議第一週交付目標）

只完成 **Phase 1 → Phase 2 → Phase 3 (US1)**，即可：
- 對內部少量 alpha 使用者開放：管理員手動建立分配 → 使用者代理呼叫 Azure
  OpenAI
- 驗證根公理「分享是資源的分配」可被實際操作

撤回（US2）、追溯（US3）、部署（US4）可在後續週次補上，每完成一個就是一次
可獨立交付的 increment。

### TDD 流程

每個 implementation 任務前必須先有對應失敗測試（標示為 [P] 的測試任務
應全部完成且全部失敗，才能進入該 story 的 implementation 區段）。SC-008
要求 git 歷史中「測試 commit 早於實作 commit」可被驗證。

### Risk Hot Spots

1. **撤回 SLO**：T034 是這個 story 的最關鍵測試；若 DB 連線過慢可能 borderline
   通過。實作時保持「每次呼叫查 DB」的簡單策略（research.md §4），勿過早優化。
2. **底層 key 洩漏**：T021 + T067 雙重把關；redaction filter（T010）與
   contract test 為防禦深度。
3. **LiteLLM 介接形態**：T028 / T031 是技術不確定性最高之處；若 LiteLLM
   API 與 research.md §1~§2 推測有出入，可能需小幅調整介接點，但**不影響
   spec 與契約**——這是契約優先的價值。

---

## Format Validation

✅ 全部 70 個任務皆符合格式：`- [ ] T### [P?] [US?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 階段無 [US] 標籤
✅ US1~US4 階段每個任務都帶對應 [US] 標籤
✅ 所有任務含明確檔案路徑
