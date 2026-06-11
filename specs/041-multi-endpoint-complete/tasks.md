# Tasks: 多端點全開（圖片 / rerank / TTS / STT）+ 目錄誠實

**Feature**: `041-multi-endpoint-complete` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/endpoints.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 各端點計量歸戶/拒絕/上游錯誤、TTS binary 回應、STT multipart 上傳、誠實債（capabilities 不假裝 chat）、token 零回歸，皆**先寫失敗測試再實作**。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`。

**核心約束**：token 計費路徑零回歸；**零 migration**（`unit`/`price_unit` 字串維度已於 0019 就緒，新單位 query/character 只是字串值）；**零新套件**（補 `arerank`/`atranscription` 薄 wrapper）；binary 限 TTS（輸出）/STT（輸入）；TTS 在 bytes 取得當下記帳（非 finally）；`_capabilities` 移除 `or ["chat"]`。

**共用檔注意**：`main.py`（四端點都 mount）、`proxy/audio.py`（US3 speech + US4 transcription）、`api-usage-example.tsx`（四端點範例）為跨 US 共用檔 → 同檔任務循序、不可 [P]。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract/test_ocr.py tests/contract/test_embeddings.py -q && ruff check .` 綠；確認 `alembic heads` = `0019`（本功能不應變動）。

---

## Phase 2: Foundational

> 各端點獨立（皆複用既有 preflight + 增量② 計費維度），無跨 US 阻塞前置。`model_kind` 加 `rerank` 與各 `upstream.*` wrapper 隨首次需要的 US 建立。直接進 US1。

---

## Phase 3: User Story 1 — 圖片生成（P1）🎯 MVP

**Goal**：`POST /v1/images/generations` 走同一條 preflight、token 計費、歸戶分配。

**Independent Test**：有效金鑰 + mock `aimage_generation`（帶 usage）→ 200 + 記一筆 token 計費歸戶。

- [X] T002 [P] [US1] 寫 `tests/contract/test_images.py`（先失敗）：(a) mock `upstream.aimage_generation` 回 `ImageResponse`-like（`data` + `usage{prompt_tokens,total_tokens}`）→ 200、記 `CallRecord(success, prompt_tokens, cost, allocation 歸戶)`；(b) 缺 `prompt` → 400；(c) 壞/缺 token → 401；(d) 金鑰範圍外 → 403；(e) mock raise → 502 `upstream_error` + 記。
- [X] T003 [US1] 新增 `src/ai_api/proxy/images.py`：複製 `embeddings.py`——`POST /images/generations`，body `{model, prompt}`、`run_preflight`、`upstream.aimage_generation`、token 計費（`usage` → `calculate_cost`）→ `record_call`；回 `model_dump()`。
- [X] T004 [US1] 改 `src/ai_api/main.py`：mount `images_router` 於 `/v1`。令 T002 轉綠。
- [X] T005 [US1] 改 `frontend/src/components/api-usage-example.tsx`（加 `kind==="image"` 範例：`/v1/images/generations` body `{model, prompt}`）+ `frontend/src/routes/catalog-detail.tsx`（依 `kind` 傳）。

**Checkpoint**：US1 可獨立驗收（圖片可呼叫 + token 計費 = MVP）。

---

## Phase 4: User Story 2 — rerank（P2）

**Goal**：`POST /v1/rerank` per-query 計費（`unit="query"`、qty=1）。

**Independent Test**：mock `arerank` 回 results → 200 + 記 `unit="query"` cost=每查詢價。

- [X] T006 [P] [US2] 寫 `tests/contract/test_rerank.py`（先失敗）：(a) mock `upstream.arerank` 回 `RerankResponse`-like（`results`）+ seed 每查詢價 → 200、記 `CallRecord(unit="query", quantity=1, cost=每查詢價, 歸戶)`；(b) 無每查詢價 → cost 0；(c) 缺 query/documents → 400；(d) 壞 token → 401；(e) mock raise → 502 + 記。
- [X] T007 [US2] 改 `src/ai_api/proxy/upstream.py`：加 `arerank(model, query, documents, …)` wrapper（沿用 `_extra`）；改 `src/ai_api/services/model_kind.py`：`Kind` 加 `"rerank"`、`_MODE_TO_KIND["rerank"]="rerank"`。
- [X] T008 [US2] 新增 `src/ai_api/proxy/rerank.py`：`POST /rerank`，body `{model, query, documents}`、`run_preflight`、`upstream.arerank`、`calculate_unit_cost(1, 每查詢價)`（`price.price_unit=="query"`）→ `record_call(quantity=1, unit="query", cost)`；回 `model_dump()`。
- [X] T009 [US2] 改 `src/ai_api/main.py`：mount `rerank_router` 於 `/v1`。令 T006 轉綠。
- [X] T010 [US2] 改 `frontend/src/components/api-usage-example.tsx`：加 `kind==="rerank"` 範例（`/v1/rerank` body `{model, query, documents}`）。

**Checkpoint**：US2 可獨立驗收（rerank per-query 計費 = 一般化第二單位）。

---

## Phase 5: User Story 3 — TTS 語音合成（P3，binary 輸出）

**Goal**：`POST /v1/audio/speech` 回 binary 音檔、per-character 計費、bytes 當下記帳。

**Independent Test**：mock `aspeech` 回 bytes 物件 → 200 + `Content-Type: audio/mpeg` + body=bytes + 記 `unit="character"` quantity=len。

- [X] T011 [P] [US3] 寫 `tests/contract/test_audio.py`（先失敗，TTS 部分）：(a) mock `upstream.aspeech` 回 binary-like（`.content` bytes）+ seed 每字元價 → 200、`Content-Type` 起始 `audio/`、body==bytes、記 `CallRecord(unit="character", quantity=len(input), cost=len×每字元價, 歸戶)`；(b) 缺 `input` → 400；(c) mock raise → 502 JSON 錯誤 + 記。
- [X] T012 [US3] 新增 `src/ai_api/proxy/audio.py`：`POST /audio/speech`，body `{model, input, voice}`、`run_preflight`、`upstream.aspeech` → 讀 `.content`（dict 時取 bytes 相容）、`calculate_unit_cost(len(input), 每字元價)`、**在此處 `record_call`**（非 finally）→ 回 `Response(content=bytes, media_type="audio/mpeg")`；錯誤路徑回 JSON（`record_and_respond`）。
- [X] T013 [US3] 改 `src/ai_api/main.py`：mount `audio_router` 於 `/v1`。令 T011 轉綠。
- [X] T014 [P] [US3] 改 `frontend/src/components/api-usage-example.tsx`：加 `kind==="tts"` 範例（`/v1/audio/speech`，註明回音檔）。

**Checkpoint**：US3 可獨立驗收（TTS binary 輸出 + per-character 計費）。

---

## Phase 6: User Story 4 — STT 語音轉文字（P4，multipart 上傳）

**Goal**：`POST /v1/audio/transcriptions` 收音檔上傳、token 計費。

**Independent Test**：mock `atranscription` 回 `{text,usage}` + multipart file → 200 + token 計費歸戶。

- [X] T015 [US4] 擴充 `tests/contract/test_audio.py`（先失敗，STT 部分）：(a) mock `upstream.atranscription` 回 `{text, usage{prompt_tokens,total_tokens}}` + 以 multipart 上傳 `model`+`file` → 200、記 `CallRecord(token 計費, 歸戶)`；(b) 無 usage → cost 0、仍記成功；(c) 缺 file → 400；(d) 壞 token → 401；(e) mock raise → 502 + 記。
- [X] T016 [US4] 改 `src/ai_api/proxy/upstream.py`：加 `atranscription(model, file, …)` wrapper（litellm `atranscription`，`_extra` 注入憑證）。
- [X] T017 [US4] 改 `src/ai_api/proxy/audio.py`：加 `POST /audio/transcriptions`——收 `UploadFile`（multipart）+ form `model`、`run_preflight`、讀 bytes → `upstream.atranscription(file=(name, bytes))`、token 計費（`usage` 有則 `calculate_cost`、無則 0）→ `record_call`；回 `model_dump()`（JSON）。令 T015 轉綠。
- [X] T018 [P] [US4] 改 `frontend/src/components/api-usage-example.tsx`：加 `kind==="stt"` 範例（`/v1/audio/transcriptions`，multipart 上傳）。

**Checkpoint**：US4 可獨立驗收（STT multipart 上傳 + token 計費）。

---

## Phase 7: User Story 5 — 目錄誠實（P3，橫切）

**Goal**：`_capabilities` 不假裝 chat + admin 詳情顯類型。

**Independent Test**：非 chat 無旗標 entry → capabilities `[]`；chat entry → 含 chat（零回歸）；admin 詳情含 `kind`。

- [X] T019 [P] [US5] 寫 `tests/contract/test_capabilities_honesty.py`（先失敗）：`litellm_registry._capabilities` 對 (a) `{mode:"ocr"}`（無旗標）→ `[]`；(b) `{mode:"embedding"}` → 不含 chat；(c) `{mode:"chat"}` → 含 `"chat"`（零回歸）；(d) `{mode:"chat", supports_function_calling:True}` → 含 chat + function-calling。擴充 `tests/contract/test_catalog_kind.py`：rerank 模型 `kind=="rerank"`、**admin 詳情端點回應含 `kind`**。
- [X] T020 [US5] 改 `src/ai_api/services/litellm_registry.py`：`_capabilities` 結尾 `return caps or ["chat"]` → `return caps`（chat-able mode 前面仍 `append("chat")`，零回歸）。
- [X] T021 [US5] 改 `src/ai_api/api/admin_catalog.py`：admin 模型詳情序列化加 `"kind": _mk.model_kind(m)`（`_mk` 已 import）。令 T019 admin 部分轉綠。
- [X] T022 [US5] 改 `frontend/src/routes/admin/catalog-*.tsx`（admin 模型詳情）：加「類型」欄顯示 `kind`（與「能力」分開）；型別加 `kind?`。擴充對應前端測試。

**Checkpoint**：US5 可獨立驗收（非 chat 模型不再假裝 chat、admin 看得到類型）。

---

## Phase 8: Polish & Cross-Cutting

- [X] T023 後端全綠：`python -m pytest tests/ -q` + **`ruff check .`（含 tests/）** + `mypy src/ai_api/proxy/{images,rerank,audio}.py src/ai_api/services/litellm_registry.py`；確認 chat/responses/embedding/OCR/token 計費/配額/**facet 篩選**零回歸（SC-005）。
- [X] T024 [P] 前端全綠：`cd frontend && npx tsc --noEmit && npm run build && npm test -- --run`。
- [X] T025 [P] 確認 `alembic heads`=`0019`（無新 migration）、依賴（pip/npm）無新增；回歸驗 `compute_facets`/篩選對**空 capabilities** 不爆（誠實債 sink，research R5）。
- [X] T026 依 `quickstart.md` 走 US1–US5 + 零回歸手動驗收（真機：四端點壞 token→401〔皆走 `location /v1`〕、TTS 回 `audio/*`、STT 收 multipart、admin 詳情非 chat 模型能力不再 chat + 顯類型）。

---

## Dependencies & 執行順序

- **Setup（T001）** → 各 US 大致獨立（皆複用 preflight + 增量② 計費）。
- **US1（T002–T005）** MVP（圖片 token）。
- **US2（T006–T010）** 加 `arerank` + `model_kind rerank`；可平行於 US1。
- **US3（T011–T014）** 建 `audio.py`（speech）。
- **US4（T015–T018）** 在 `audio.py` 加 transcription → **依賴 US3 的 `audio.py` 存在**（同檔，循序）。
- **US5（T019–T022）** 橫切（capabilities + kind），與端點正交、可平行；但 `kind` 顯示涉及 `model_kind rerank`（US2 的 T007）→ 若先做 US5 需先加 rerank kind。
- **共用檔循序**：`main.py`（T004/T009/T013）、`api-usage-example.tsx`（T005/T010/T014/T018）、`audio.py`（T012/T017）。
- **Polish（T023–T026）** 最後。

## 平行機會
- 測試先寫：T002/T006/T011/T019 不同檔可平行起草。
- **US1/US2 可平行**（不同端點檔）；US5 與端點正交可平行（注意 model_kind rerank 前置）。
- 共用檔（main.py / audio.py / api-usage-example.tsx）內循序。
- Polish：T024/T025 可平行。

## MVP 範圍
**US1（T001–T005）** 即 MVP：圖片可呼叫 + token 計費。US2（rerank）、US3（TTS）、US4（STT）、US5（誠實債）為增量；各自獨立可驗收、可分批 PR。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
