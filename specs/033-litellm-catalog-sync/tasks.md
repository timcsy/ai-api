# Tasks: 模型目錄 ↔ LiteLLM 登錄表對接

**Input**: Design documents from `/specs/033-litellm-catalog-sync/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-litellm-sync.md, quickstart.md

**Tests**: 嚴格 TDD（憲章 I）。每個 User Story 先寫/改失敗測試（紅）再實作（綠）。外部依賴（litellm 線上抓）以 **mock** 驗 timeout + 回退，不打真網路（憲章 III）。

**Organization**: 任務依 User Story 分組。後端 `src/ai_api/`、`alembic/versions/`、`tests/`；前端 `frontend/src/`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔、無未完成相依）
- **[Story]**: US1–US4；Setup/Foundational/Polish 無標籤

---

## Phase 1: Setup

- [X] T001 跑基準綠（實作前對照）：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、`npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**不新增套件**、下一個 migration 為 `0018`、`litellm`/`PriceList`/`ModelCatalog`/`admin_catalog` 既有基建可復用。

---

## Phase 2: Foundational（阻斷所有 User Story 的前置：schema + adapter 核心）

**Purpose**: `litellm_sync` 欄位 + litellm adapter service 是 US1–US4 全部的根基；先做完並固化零回歸。

### Tests First (Red)

- [X] T002 新增 `tests/integration/test_litellm_sync_migration.py`（Postgres）：`alembic upgrade head` → 斷言 `model_catalog.litellm_sync`（nullable JSON）建出；既有目錄/價目/計費**零回歸**、既有列 `litellm_sync` 為 null（先 Red）。
- [X] T003 [P] 新增 `tests/unit/test_litellm_registry.py`：`litellm_registry.lookup("azure/gpt-4o")` 回 context_window=128000、modality 含 text/image、capabilities 含 vision/function_calling；`suggest_price` 回 input `0.0025`/output `0.01`/cached `0.00125`（per-token×1000）；查無 key 回 None（先 Red）。
- [X] T004 跑 T002–T003 確認 **全 Red**。

### Implementation (Green)

- [X] T005 改 `src/ai_api/models/model_catalog.py`：加 `litellm_sync: Mapped[dict | None]`（JSON, nullable, default None）。
- [X] T006 新增 `alembic/versions/0018_model_litellm_sync.py`：`add_column` `litellm_sync`（nullable JSON）；`downgrade` drop 欄。**additive、非改 PK**。
- [X] T007 新增 `src/ai_api/services/litellm_registry.py`：adapter——`lookup(key)`（讀 bundled `litellm.model_cost` → 我們的 metadata dict，欄位對應見 data-model）、`suggest_price(key)`（per-token×1000 → Decimal）、`search(q, limit)`、`current_version()`（`importlib.metadata.version('litellm')`）、`fetch_latest(timeout)`（`litellm.get_model_cost_map(url)`，例外/逾時回 None）、`diff(catalog_model, latest_map)`（逐欄 old→new + source）。集中所有 litellm 讀取/對應於此一處。
- [X] T008 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**。

**Checkpoint**：schema + adapter 上線、既有零回歸。可進 US1。

---

## Phase 3: US1 — 新增模型時一鍵帶入（Priority: P1）🎯 MVP

**Goal**: admin 搜 LiteLLM key → 帶入 metadata + 建議價、slug 預設＝key 可改。

**Independent Test**: 搜 `gpt-4o` → 選 `azure/gpt-4o` → 表單自動填 + slug 預設 → 存檔 → 模型落地 + 產生 litellm 來源價目。

### Tests First (Red)

- [X] T009 [P] [US1] 新增 `tests/contract/test_admin_litellm_search.py`：`GET /admin/catalog/litellm/search?q=gpt-4o` 命中 `azure/gpt-4o`（含 provider/mode/context/建議價）；`limit` 生效。
- [X] T010 [P] [US1] 新增 `tests/contract/test_admin_litellm_suggest.py`：`GET /admin/catalog/litellm/suggest/azure/gpt-4o` 回 metadata + 建議價 + slug_default；查無 key → 404 `litellm_model_not_found`。
- [X] T011 [US1] 新增 `tests/contract/test_admin_create_with_litellm.py`：`POST /admin/catalog/models` 帶 `litellm_sync` + 建議價 → 模型 `litellm_sync` 落地、欄位來源=litellm；產生一筆 `PriceList` 帶 `source_note=litellm@<ver>`。
- [X] T012 [US1] 跑 T009–T011 確認 **全 Red**。

### Implementation (Green)

- [X] T013 [US1] 在 `src/ai_api/api/admin_catalog.py` 加 `GET /admin/catalog/litellm/search` 與 `GET /admin/catalog/litellm/suggest/{key:path}`（呼叫 `litellm_registry`，讀 bundled）。
- [X] T014 [US1] 改 `src/ai_api/api/schemas.py`：`ModelCatalogCreate` 加選填 `base_model_key: str | None`、`litellm_sync: {field_sources, snapshot, imported_version} | None`。
- [X] T015 [US1] 改 `src/ai_api/api/admin_catalog.py` `admin_create_model`：落 `litellm_sync`；若帶建議價沿用既有價目建立流程 append `PriceList`（`source_note=litellm@<ver>`）。
- [X] T016 [US1] 跑 T009–T011 確認 **全 Green**。
- [X] T017 [P] [US1] 前端：新增 `frontend/src/components/litellm-model-picker.tsx`（搜尋 `/admin/catalog/litellm/search` → 選 → 回填 metadata + 建議價 + slug 預設）；接進 `frontend/src/routes/admin/model.tsx`（或 catalog-manage）新增模型表單。
- [X] T018 [P] [US1] 前端 vitest：`frontend/src/__tests__/litellm-model-picker.test.tsx` 驗搜尋 → 選 → 表單自動填 + slug 可改；lint/typecheck/build 綠。

**Checkpoint**：US1 可獨立交付——登錄表內模型免手打建立（MVP）。

---

## Phase 4: US2 — 自訂 deployment 借對照基礎模型（Priority: P1）

**Goal**: 查無 slug（如 `azure/gpt-5.4`）指定對照基礎模型借 metadata、價格自訂。

**Independent Test**: 自訂 slug + `base_model_key=azure/gpt-4o` → 借入 metadata（source=borrowed）、slug 維持自訂、價自填。

### Tests First (Red)

- [X] T019 [US2] 在 `tests/contract/test_admin_create_with_litellm.py` 加：自訂 slug `azure/gpt-5.4` + `base_model_key=azure/gpt-4o` → 借入 metadata、`field_sources` 標 `borrowed`、slug 維持自訂；未帶價則不自動帶基礎模型價。
- [X] T020 [US2] 跑 T019 確認 **Red**。

### Implementation (Green)

- [X] T021 [US2] 改 `admin_create_model`（+ `litellm_registry`）：`base_model_key` 指定時用其 metadata 填、來源標 `borrowed`、slug 用 payload 自訂值；價格僅用 payload（不帶基礎模型價）。
- [X] T022 [US2] 跑 T019 確認 **Green**。
- [X] T023 [P] [US2] 前端：`litellm-model-picker.tsx` 支援「自訂 slug + 對照基礎模型」模式（選基礎模型借 metadata、slug 欄可自填、價格欄留白自填）；對應 vitest。

**Checkpoint**：US2 測試全綠。

---

## Phase 5: US3 — 來源標記與匯入快照（Priority: P1）

**Goal**: 每個可同步欄記來源（litellm/borrowed/manual）+ 匯入快照；手改轉 manual。

**Independent Test**: 帶入後存檔 → 欄位來源正確、有 snapshot；PATCH 某欄 → 該欄轉 manual。

### Tests First (Red)

- [X] T024 [US3] 在 `tests/contract/test_admin_create_with_litellm.py` 加：建立後 `litellm_sync.field_sources`/`snapshot` 正確；`PATCH /admin/catalog/models/{slug}` 改某可同步欄 → 該欄 `field_sources` 轉 `manual`、snapshot 不變。
- [X] T025 [US3] 跑 T024 確認 **Red**。

### Implementation (Green)

- [X] T026 [US3] 改 `admin_update_model`（`schemas.py` `ModelCatalogUpdate` + `admin_catalog.py`）：偵測可同步欄變更 → 更新 `litellm_sync.field_sources[field]="manual"`（保留 snapshot）。
- [X] T027 [US3] 跑 T024 確認 **Green**。
- [X] T028 [P] [US3] 前端：model 詳情/管理頁各可同步欄顯示**來源徽章**（litellm / 借用 / 手動）；對應 vitest。

**Checkpoint**：US3 測試全綠（US4 的前提就緒）。

---

## Phase 6: US4 — 一鍵檢查 LiteLLM 更新並選擇性採納（Priority: P2）

**Goal**: 線上抓最新（timeout 回退 bundled）→ 逐欄 old→new + 來源 → 選擇性採納；採納價 append 版本。

**Independent Test**: mock live 新值 → check 列 diffs → apply 勾選欄 → 套用、價格 append、manual 欄不動。

### Tests First (Red)

- [X] T029 [US4] 新增 `tests/contract/test_admin_litellm_check.py`：mock `litellm_registry.fetch_latest` 回新值 → `POST …/{slug}/litellm-check` 回 `source:"live"` + diffs（changed + source）；mock 丟例外/逾時 → `source:"bundled-fallback"` 仍回 diffs。
- [X] T030 [US4] 新增 `tests/contract/test_admin_litellm_apply.py`：`POST …/{slug}/litellm-apply {fields:[context_window]}` → 只更新該欄 + snapshot/imported_version；採納 `price.input_per_1k` → **新增一筆 `PriceList`** 帶 litellm source_note、舊版本仍在、`current_price_map` 取最新；`fields` 含 manual 欄 → 不套用該欄。
- [X] T031 [US4] 跑 T029–T030 確認 **全 Red**。

### Implementation (Green)

- [X] T032 [US4] 在 `src/ai_api/api/admin_catalog.py` 加 `POST /admin/catalog/models/{slug:path}/litellm-check`：`fetch_latest(timeout)` 失敗回退 bundled（標 source）+ log；`diff()` 逐欄；回 contract 形狀。
- [X] T033 [US4] 加 `POST /admin/catalog/models/{slug:path}/litellm-apply`：套用選定且**非 manual** 的 metadata 欄（更新 model + snapshot + imported_version、source=litellm）；`price.*` 欄 → append `PriceList`（`source_note=litellm@<ver>`，不覆寫）；留稽核。
- [X] T034 [US4] 跑 T029–T030 確認 **全 Green**。
- [X] T035 [P] [US4] 前端：新增 `frontend/src/components/litellm-update-diff.tsx`（逐欄 old→new + 來源徽章 + 勾選採納，manual 欄不可勾或明示）；「檢查 LiteLLM 更新」入口接進 `frontend/src/routes/admin/model-detail.tsx`（或 catalog-manage）；對應 vitest。

**Checkpoint**：US4 測試全綠。

---

## Phase 7: Polish & Cross-Cutting

- [X] T036 跑 `uv run pytest tests/` 全套零回歸（含 migration 0018 + 既有目錄/價目/計費/proxy）；`uv run ruff check . && uv run mypy src/` 零警告。
- [X] T037 前端全綠：`npm --prefix frontend run test && lint && typecheck && build`；360px RWD 不溢出（picker / diff 對話框）。
- [X] T038 [P] 知識/文件：`knowledge/vision.md` 加階段 23 → ✅；若有新教訓（litellm 欄位對應、線上抓 egress）補 `knowledge/experience.md`；`knowledge/design/` 可選加 model-catalog↔litellm 對接設計頁。
- [X] T039 commit + push + 開 PR；push 前 ruff + 前端 build；**特別檢視 migration 0018 additive、線上抓 timeout/回退、價格 append-only**；等 CI 全綠後 squash merge 到 main。
- [X] T040 main image build 綠後 `helm upgrade`（**含 `--set migrationJob.enabled=true` 套 0018** + 新 backend sha + frontend sha）；**部署後驗 egress**：admin 按「檢查更新」回 `source:"live"`（或環境擋外連時回 `bundled-fallback` 不卡）；既有 proxy/計費零回歸（壞 token → 401）。

---

## Dependencies & Execution Order

```
Setup(T001)
  └─ Foundational(T002–T008)         # schema 0018 + adapter，阻斷所有 US
       ├─ US1(T009–T018) 🎯 MVP      # search/suggest/建立帶入 + picker
       │    ├─ US2(T019–T023)        # 對照基礎模型（擴充建立流程）
       │    └─ US3(T024–T028)        # 來源標記 + 手改轉 manual
       │         └─ US4(T029–T035)   # 檢查更新 + 選擇性採納（依賴 US3 的 field_sources）
       └─ Polish(T036–T040)
```

- **US2/US3 依賴 US1**：都擴充建立/更新流程與 picker。
- **US4 依賴 US3**：選擇性採納要靠 `field_sources` 分辨 litellm vs manual。
- **adapter（T007）是全功能核心**：search/suggest/check/apply 都呼叫它。

## Parallel Opportunities

- Foundational：T003（adapter 測試）與 T002（migration 測試）平行。
- US1 tests：T009、T010 `[P]`；T011 依賴 schema。
- 前端元件 T017、T023、T028、T035 與各自後端不同檔，可在該 US 後端綠後平行。
- Polish：T038 可平行。

## Implementation Strategy

- **MVP = Foundational + US1**（T001–T018）：登錄表內模型免手打建立，可獨立交付。
- **完整帶入體驗 = + US2 + US3**：自訂 deployment 對照 + 來源標記（三者皆 P1）。
- **維護面 = US4**：一鍵檢查更新 + 選擇性採納（P2）。
- 每階段結束跑該階段測試確認綠；T036–T037 全量綠才 T039 push、CI 綠才 T040 部署（含 migration + egress 驗證）。
