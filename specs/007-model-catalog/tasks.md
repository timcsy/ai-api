# Tasks: 階段 4 — Model Catalog + Multi-facet Filter

**Input**: Design documents from `/specs/007-model-catalog/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: TDD enforced — unit (filter / facet pure functions) → contract → integration。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`<repo-root>`

---

## Phase 1: Setup

- [ ] T001 [P] 建 dir `deploy/catalog/`
- [ ] T002 [P] 撰寫 `deploy/catalog/azure-2026-05.yaml`（依 data-model.md 範例；9 個 Azure OpenAI 主力模型：gpt-4o, gpt-4o-mini, o1-mini, o3-mini, text-embedding-3-small, text-embedding-3-large, dall-e-3, whisper-1, tts-1）

---

## Phase 2: Foundational

### Models + Migration

- [ ] T003 建立 `src/ai_api/models/model_catalog.py`：`ModelCatalog` ORM model（依 data-model.md schema；slug PK；JSON columns）
- [ ] T004 修改 `src/ai_api/models/__init__.py`：export `ModelCatalog`
- [ ] T005 建立 Alembic migration `alembic/versions/0006_model_catalog.py`：CREATE TABLE + INDEX on status
- [ ] T006 確認 `uv run alembic upgrade head` 通過；既有 167 tests 仍綠

### Pydantic schema for YAML

- [ ] T007 建立 `src/ai_api/services/model_catalog.py` 骨架：
  - `class ModelEntry(BaseModel)` — Pydantic schema 含 Literal enum 限制（依 research.md §4）
  - `filter_models(...)` 純函式 stub（先回傳 input 不變）
  - `compute_facets(...)` 純函式 stub（先回固定空 dict）

### require_active_member dependency

- [ ] T008 修改 `src/ai_api/api/deps.py`：新增 `require_active_member(session=Depends(get_session_from_cookie)) -> Member`；status != active → 403

**Checkpoint**：T006 既有 tests 綠 + T007/T008 import 成功。

---

## Phase 3: US1 — Filter by modality (P1)

**Goal**：透過 modality_output filter 找模型；detail 端點含 example_request。
**Independent Test**：`?modality_output=image` → 僅 dall-e-3；detail 含 example_request。

### Tests First

- [ ] T009 [US1] 建立 `tests/unit/test_model_filter.py`：覆蓋 `filter_models` boundary
  - 空 filter → 全 active 回傳
  - `modality_output={image}` → 僅 image-output models
  - `modality_input={text}, modality_output={text}` → text-only chat models
  - 大小寫不敏感（`Text` 與 `text` 等效）
- [ ] T010 [US1] 建立 `tests/contract/test_catalog_detail.py`：
  - 已存在 slug → 200 + example_request、ModelDetail schema
  - 不存在 slug → 404
  - URL-encoded slug `azure%2Fgpt-4o-mini` 正確 decode

### Impl

- [ ] T011 [US1] 實作 `services/model_catalog.py` `filter_models(models, *, criteria)` 純函式（依 research.md §2+§3）：list 欄位用 `set.issubset`；single 欄位 `==`；filter 值全 lowercase
- [ ] T012 [US1] 建立 `src/ai_api/api/catalog.py`：
  - `GET /catalog/models/{slug}` → 取 model；轉 ModelDetail；404 結構化錯誤
- [ ] T013 [US1] `src/ai_api/main.py`：註冊 `catalog.router`，prefix=`/catalog`

**Checkpoint**：T009-T010 全綠。

---

## Phase 4: US2 — Multi-AND filter (P1)

**Goal**：list 欄位重複 query key = AND（全具備）；跨欄位 AND。
**Independent Test**：`?capability=vision&capability=function-calling&cost_tier=low` → 僅 gpt-4o-mini。

### Tests First

- [ ] T014 [US2] 在 `tests/unit/test_model_filter.py` 加 case：
  - `capabilities={vision, function-calling}` → 必須全具備才命中
  - 缺一即排除
  - 跨欄位 AND（capability + cost_tier）
- [ ] T015 [US2] 建立 `tests/contract/test_catalog_list.py`：
  - 全部 active：seed 9 → list 回 9
  - vision+fn-calling+low → 1 個（SC-002）
  - 無命中 filter → 200 + []
  - `min_context_window` 過濾
  - `?include_deprecated=true` 含 deprecated
  - 預設不含 deprecated

### Impl

- [ ] T016 [US2] `api/catalog.py`：實作 `GET /catalog/models` 含 query parameters（依 openapi.yaml）；列表 query 大小寫 lowercase → 呼叫 `filter_models`
- [ ] T017 [US2] DB query helper：取所有 model（依 status 過濾 active vs include_deprecated），依 slug ORDER BY

**Checkpoint**：T014-T015 全綠 + SC-002 驗證。

---

## Phase 5: US3 — Facet API (P1)

**Goal**：`GET /catalog/filters` 回 faceted counts。
**Independent Test**：空 DB 與 9-model DB 兩態的 dimension key 集合相同。

### Tests First

- [ ] T018 [US3] 在 `tests/unit/test_model_filter.py` 加 `compute_facets` 測試：
  - 空 list → 所有 dimension 為 `{}`（穩定 schema）
  - 9 模型 seed → 期望計數
  - facet 排除 deprecated（呼應 FR-015）
- [ ] T019 [US3] 建立 `tests/contract/test_catalog_filters.py`：
  - 空 DB → 200 + 所有 dimension key 存在但為 `{}`
  - 9-model DB → 計數正確；deprecated 不計入

### Impl

- [ ] T020 [US3] `services/model_catalog.py`：實作 `compute_facets(models)` 純函式（依 research.md §6）；dimension keys 寫死保穩定
- [ ] T021 [US3] `api/catalog.py`：實作 `GET /catalog/filters`

**Checkpoint**：T018-T019 全綠 + SC-003 驗證。

---

## Phase 6: US4 — YAML upsert CLI (P2)

**Goal**：CLI 載入 YAML；idempotent；upsert by slug；未列出不刪除。

### Tests First

- [ ] T022 [US4] 建立 `tests/integration/test_catalog_yaml_upsert.py`：
  - 空 DB + 載入 → DB 多 N 筆
  - 同 YAML 再載 → row count 不變，但 updated_at 有更新
  - 改 description → 重載後 description 更新
  - YAML 移除某 model → 該 model 在 DB 仍存在（防 wipe）
  - YAML schema 錯誤（如 cost_tier=ultra）→ CLI exit 非 0 + DB 無變更
  - YAML 內 slug 重複 → 報錯

### Impl

- [ ] T023 [US4] 完整 `ModelEntry` Pydantic schema（research.md §4）— Literal enums + slug pattern
- [ ] T024 [US4] 建立 `src/ai_api/cli/load_models.py`：
  - 讀 YAML → 對每 entry validate → 在 transaction 內 get-or-create+update
  - 失敗 → rollback + stderr 明確訊息 + exit 1
  - 成功 → 印 `loaded: inserted=X updated=Y`
- [ ] T025 [US4] 確認 YAML 內所有 enum 值都會被正規化小寫（YAML 寫 `Text` 也接受）

**Checkpoint**：T022 全綠 + SC-004 驗證。

---

## Phase 7: US5 — Deprecation isolation (P2)

**Goal**：deprecated 預設不出現在列表；detail 仍可查；含 deprecation_note。

### Tests First

- [ ] T026 [US5] 在 `tests/integration/test_catalog_deprecation.py` 建立：
  - seed 一個 active + 一個 deprecated
  - default list 只回 active
  - `?include_deprecated=true` 兩個都回
  - detail 直接查 deprecated slug → 200 含 deprecation_note
  - facet 計數排除 deprecated

### Impl

說明：US2 T017 已實作 include_deprecated 開關；本階段測 deprecation_note
欄位 + facet 排除行為。

- [ ] T027 [US5] 確認 ModelDetail schema 含 `deprecation_note`（已在 T012 處理）
- [ ] T028 [US5] 確認 facet 計算只跑 active models（與 list endpoint 一致）

**Checkpoint**：T026 全綠 + SC-005 驗證。

---

## Phase 8: Polish

- [ ] T029 [P] 跑 `uv run pytest -q` 確認既有 167 tests + 新增測試全綠
- [ ] T030 [P] 跑 `uv run ruff check .` + `uv run mypy src/ai_api` 全綠
- [ ] T031 [P] 建立 `docs/model-catalog.md`：YAML 維護 SOP + PriceList 對齊規則
- [ ] T032 [P] 更新 `knowledge/vision.md`：階段 4 SC checkbox 由 `[ ]` → `[x]`
- [ ] T033 PR 描述附 quickstart §3+§4+§5 執行紀錄

---

## Dependencies

```
Phase 1 (Setup: dir + YAML content)
   │
   ▼
Phase 2 (Foundational: model + migration + service stub + active member dep)
   │
   ├─→ Phase 3 (US1 — modality filter + detail)
   │      │
   │      ├─→ Phase 4 (US2 — multi-AND filter; depends on US1 filter_models)
   │      └─→ Phase 5 (US3 — facet API; uses same filter pure function)
   │
   ├─→ Phase 6 (US4 — YAML upsert CLI; depends on Phase 2 model)
   │
   └─→ Phase 7 (US5 — deprecation isolation; depends on US2+US4)
        │
        ▼
   Phase 8 Polish
```

**Story dependencies**：
- US1 是基礎（filter_models pure function + detail endpoint + router）
- US2 直接擴 US1 的 query params + filter logic
- US3 用同一個 filter_models 結果 + compute_facets
- US4 獨立（CLI + Pydantic）；只依賴 Phase 2 ORM
- US5 依賴 US2 (include_deprecated 開關) + US4 (status 欄位 upsert)

---

## Parallel Execution Opportunities

- **Phase 1**：T001/T002 並行
- **Phase 2**：T003-T005 是循序（同檔 / 依賴關係）；T007/T008 並行
- **Phase 3-5 (US1/US2/US3)**：純函式部分可並行寫測試 + impl；但都改 `services/model_catalog.py` 與 `api/catalog.py`，需 sequential commit
- **Phase 6 (US4)**：與 US1-US3 完全獨立，可並行開發
- **Phase 8**：T029-T032 全部並行

---

## Implementation Strategy

### MVP

**Phase 1+2+3** 完成 = MVP（US1：modality filter + detail）。
**+ Phase 4+5** = 完整 P1 stories（multi-AND + facet）。
**+ Phase 6+7** = 上線就緒。

### TDD Discipline

每個 user story：unit/contract/integration test commit → impl commit。
git history 顯示「test < impl」順序。

### Risk Hot Spots

1. **filter 大小寫處理位置不一致** → spec 明定：YAML 載入時 lowercase + API
   query 進 set 前 lowercase；filter_models 內**不**再做轉換（單一責任）
2. **FastAPI Query 重複 key 解析** → `Query(default=None, alias="capability")` 配
   `list[str] | None`；測試覆蓋 `?capability=A&capability=B` → `["A","B"]`
3. **slug URL-encoding** → 測試覆蓋 path param `azure%2Fgpt-4o-mini`
4. **JSON column 在 SQLite vs Postgres 行為差異** → 整合測試走 testcontainers
   Postgres + SQLite 兩態
5. **YAML 內 example_request 巢狀 dict 太深** → schema 不驗結構，CLI 直接存

---

## Format Validation

✅ 全部 33 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-7 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
