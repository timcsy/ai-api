# Tasks: 管理員 Bootstrap 與部署強化

**Input**: Design documents from `/specs/017-admin-bootstrap/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: 強制 TDD（Constitution Principle I）—— 每個 user story 先寫失敗測試再實作。

## Phase 1: Setup

- [ ] T001 確認分支 `017-admin-bootstrap` 與既有測試基線：`uv run pytest -q` 全綠、`uv run ruff check .` 無錯，作為退化比對基準（SC-005）。

## Phase 2: Foundational（阻擋 US2）

- [ ] T002 在 `src/ai_api/config.py` 抽出模組常數 `DEFAULT_ADMIN_BOOTSTRAP_TOKEN = "local-dev-admin-only"`，並讓 `admin_bootstrap_token` 的 default 引用此常數（行為不變，只為防呆與測試共用字面值）。

## Phase 3: User Story 1 — 首位管理員自動佈建 (P1) 🎯 MVP

**Goal**: 提供 idempotent CLI 佈建首位 admin（OIDC 預建／本地密碼），供 Helm Job 與手動執行。
**Independent Test**: 乾淨 DB 以指定 email 執行 CLI → 該成員存在且具 admin 權限；重跑不重複、不報錯。

### Tests（先寫，須 Red）

- [ ] T003 [P] [US1] 建 `tests/integration/test_create_admin_cli.py`：乾淨 DB 以 `--provider google_oidc` 佈建 → `members` 出現該 email、`is_admin=True`、`provider=google_oidc`、`password_hash is None`、退出碼 0（FR-001/002, US1-AS1）。
- [ ] T004 [P] [US1] 於同檔加測：對已存在的指定 admin 重跑佈建 → 不新增列、退出碼 0、輸出含 "already exists"／"no change"（FR-003, US1-AS3, SC-002）。
- [ ] T005 [P] [US1] 於同檔加測：email 已存在但 provider 不符（既有 local_password，佈建要求 google_oidc）→ 非 0 退出、stderr 明確衝突訊息、既有成員不被變更（FR-005, Edge）。
- [ ] T006 [P] [US1] 於同檔加測：`--provider local_password` 佈建 → 建立成員、`is_admin=True`、輸出含一次性邀請連結（FR-002, US1-AS4）。
- [ ] T007 [P] [US1] 於同檔加測：已存在其他 admin、但指定 email 不存在 → 仍建立並升級指定 email（Edge）；以及「已存在、provider 相符、尚非 admin」→ 升級為 admin、退出 0。

### Implementation（測試轉 Green）

- [ ] T008 [US1] 新增 `src/ai_api/cli/create_admin.py`：argparse `--email`（必填）/`--provider`（預設 google_oidc）/`--name`；以 `get_sessionmaker()` 開 session，複用 `MemberService.create` + `set_is_admin`，依 `contracts/cli-create-admin.md` 的行為與退出碼矩陣實作；idempotent 與 provider 衝突處理；不洩漏密鑰；`asyncio.run` 入口比照 `cli/load_models.py`。
- [ ] T009 [US1] 跑 T003–T007 轉綠；確認輸出文案（繁中／英文）符合契約且不含 token 值。

## Phase 4: User Story 2 — 不安全預設憑證防呆 (P2)

**Goal**: production 訊號下、token 為空或預設值即拒絕啟動。
**Independent Test**: `create_app()` 在 cookie_secure=true + 預設／空 token 時 raise；自訂值與 dev 環境正常。

### Tests（先寫，須 Red）

- [ ] T010 [P] [US2] 建 `tests/unit/test_startup_admin_token_guard.py`：仿 `test_startup_crypto.py` 的 settings 快取隔離 fixture（`get_settings.cache_clear()`），覆蓋行為矩陣：(cookie_secure=true, 預設)→raise、(true, 空)→raise、(true, 自訂)→ok、(false, 預設)→ok（FR-006/007, US2-AS1~4, SC-003）。需設定有效 `PROVIDER_KEY_ENC_KEY` 以隔離出 token 這道防呆。
- [ ] T011 [P] [US2] 加測：raise 的訊息不含 token 實際值、且點出「預設／空、拒絕在 production 啟動」（R5、契約訊息要求）。

### Implementation

- [ ] T012 [US2] 在 `src/ai_api/main.py` `create_app()` 既有 fail-fast 區塊（`get_fernet()` 之後、`allowed_providers` 檢查附近）加入 token 防呆，使用 `config.DEFAULT_ADMIN_BOOTSTRAP_TOKEN` 與 `settings.cookie_secure`，依 `contracts/startup-token-guard.md` 實作。
- [ ] T013 [US2] 跑 T010–T011 轉綠；執行既有 admin/auth 測試確認 dev（cookie_secure=false）零退化（FR-011, SC-005）。

## Phase 5: User Story 3 — 部署與救援文件 (P3)

**Goal**: Helm 佈建編排 + 部署文件，讓維運者零提問完成部署。
**Independent Test**: `helm template` 渲染出 bootstrap-admin Job（排序在 migrate 後、envFrom secret、可停用）；文件可獨立帶領部署。

### Tests（先寫，須 Red）

- [ ] T014 [P] [US3] 在 `tests/integration/test_us4_helm_template.py` 加測：預設 values 下渲染含 `job: bootstrap-admin` 標籤的 Job、其 hook 為 `pre-install,pre-upgrade`、`hook-weight` 大於 migrate、有 `envFrom` secretRef、command 帶 `create_admin` 與 `--email`；並加測 `bootstrapAdmin.enabled=false` 時不渲染該 Job（FR-009）。

### Implementation

- [ ] T015 [US3] 在 `deploy/helm/ai-api/values.yaml` 新增 `bootstrapAdmin: {enabled, email, provider, displayName}` 區塊與註解（預設 enabled=false 或 email 空時 Job 不渲染，避免空 email 佈建）。
- [ ] T016 [US3] 新增 `deploy/helm/ai-api/templates/bootstrap-admin-job.yaml`：比照 `migration-job.yaml`，`hook-weight: "1"`，`command` 執行 `python -m ai_api.cli.create_admin --email {{ .Values.bootstrapAdmin.email }} --provider {{ .Values.bootstrapAdmin.provider }}`（含 displayName 時帶 `--name`），`envFrom` 同一 secret，僅在 `bootstrapAdmin.enabled` 且 `email` 非空時渲染。
- [ ] T017 [US3] 跑 T014 轉綠（若本機無 helm 則該測試 skip，比照既有）。
- [ ] T018 [P] [US3] 新增 `docs/deployment.md`（繁中）：必填機密清單（DATABASE_URL、PROVIDER_KEY_ENC_KEY、ADMIN_BOOTSTRAP_TOKEN、Google OAuth、baseUrl/cookieSecure）、首位 admin 佈建（OIDC／密碼兩路徑與登入後續）、預設 token 防呆行為與修正、全員失聯救援（重跑 CLI Job / `kubectl` 一次性 Job）、bootstrap token 定位為 break-glass。
- [ ] T019 [P] [US3] 在 `README.md` 新增「部署」段落連結到 `docs/deployment.md`（FR-010, US3-AS2）。

## Phase 6: Polish & Cross-cutting

- [ ] T020 全套測試 `uv run pytest -q` 綠、`uv run ruff check .` 無錯、`uv run mypy`（若 CI 有）無新錯；確認既有測試零退化（SC-005）。
- [ ] T021 依 `quickstart.md` 手動走一遍本地驗證（CLI OIDC/密碼、啟動防呆、helm template），記錄結果。
- [ ] T022 遷移測試：`DATABASE_URL="sqlite+aiosqlite:////tmp/x.db" uv run alembic upgrade head` 確認本功能未引入 schema 變更、既有遷移仍可乾淨套用。

## Dependencies

- T001 → 全部之前的基線。
- T002 阻擋 US2（T010、T012 依賴常數）。
- US1（T003–T009）、US2（T010–T013）相互獨立，可分別交付；US2 依賴 T002。
- US3（T014–T019）依賴 US1 的 CLI 存在（T008，Job 才有指令可呼叫）；文件（T018/T019）可與 helm（T015–T017）並行。
- Phase 6 在所有 story 後。

## MVP

US1（首位管理員佈建）即為可交付 MVP：沒有它系統部署後無人能進後台。US2、US3 為遞增強化。

## Parallel 範例

- T003–T007 同檔不同測試函式，邏輯獨立，可一次寫齊（標 [P] 指獨立性）。
- T018、T019（文件）與 T015–T016（helm）可並行。
