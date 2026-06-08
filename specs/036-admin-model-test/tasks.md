# Tasks: admin 依模型種類一鍵測試模型是否可用

**Feature**: `036-admin-model-test` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/model-test.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 每個有行為的單元/端點/分派皆先寫失敗測試再實作。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`（皆 repo root 相對）。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/unit -q -k litellm && ruff check src/ai_api` 綠（改動前基準）。

---

## Phase 2: Foundational（阻擋所有 user story 的前置）

**目的**：建立「種類判定（單一真相）」+「三個 upstream wrapper」+「audit 值」，後續所有測法都依賴它們。

### 2a. 種類判定 helper

- [X] T002 [P] 寫 `tests/unit/test_model_kind.py`（先失敗）：覆蓋 data-model.md 判定表 —— litellm mode 優先（chat/completion→chat、embedding→embedding、image_generation→image、audio_speech→tts、audio_transcription→stt、其他→unknown）；無 `litellm_sync` 時 modality 退路（output image→image、output audio→tts、input 含 audio→stt、其餘→chat）；**embedding 撞型驗證**（mode=embedding 回 embedding，但無 mode 的 text→text 回 chat）；任一輸入皆回六值之一不丟例外。
- [X] T003 實作 `src/ai_api/services/model_kind.py`：`model_kind(model) -> Literal["chat","embedding","tts","image","stt","unknown"]`（讀 `model.litellm_sync["raw"]["mode"]`，None-safe；退 `modality_output`/`modality_input`）+ `is_billable(kind)`（image/tts）+ `is_supported(kind)`（非 stt/unknown）。令 T002 轉綠。

### 2b. upstream wrapper

- [X] T004 [P] 寫 `tests/unit/test_upstream_wrappers.py`（先失敗）：mock `litellm.aembedding`/`aspeech`/`aimage_generation`，斷言三 wrapper 帶 `model` + `api_key`，且 None 的 `api_base`/`api_version` 不外洩（沿用 acompletion 既有注入規則）。
- [X] T005 改 `src/ai_api/proxy/upstream.py`：新增 async `aembedding(*, model, input, api_key, api_base=None, api_version=None, **kwargs)`、`aspeech(*, model, input, voice, api_key, ...)`、`aimage_generation(*, model, prompt, api_key, ...)`，各 `extra={api_key, api_base?, api_version?}` + drop None kwargs 後呼叫對應 `litellm.a*`。令 T004 轉綠。

### 2c. audit 值

- [X] T006 [P] 改 `src/ai_api/models/auth_audit.py`：`AuditEventType` 加 `model_tested = "model_tested"`（非 native enum，無 migration）。

**Checkpoint**：種類判定 + wrapper + audit 就緒，端點層可開工。

---

## Phase 3: User Story 1 — 對話模型一鍵測試（P1）🎯 MVP

**Goal**：對話模型詳情頁按「測試模型」→ 1-token 呼叫、結果即回應。

**Independent Test**：可用對話模型→通過+延遲；壞掉→帶上游原因；無憑證→清楚說明。

- [X] T007 [US1] 寫 `tests/integration/test_admin_model_test.py`（先失敗，本檔後續 story 共用）：`POST /admin/catalog/models/{slug}/test` 對話模型 —— (a) mock `upstream.acompletion` 成功 → `{ok:true, kind:"chat", latency_ms}` 且寫 `model_tested` audit；(b) mock 上游 raise → `{ok:false, kind:"chat", error_type:"upstream_error", message}`（HTTP 200，不 5xx）；(c) 該 provider 無憑證 → `{ok:false, error_type:"provider_unavailable"}`；(d) slug 不存在 → 404。
- [X] T008 [US1] 在 `src/ai_api/api/admin_catalog.py` 新增 `POST /catalog/models/{slug:path}/test`：取模型（404）→ `kind=model_kind(model)` → 分派骨架（先實作 chat 分支：解供應商憑證[沿用 test-responses 的 `_resolve_credential`]→ `upstream.acompletion(messages=[{user:"ping"}], max_tokens=1)`）→ 結果即回應、上游例外不 5xx → 寫 `model_tested` audit。令 T007 (a)–(d) 轉綠。

**Checkpoint**：US1 可獨立驗收（對話測試 MVP）。

---

## Phase 4: User Story 2 — embedding 模型測試（P2）

**Goal**：embedding 模型按測試 → 短字串 embedding、結果即回應、不被誤判成對話。

**Independent Test**：mode=embedding 模型→走 embedding 測法通/不通。

- [X] T009 [US2] 擴充 `tests/integration/test_admin_model_test.py`（先失敗）：seed 一個 `litellm_sync.raw.mode="embedding"` 的模型，`POST .../test` → mock `upstream.aembedding` 成功 → `{ok:true, kind:"embedding"}`；失敗 → `error_type:"upstream_error"`。
- [X] T010 [US2] 在測試端點加 `embedding` 分派：`upstream.aembedding(input="ping")`。令 T009 轉綠。

**Checkpoint**：US2 可獨立驗收。

---

## Phase 5: User Story 3 — 計費種類（TTS/圖片）+ 費用確認（P2）

**Goal**：billable 種類先確認再打；未確認後端不打上游。

**Independent Test**：未帶 acknowledge→needs_confirmation 不打；帶了→打最小呼叫。

- [X] T011 [US3] 擴充 `tests/integration/test_admin_model_test.py`（先失敗）：(a) image 模型不帶 `acknowledge_billable` → `{ok:false, kind:"image", needs_confirmation:true}` 且 `upstream.aimage_generation` **未被呼叫**；(b) 帶 `{acknowledge_billable:true}` → mock 成功 → `{ok:true, kind:"image"}`；(c) tts 同理（`aspeech`，voice 帶入）；(d) 失敗路徑回 upstream_error 不 5xx。
- [X] T012 [US3] 在測試端點加 billable 閘門 + `image`/`tts` 分派：`kind ∈ {image,tts}` 且 `acknowledge_billable != true` → 回 `needs_confirmation`（不解憑證、不打上游）；確認後 `upstream.aimage_generation(prompt="a red dot", size="256x256", n=1)` / `upstream.aspeech(input="hi", voice="alloy")`。Body 模型加選填 `acknowledge_billable`。令 T011 轉綠。

**Checkpoint**：US3 可獨立驗收（成本閘門前後端雙保險）。

---

## Phase 6: User Story 4 — 未支援種類給說明（P3）

**Goal**：stt/unknown 顯示清楚說明、不打上游、不崩。

**Independent Test**：STT 模型按測試→supported:false + 說明、上游未被呼叫。

- [X] T013 [US4] 擴充 `tests/integration/test_admin_model_test.py`（先失敗）：seed 一個 `mode="audio_transcription"`（或 modality input audio）模型，`POST .../test` → `{ok:false, kind:"stt", supported:false, message}` 且任何 `upstream.*` 未被呼叫；unknown mode 同理。
- [X] T014 [US4] 在測試端點最前面加 `is_supported` 閘門：`kind ∈ {stt,unknown}` → 回 `supported:false` + 說明，不打上游。令 T013 轉綠。

**Checkpoint**：US4 可獨立驗收（按鈕在所有種類行為一致）。

---

## Phase 7: 前端（US1–US4 的畫面，依賴後端端點）

- [X] T015 改 `src/ai_api/api/admin_catalog.py:_to_dict`：加唯讀衍生欄 `test_kind`/`test_billable`/`test_supported`（呼叫 `model_kind`/`is_billable`/`is_supported`）。
- [X] T016 [P] 前端 `frontend/src/routes/admin/model-detail.tsx`：CatalogModel 型別加 `test_kind`/`test_billable`/`test_supported`；加「測試模型」按鈕（與既有「測試 responses」並列）+ `useMutation` 呼 `POST .../test`；結果以 toast 顯示（通過+延遲 / 失敗原因）。
- [X] T017 [P] 前端 model-detail：billable（`test_billable`）按鈕點擊先跳 `AlertDialog`「此測試會產生一次實際費用」→ 確認後帶 `{acknowledge_billable:true}` 呼叫；`test_supported===false` 按鈕停用 + 「此類型尚不支援自動測試」說明。

---

## Phase 8: Polish & Cross-Cutting

- [X] T018 跑全套後端 `python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api/services/model_kind.py src/ai_api/proxy/upstream.py src/ai_api/api/admin_catalog.py` 全綠；確認計費/proxy/目錄零回歸（SC-005）。
- [X] T019 [P] 確認 `alembic heads` 無新增、依賴無新增（litellm 既有函式）；`cd frontend && npx tsc --noEmit && npm run build && npm test -- --run` 全綠。
- [X] T020 [P] 依 `quickstart.md` 走四種 + 未支援 + 零回歸手動驗收（本機）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **Foundational（T002–T006）** 阻擋全部。
- **US1（T007–T008）** 依賴 Foundational。MVP。
- **US2（T009–T010）**、**US3（T011–T012）**、**US4（T014）** 皆擴充**同一個** `admin_catalog.py` 測試端點 + 同一個整合測試檔 → 端點實作任務循序（T008→T010→T012→T014），但各 story 的測試斷言可獨立驗收。
- **前端（T015–T017）** 依賴端點（T008 起）+ 衍生欄（T015）。T016/T017 同檔循序或小心合併。
- **Polish（T018–T020）** 最後。

## 平行機會
- Foundational：T002（kind 測試）、T004（wrapper 測試）、T006（audit 值）不同檔可平行起草。
- Polish：T019/T020 可平行。

## MVP 範圍
**US1（T001–T008）** 即 MVP：對話模型一鍵測試（最大宗、免費可測）。US2–US4 為增量。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/前端/Polish 無 story 標籤、US 階段帶 [US#]。
