# Tasks: responses 支援判斷（實測 + 手動雙來源）

**Feature**: `035-responses-support-detection` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/responses-support.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 每個有行為的單元/端點/閘門皆先寫失敗測試再實作。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`（皆 repo root 相對）。

---

## Phase 1: Setup

- [X] T001 確認 Phase 25 分支與測試基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/unit/test_litellm_registry.py -q && ruff check src/ai_api` 全綠（建立改動前基準）。

---

## Phase 2: Foundational（阻擋所有 user story 的前置）

**目的**：建立 responses 支援的單一真相來源（標記狀態機 helper）並完成三軸解耦，使後續所有 story 都讀寫同一份語意、且 LiteLLM 同步永不洗掉狀態。

### 2a. `responses_support` helper（標記狀態機）

- [X] T002 [P] 寫 `tests/unit/test_responses_support.py`（先失敗）：覆蓋 data-model.md 狀態表 —— `get_support` 三態推導（blocked>available>unknown、source tested/manual/None、blocked 隱含 manual）；四個轉換 `mark_tested_ok`/`mark_tested_failed`/`mark_manual_on`/`mark_manual_off` 每次先清所有 `responses*` 再設；不變式（`responses` 與 `responses:blocked` 互斥、`responses:tested` 與 `responses:manual` 互斥）；`preserve_into(new_caps, old_caps)` 保留舊 `responses*`；`strip_internal(caps)` 過濾 `responses:*` 但保留裸 `responses`。
- [X] T003 實作 `src/ai_api/services/responses_support.py`：標記常數（`responses`/`responses:blocked`/`responses:tested`/`responses:manual`）、`get_support(caps) -> {state, source}`、四個轉換函式（回傳新 caps list）、`preserve_into`、`strip_internal`，以及 async `lookup(session, slug) -> Support`（讀 `ModelCatalog.capabilities`，row 不存在回 `state=unknown`）。令 T002 轉綠。

### 2b. 三軸解耦（FR-006）

- [X] T004 [P] 改 `tests/unit/test_litellm_registry.py`（先失敗）：反向斷言 registry **不**產生 responses —— `test_lookup_maps_metadata` 移除 `"responses" in caps` 斷言改為 `"responses" not in meta["capabilities"]`；`test_chat_mode_yields_chat_and_responses` 改名/改為 `test_chat_mode_yields_chat_only`，斷言 `metadata_from_entry({"mode":"chat"})["capabilities"] == ["chat"]`；`test_capabilities_expanded_decision_flags` 移除 `responses` 於期望清單。
- [X] T005 改 `src/ai_api/services/litellm_registry.py`：`_capabilities` 移除 `caps.append("responses")` 那行（mode 分支只保留 `chat`），更新 docstring 移除「responses 由 mode 衍生」說明，改述 responses 屬軸③、由 `responses_support` 管轄。令 T004 轉綠。

### 2c. LiteLLM 採納 merge-preserve（FR-006 / SC-004）

- [X] T006 [P] 寫 `tests/integration/test_litellm_apply_preserve.py`（先失敗）：建一個 capabilities 含 `responses` + `responses:manual` 的 catalog 項，呼 `admin_litellm_apply` 採納 `capabilities` 欄，斷言採納後仍保留 `responses` 與 `responses:manual`（merge-preserve），且 litellm 帶來的非 responses 能力有更新。
- [X] T007 改 `src/ai_api/api/admin_catalog.py:admin_litellm_apply`：採納 `capabilities` 欄時改用 `responses_support.preserve_into(latest_meta["capabilities"], m.capabilities)` 後再 `setattr`，其餘欄維持原行為。令 T006 轉綠。

**Checkpoint**：helper + 解耦 + merge-preserve 完成，所有 story 可平行開工。

---

## Phase 3: User Story 1 — runtime 軟化閘門（P1）🎯 MVP

**Goal**：`/v1/responses` 不因缺靜態旗標誤擋；唯一事前封鎖是手動 blocked。

**Independent Test**：未標記但可橋接模型 → 成功；不支援 → 帶上游原因錯誤；手動 blocked → 事前擋。

- [X] T008 [US1] 寫 `tests/integration/test_responses_soft_gate.py`（先失敗）：(a) state=unknown 模型打 `/v1/responses` 不回 `model_not_responses_capable`、走上游（mock 成功）；(b) 上游失敗 → 回帶原因的 `upstream_error`（非無資訊 400）；(c) 手動 blocked 模型 → 事前 400 `model_responses_disabled` 且訊息指明手動停用。
- [X] T009 [US1] 改 `src/ai_api/proxy/responses.py`：把第 4 步閘門由 `model_supports_responses` 改為 `support = await responses_support.lookup(session, requested_model)`，僅 `support.state == "unavailable"` 時 `reject("model_responses_disabled", ..., 400)`；available/unknown 不擋，續走既有上游 aresponses 管線。移除（或保留為 deprecated 不再呼叫）`model_supports_responses`。令 T008 轉綠。
- [X] T010 [US1] 跑 `pytest tests/integration/test_responses_soft_gate.py tests/ -q` 確認 US1 綠且既有 responses 測試零回歸。

**Checkpoint**：US1 可獨立驗收（MVP 解掉誤擋 + 旗標過時）。

---

## Phase 4: User Story 2 — admin「測試 responses」實測（P1）

**Goal**：admin 按「測試 responses」打極小真實呼叫，結果即答案、通過記來源「實測」。

**Independent Test**：可橋接模型按測試→通過、state=available/source=tested；不支援→不通、不標可用。

- [X] T011 [US2] 寫 `tests/integration/test_responses_test_endpoint.py`（先失敗）：`POST /admin/catalog/{slug}/test-responses` —— 成功路徑（mock aresponses 成功）回 `{ok:true, latency_ms, support:{available,tested}}` 且 catalog 被標 `responses`+`responses:tested`；失敗路徑（mock 上游錯誤）回 `{ok:false, error_type, message}`（HTTP 200，不 5xx）且模型維持 unknown；`404 not_found`（slug 不存在）；手動 blocked 模型測試通過時**不**翻轉手動狀態（手動優先）。
- [X] T012 [US2] 在 `src/ai_api/api/admin_catalog.py` 新增 `POST /admin/catalog/{slug}/test-responses`：沿用 `admin_providers.test_provider_connection` 的「結果即回應、NEVER 5xx」模式，打 1-token `aresponses`；成功且非手動 blocked → `mark_tested_ok` 寫回 capabilities；失敗 → 不標；寫 audit（action `responses_test`）。令 T011 轉綠。

**Checkpoint**：US2 可獨立驗收（admin 主動確定可用性）。

---

## Phase 5: User Story 3 — admin 手動覆寫（P2）

**Goal**：admin 直接設「可用/不可用」，覆寫實測、手動優先。

**Independent Test**：手動設不可用→即使測試會通 runtime 仍擋、目錄不顯示徽章；手動設可用→來源標「手動」。

- [X] T013 [US3] 寫 `tests/integration/test_responses_manual_override.py`（先失敗）：`PATCH /admin/catalog/{slug}/responses-support` —— `{available:false}` → state=unavailable/source=manual 且 runtime 事前擋（接 US1 閘門）；`{available:true}` → state=available/source=manual（蓋過先前 tested）；`404 not_found`；寫 audit。
- [X] T014 [US3] 在 `src/ai_api/api/admin_catalog.py` 新增 `PATCH /admin/catalog/{slug}/responses-support`：body `{available: bool}` → `mark_manual_on`/`mark_manual_off` 寫回 capabilities；寫 audit（action `responses_manual_override`，details 含 available）。令 T013 轉綠。

**Checkpoint**：US3 可獨立驗收（admin 最終裁量、手動優先）。

---

## Phase 6: User Story 4 — 目錄徽章 + 成員可篩 + i18n（P2）

**Goal**：目錄顯示「Agent 相容（Responses）」徽章 + 來源；成員可篩；能力清單不露內部標記。

**Independent Test**：available 模型顯示徽章 + 來源；篩「Agent 相容」只列 available；裸 `responses:*` 不外露。

- [X] T015 [US4] 寫 `tests/integration/test_catalog_responses_badge.py`（先失敗）：`GET /catalog` 序列化 —— `capabilities` 過濾掉 `responses:*` 內部標記（保留裸 `responses`）；新增 `responses_support:{state,source}`；available 模型可被「Agent 相容」篩選列出，unknown/unavailable 不列。
- [X] T016 [US4] 改 `src/ai_api/api/catalog.py`：序列化時 `capabilities = responses_support.strip_internal(m.capabilities)`，並附 `responses_support = responses_support.get_support(m.capabilities)`；「Agent 相容」facet 篩選依 `state=available`。令 T015 轉綠。
- [X] T017 [P] [US4] 前端 `frontend/src/routes/admin/model-detail.tsx`：admin 區塊顯示目前 state（可用/不可用/未知）+ source（實測/手動/—）；「測試 responses」按鈕（呼 `POST .../test-responses`、顯示通/不通 + 原因）；可用/不可用切換（呼 `PATCH .../responses-support`）。
- [X] T018 [P] [US4] 前端目錄：available 模型顯示「Agent 相容（Responses）」徽章 + 來源；facet 篩選含「Agent 相容」（讀 `responses_support`）。
- [X] T019 [P] [US4] 確認 `frontend/src/lib/catalog-labels.ts` i18n 修正已就緒並對齊（hyphen 詞彙 `function-calling` 等 + 補齊缺漏標籤），隨本階段一起上線；不外露 `responses:*` 標籤。

**Checkpoint**：US4 可獨立驗收（成員看得懂 + i18n 乾淨）。

---

## Phase 7: Polish & Cross-Cutting

- [X] T020 跑全套後端測試 `python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api`（若 CI 含）全綠；確認計費/proxy/目錄零回歸（SC-005）。
- [X] T021 [P] 確認 `alembic heads` 無新增、`requirements*.txt`/`pyproject` 依賴無新增（SC-005「無新 migration、無新套件」）。
- [X] T022 [P] 前端 `cd frontend && npm run build`（或 typecheck）通過。
- [X] T023 依 `quickstart.md` 走四條 user story + 解耦/零回歸手動驗收（本機）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **Foundational（T002–T007）** 阻擋全部。
- **US1（T008–T010）** 依賴 Foundational（helper `lookup`）。MVP。
- **US2（T011–T012）**、**US3（T013–T014）**、**US4（T015–T019）** 皆依賴 Foundational；US3/US4 的 runtime 行為驗收依賴 US1 閘門已上。
  - 後端端點 US2/US3/US4 改同一檔 `admin_catalog.py`/`catalog.py` → 同檔任務循序；不同檔可平行。
- **Polish（T020–T023）** 最後。

## 平行機會

- Foundational 內：T002（helper 測試）、T004（registry 測試）、T006（apply 測試）可平行起草（不同檔）。
- US4 前端 T017/T018/T019 三檔可平行。
- Polish T021/T022 可平行。

## MVP 範圍

**US1（T001–T010）** 即 MVP：解掉「誤擋」與「旗標過時」兩個核心痛點。US2–US4 為增量交付。

## Format 驗證

所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段皆帶 [US#]。
