# Tasks: 模型目錄 admin 體驗整合 + 充分利用 LiteLLM

**Input**: Design documents from `/specs/034-catalog-admin-consolidation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-and-adapter.md, quickstart.md

**Tests**: 嚴格 TDD（憲章 I）。先紅後綠。外部依賴（litellm）以 bundled 真實值 + 既有 mock 驗，不打真網路。

**Organization**: 依 User Story 分組。後端 `src/ai_api/`、`tests/`；前端 `frontend/src/`。**重用階段 23 端點與 `LiteLLMUpdateDiff`，0 新端點、0 migration、0 套件。**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔、無未完成相依）
- **[Story]**: US1–US4；Setup/Foundational/Polish 無標籤

---

## Phase 1: Setup

- [X] T001 跑基準綠：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、`npm --prefix frontend run test && lint && typecheck && build` 全綠；確認階段 23 基建（`litellm_registry`、`litellm_sync`、`LiteLLMUpdateDiff`、`/admin/catalog/litellm/*` 端點）可重用、本階段**不新增端點/migration/套件**。

---

## Phase 2: Foundational（後端 adapter 擴充——US1/US4 的根基）

**Purpose**: 能力映射擴充 + `litellm_sync.raw` 落地，是詳情頁徽章/唯讀面板/充分利用的資料根基。

### Tests First (Red)

- [X] T002 [P] 在 `tests/unit/test_litellm_registry.py` 加：`_capabilities`/`metadata_from_entry` 對含 `supports_prompt_caching=true` 的 entry → capabilities 含 `prompt_caching`；`supports_reasoning=true` → 含 `reasoning`；`supports_pdf_input`/`web_search`/`audio`/`video`/`structured_output`/`computer_use` 各對應；皆無 → `["chat"]`；既有 vision/function_calling 不回歸（先 Red）。
- [X] T003 [P] 在 `tests/contract/test_admin_create_with_litellm.py` 加：建立 `azure/gpt-4o` 對齊模型 → `litellm_sync.raw.max_output_tokens == 16384`、`raw.mode == "chat"`、`raw` 含價格/能力旗標（先 Red）。
- [X] T004 跑 T002–T003 確認 **全 Red**。

### Implementation (Green)

- [X] T005 改 `src/ai_api/services/litellm_registry.py` `_capabilities`：擴到 ~10 個決策旗標（chat/function_calling/vision/reasoning/pdf/prompt_caching/web_search/audio/video/structured_output/computer_use），只輸出為真者，皆無回 `["chat"]`。
- [X] T006 改 `src/ai_api/api/admin_catalog.py` `_build_litellm_sync`：`litellm_sync` 多存 `raw`＝該 key 的**完整 litellm entry**（`litellm_registry.bundled().get(key)`）。
- [X] T007 改 `admin_litellm_apply`：採納套用後一併更新 `litellm_sync.raw` 為最新 entry（與 snapshot/imported_version 同步）。
- [X] T008 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**（含成員端目錄 facet）。

**Checkpoint**: adapter 擴充上線、零回歸。可進 US1。

---

## Phase 3: US1 — 詳情頁單一中樞 + 來源徽章（Priority: P1）🎯 MVP

**Goal**: 模型詳情頁每個可同步欄位顯示來源徽章（litellm/借用/手動）。

**Independent Test**: LiteLLM 帶入的模型詳情頁 → 每欄有徽章；手改欄顯示手動；純手動模型不誤導。

### Tests First (Red)

- [X] T009 [P] [US1] 新增 `frontend/src/__tests__/field-source-badge.test.tsx`：`<FieldSourceBadge source="litellm|borrowed|manual"/>` 各顯示正確文字/樣式。
- [X] T010 [US1] 在 `frontend/src/__tests__/`（model-detail 對應測試或新檔）加：渲染 field_sources 含 litellm+manual 的模型詳情 → 對應欄位徽章正確；`litellm_sync=null` 的模型不顯示誤導徽章（先 Red）。

### Implementation (Green)

- [X] T011 [P] [US1] 新增 `frontend/src/components/field-source-badge.tsx`（依 `source` 顯示 LiteLLM／借用／手動 小徽章）。
- [X] T012 [US1] 改 `frontend/src/routes/admin/model-detail.tsx`：`CatalogModel` 型別加 `litellm_sync`；在 context_window / modality / capabilities 顯示處掛 `<FieldSourceBadge>`（讀 `litellm_sync.field_sources`）。
- [X] T013 [US1] 跑 T009–T010 確認 **全 Green**；`lint`/`typecheck`/`build` 綠。

**Checkpoint**: US1 可獨立交付——詳情頁看得出每欄來源（MVP）。

---

## Phase 4: US2 — 檢查更新前移到詳情頁（Priority: P1）

**Goal**: 「檢查 LiteLLM 更新」入口移到詳情頁，掛載既有 `LiteLLMUpdateDiff`。

**Independent Test**: 詳情頁有「檢查更新」→ 點開列 metadata + 價格差異 → 勾選採納。

### Tests First (Red)

- [X] T014 [US2] 在 model-detail 測試加：詳情頁有「檢查 LiteLLM 更新」入口；點擊呼叫 `litellm-check`（mock fetch）並渲染 diff（先 Red）。

### Implementation (Green)

- [X] T015 [US2] 改 `frontend/src/routes/admin/model-detail.tsx`：加「檢查 LiteLLM 更新」按鈕 + 掛載既有 `LiteLLMUpdateDiff`（slug=本模型，onApplied → invalidate 模型查詢）。
- [X] T016 [US2] （收尾）`frontend/src/routes/admin/catalog-manage.tsx`：移除列表列的「檢查更新」按鈕（避免兩處；詳情頁為唯一中樞）；更新對應測試。
- [X] T017 [US2] 跑 T014 確認 **Green**。

**Checkpoint**: US2 測試全綠；檢查更新在詳情頁。

---

## Phase 5: US3 — 退役價格「常見範本」改 LiteLLM 建議（Priority: P1）

**Goal**: `prices.tsx` 移除硬編 `TEMPLATES`，改用 LiteLLM 建議價。

**Independent Test**: 價格新增畫面無舊範本；有「從 LiteLLM 帶入建議價」；帶入後手改仍 append。

### Tests First (Red)

- [X] T018 [US3] 在 `frontend/src/__tests__/`（prices 對應測試）加：價格新增畫面**無**舊範本標籤（如「Azure / OpenAI — gpt-4o」）；有「從 LiteLLM 帶入建議價」入口；帶入（mock `/litellm/suggest`）填入建議價、可手改（先 Red）。

### Implementation (Green)

- [X] T019 [US3] 改 `frontend/src/routes/admin/prices.tsx`：移除 `TEMPLATES` 陣列與「從常見範本帶入」下拉；改為「從 LiteLLM 帶入建議價」——用對話框 provider+model 組 `{provider}/{model}` key 呼叫 `GET /admin/catalog/litellm/suggest/{key}`，填入 `suggested_price`（每 1M 換算沿用畫面既有單位邏輯），查無 key 優雅提示、不阻擋手填。
- [X] T020 [US3] 跑 T018 確認 **Green**。

**Checkpoint**: US3 測試全綠；價格帶入統一到 LiteLLM。

---

## Phase 6: US4 — 充分利用 LiteLLM（唯讀原始資訊面板）（Priority: P2）

**Goal**: 詳情頁唯讀「LiteLLM 原始資訊」面板顯示 `litellm_sync.raw` 全欄。（能力擴充 + max_output_tokens 已於 Foundational 落地。）

**Independent Test**: 有 raw 的模型 → 面板展開見 mode/max_output_tokens…；無 raw → 無面板。

### Tests First (Red)

- [X] T021 [P] [US4] 新增 `frontend/src/__tests__/litellm-raw-panel.test.tsx`：`<LiteLLMRawPanel raw={{mode,max_output_tokens,...}}/>` 展開顯示欄位；`raw` 為空/undefined → 不渲染。

### Implementation (Green)

- [X] T022 [P] [US4] 新增 `frontend/src/components/litellm-raw-panel.tsx`（可折疊唯讀面板，列出 `raw` 的 key/value）。
- [X] T023 [US4] 改 `frontend/src/routes/admin/model-detail.tsx`：在詳情頁掛 `<LiteLLMRawPanel raw={model.litellm_sync?.raw}/>`（無 litellm_sync 不顯示）。
- [X] T024 [US4] 跑 T021 確認 **Green**。

**Checkpoint**: US4 測試全綠；充分利用 LiteLLM 資訊。

---

## Phase 7: Polish & Cross-Cutting

- [X] T025 後端全套 `uv run pytest tests/` 零回歸（adapter 擴充 + 既有目錄/價目/計費/proxy/成員端 facet）；`ruff` + `mypy` 零警告。
- [X] T026 前端全綠：`npm --prefix frontend run test && lint && typecheck && build`；詳情頁 + 價格畫面 360px RWD 不溢出。
- [X] T027 [P] 知識/文件：`knowledge/vision.md` 階段 24 → ✅；若有新教訓（能力 sink 擴充、UI 中樞收斂）補 `knowledge/experience.md`。
- [ ] T028 commit + push + 開 PR；push 前 ruff + 前端 build；**特別檢視 0 migration/0 端點、能力 sink 零回歸、退役範本無殘留**；CI 全綠後 squash merge 到 main。
- [ ] T029 main image build 綠後 `helm upgrade`（backend + frontend 新 sha；**無 migration → 不加 migrationJob.enabled**）；部署後驗：詳情頁徽章/檢查更新/唯讀面板可用、價格 LiteLLM 帶入可用、壞 token → 401 零回歸。

---

## Dependencies & Execution Order

```
Setup(T001)
  └─ Foundational(T002–T008)         # adapter 能力擴充 + raw 落地，US1/US4 根基
       ├─ US1(T009–T013) 🎯 MVP      # 詳情頁來源徽章
       │    ├─ US2(T014–T017)        # 檢查更新前移（同詳情頁檔）
       │    └─ US4(T021–T024)        # 唯讀 raw 面板（依賴 Foundational 的 raw）
       └─ US3(T018–T020)             # 退役價格範本（獨立檔 prices.tsx，可平行於 US1 之後）
            └─ Polish(T025–T029)
```

- **US1/US2/US4 同動 `model-detail.tsx`** → US1 先（型別 + litellm_sync），US2/US4 接著（同檔需序列）。
- **US3 獨立**（`prices.tsx`，與詳情頁不同檔）→ Foundational 後可平行於 US1。
- **US4 唯讀面板依賴 Foundational 的 `raw`**。

## Parallel Opportunities

- Foundational：T002（能力）‖ T003（raw）測試平行。
- US1：T009（badge 測試）‖ T011（badge 元件）；T012（詳情頁）序後。
- US4：T021‖T022（面板測試/元件）；T023 序後。
- US3 整段可平行於 US1（不同檔）。
- Polish：T027 可平行。

## Implementation Strategy

- **MVP = Foundational + US1**（T001–T013）：詳情頁看得出每欄來源（可獨立交付）。
- **整合完成 = + US2 + US3**：檢查更新前移 + 退役價格範本（三畫面收斂）。
- **充分利用 = US4**：唯讀原始資訊面板（能力擴充已在 Foundational）。
- 每階段結束跑該階段測試；T025–T026 全量綠才 T028 push、CI 綠才 T029 部署（無 migration）。
