# Tasks: 統一端點架構（資料驅動 registry）+ moderation / search / image_edit

**Feature**: `042-endpoint-registry` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/endpoints.md / quickstart.md

**測試策略**：Constitution I（Test-First）→ 引擎/Meter/IOShape 單元先寫；三新端點先寫失敗 contract；**重構以「既有測試一行斷言不改、全綠」為驗收金鋼罩**（行為不變的證明）。

**路徑慣例**：後端 `src/ai_api/proxy/`、測試 `tests/`、前端 `frontend/src/`。

**核心約束**：既有 5 端點（embeddings/ocr/images/rerank/audio）外部行為**零回歸**；串流端點（`router.py` chat、`responses.py`）**零觸碰**；**零 migration（0019 不變）、零套件**；三軸正交（IOShape × Meter × call）。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract/test_{embeddings,ocr,images,rerank,audio}.py -q && ruff check .` 全綠（重構金鋼罩的基準）；確認 `alembic heads`=`0019`。

---

## Phase 2: Foundational（統一執行引擎——所有 US 的阻塞前置）

> 引擎 + 三軸抽象是 US1（遷移既有）與 US2–4（新端點）的共同地基，必須先完成。

- [X] T002 [P] 寫 `tests/unit/test_endpoint_engine.py`（先失敗）：(a) `TokenMeter.measure` 從 `payload.usage` 取 token、`UnitMeter("page", fn).measure` 算 quantity；(b) IOShape `json` parse `{model, …}`、`binary` respond 回 `Response(bytes, media_type)`、`multipart` parse `Form+File`；(c) 引擎對一個假 spec（mock call）跑完整流程→回應 + 記一筆。
- [X] T003 新增 `src/ai_api/proxy/endpoint_spec.py`：`EndpointSpec` dataclass（`path, io, required, call, meter, model_field`）；`IOShape`（input∈json/multipart × output∈json/binary，含 `parse(request)->(model, fields)` 與 `respond(result)`）；`Meter`（`TokenMeter`、`UnitMeter(unit, quantity_fn)`，各回計量 + 用 `calculate_cost`/`calculate_unit_cost` 算 cost）。
- [X] T004 新增 `src/ai_api/proxy/engine.py`：`run_endpoint(spec, request, authorization, session, **parts)`——bearer → `spec.io.parse` → 驗 `required`（缺→400）→ `run_preflight` → `spec.call(fields, resolved, upstream_model)`（except→`upstream_error` 502）→ `spec.meter.measure` → `record_call` → `spec.io.respond`；錯誤統一 `record_and_respond`（沿用 `_outcome_for_code`/`_error_payload`/`redact_string`）。令 T002 轉綠。

**Checkpoint**：引擎可對任意 spec 執行（用假 spec 驗證）= 架構成立。

---

## Phase 3: User Story 1 — 既有端點零回歸遷移到 registry（P1）🎯 MVP

**Goal**：5 個非串流端點變成 registry 內的 `EndpointSpec`，刪除複製檔，**外部行為逐字不變**。

**Independent Test**：`test_{embeddings,ocr,images,rerank,audio}.py` 斷言不改、全綠;串流端點測試全綠。

- [X] T005 [US1] 新增 `src/ai_api/proxy/registry.py`：先放 **embeddings** 一筆 `EndpointSpec`（json→json、`TokenMeter`、`call=aembedding(model, input)`、required=`["input"]`）+ `build_router()` 把 spec 們組成 `APIRouter`。改 `main.py` mount `build_router()`、移除 `embeddings_router`；刪 `proxy/embeddings.py`。跑 `test_embeddings.py` **斷言不改**轉綠（驗證引擎接得起一個真端點）。
- [X] T006 [US1] 在 `registry.py` 補 **ocr / images / rerank** 三筆 spec（ocr: json→json `UnitMeter("page", len(pages))` `aocr(model, document)` req=`["document"]`；images: json→json `TokenMeter` `aimage_generation(model, prompt)` req=`["prompt"]`；rerank: json→json `UnitMeter("query",1)` `arerank(model, query, documents)` req=`["query","documents"]`）；`main.py` 移除三個 router；刪三個檔。跑對應既有測試**不改斷言**轉綠。
- [X] T007 [US1] 在 `registry.py` 補 **audio**：`/audio/speech`（json→**binary** `UnitMeter("character", len(input))` `aspeech(model, input, voice)` req=`["input"]`）+ `/audio/transcriptions`（**multipart**→json `TokenMeter` `atranscription(model, file)` req=`["file"]`）；`main.py` 移除 `audio_router`；刪 `proxy/audio.py`。跑 `test_audio.py` **不改斷言**轉綠——**這驗證 binary 輸出 + multipart 輸入兩種形態在引擎內成立**。
- [X] T008 [US1] 確認 `router.py`（chat）、`responses.py` **完全未動**、其測試全綠（串流零觸碰）。

**Checkpoint**：US1 可獨立驗收（5 端點遷移完、既有測試零修改全綠 = 重構成功、架構驗證）。

---

## Phase 4: User Story 2 — moderation 端點（P2）

**Goal**：`POST /v1/moderations`——加一筆 spec + 一個 wrapper 即上線（驗證「加端點=加資料」）。

**Independent Test**：mock `amoderation` 回 `{...,usage}` → 200 + token 計費歸戶。

- [X] T009 [P] [US2] 寫 `tests/contract/test_moderation.py`（先失敗）：(a) mock `upstream.amoderation` 回帶 usage → 200 + 記 token 計費歸戶；(b) 缺 input → 400；(c) 壞 token → 401；(d) 範圍外模型 → 403；(e) mock raise → 502 + 記。
- [X] T010 [US2] 改 `src/ai_api/proxy/upstream.py`：加 `amoderation(model, input, …)` wrapper；在 `registry.py` 加一筆 moderation spec（`/moderations`、json→json、`TokenMeter`、`call=amoderation(model, input)`、req=`["input"]`）。令 T009 轉綠。

**Checkpoint**：US2 可獨立驗收（程式增量＝1 wrapper + 1 spec）。

---

## Phase 5: User Story 3 — search 端點（P2）

**Goal**：`POST /v1/search`——per-query，且 `call` 把 provider 對映成 `search_provider`（驗證參數對映各異）。

**Independent Test**：mock `asearch` 回結果 + seed 每查詢價 → 200 + 記 `unit="query"`。

- [X] T011 [P] [US3] 寫 `tests/contract/test_search.py`（先失敗）：(a) mock `upstream.asearch` 回結果 + seed 每查詢價 → 200 + 記 `CallRecord(unit="query", quantity=1, cost=每查詢價, 歸戶)`；(b) 無價 → 0；(c) 缺 query → 400；(d) 壞 token → 401；(e) mock raise → 502 + 記。
- [X] T012 [US3] 改 `src/ai_api/proxy/upstream.py`：加 `asearch(search_provider, query, …)` wrapper；在 `registry.py` 加 search spec（`/search`、json→json、`UnitMeter("query",1)`、`call` 把 `resolved`/分配的 provider 對映成 `asearch` 的 `search_provider`、`query` 直傳、req=`["query"]`）。令 T011 轉綠。

**Checkpoint**：US3 可獨立驗收（registry 承載各異的上游參數對映）。

---

## Phase 6: User Story 4 — image_edit 端點（P3）

**Goal**：`POST /v1/images/edits`——multipart 上傳 + 每張圖計費。

**Independent Test**：mock `aimage_edit` 回 `{data:[...]}` + multipart 上傳 image → 200 + 記 `unit="image"`。

- [X] T013 [P] [US4] 寫 `tests/contract/test_image_edit.py`（先失敗）：(a) mock `upstream.aimage_edit` 回 `{data:[{b64_json}]}` + multipart 上傳 `model`+`image`(+`prompt`) + seed 每張圖價 → 200 + 記 `CallRecord(unit="image", quantity=產出圖數, cost, 歸戶)`；(b) 缺 image → 400；(c) 壞 token → 401；(d) mock raise → 502 + 記。
- [X] T014 [US4] 改 `src/ai_api/proxy/upstream.py`：加 `aimage_edit(model, image, prompt, …)` wrapper；在 `registry.py` 加 image_edit spec（`/images/edits`、**multipart**→json、`UnitMeter("image", len(payload["data"]))`、`call=aimage_edit(model, image=(name,bytes), prompt=...)`、req=`["image"]`，沿用 stt 的上傳 parse）。令 T013 轉綠。

**Checkpoint**：US4 可獨立驗收（multipart + 每張圖,複用既有上傳形態）。

---

## Phase 7: Polish & Cross-Cutting

- [X] T015 [P] [US2/3/4] 改 `frontend/src/components/api-usage-example.tsx`（加 moderation/search/image_edit 範例，依 `kind`）+ `frontend/src/routes/catalog-detail.tsx`（kind 型別加 `moderation`/`search`/`image-edit`）；`model_kind` 若需加 `moderation`/`search`/`image-edit` 對映則一併補（`tests/unit/test_model_kind.py` 同步）。
- [X] T016 後端全綠：`python -m pytest tests/ -q` + **`ruff check .`** + `mypy src/ai_api/proxy/{engine,endpoint_spec,registry}.py`；確認既有端點/串流/計費/facet 零回歸（SC-001/005）。
- [X] T017 [P] 前端全綠：`cd frontend && npx tsc --noEmit && npm run build && npm test -- --run`。
- [X] T018 [P] 確認 `alembic heads`=`0019`（無新 migration）、依賴無新增；`git diff` 確認 `test_{embeddings,ocr,images,rerank,audio}.py` 斷言未改（只可能動 import）。
- [X] T019 依 `quickstart.md` 走 US1（既有零回歸）+ US2–4 + 「加端點=加資料」+ 真機煙霧（三新端點壞 token→401、既有 8 端點壞 token→401 不變）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **Foundational（T002–T004，引擎）** 阻塞全部 US。
- **US1（T005–T008）** 依賴引擎；遷移循序（同 `registry.py`/`main.py`），embeddings 先（驗證引擎接真端點）→ ocr/images/rerank → audio（binary+multipart）→ 串流零觸碰確認。
- **US2/US3/US4（T009–T014）** 依賴引擎 + registry 存在（US1 建了 `registry.py`）；三者各自獨立（不同 spec + 不同 wrapper、不同測試檔），**可平行**（但都改 `upstream.py`/`registry.py` → 同檔循序）。
- **Polish（T015–T019）** 最後。

## 平行機會
- Foundational：T002（測試）可先起草。
- 新端點測試 T009/T011/T013 不同檔可平行；實作改同 `registry.py`/`upstream.py` → 循序。
- Polish：T017/T018 可平行。

## MVP 範圍
**Foundational + US1（T001–T008）** 即 MVP：引擎成立 + 5 端點零回歸遷移（複製債消除、架構驗證）。US2（moderation）、US3（search）、US4（image_edit）為增量,各證明「加端點=加資料」。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
