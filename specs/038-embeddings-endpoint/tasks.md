# Tasks: 對成員開放 `/v1/embeddings` 端點

**Feature**: `038-embeddings-endpoint` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/embeddings.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 端點/計費/拒絕、目錄衍生欄、前端範例皆先寫失敗測試再實作。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`（皆 repo root 相對）。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract -q -k "chat or proxy" && ruff check src/ai_api` 綠（改動前基準）。

---

## Phase 2: Foundational

> 本功能無跨 story 的共用前置（端點複用既有 preflight/計費，目錄衍生欄只 US3 用）。直接進 US1。

---

## Phase 3: User Story 1 — 成員呼叫 embedding + 計量歸戶（P1）🎯 MVP

**Goal**：`POST /v1/embeddings` 走同一條 preflight + token 計費，回向量、記一筆歸戶分配。

**Independent Test**：有效金鑰+授權模型→向量+一筆 input-token 計費；未授權/壞金鑰→擋下。

- [X] T002 [US1] 寫 `tests/contract/test_embeddings.py`（先失敗）：`POST /v1/embeddings`（seed embedding catalog + provider cred + 成員分配/金鑰，沿用既有 contract helper）—— (a) mock `upstream.aembedding` 回 `{data:[...], usage:{prompt_tokens:5,total_tokens:5}}` → 200 回向量、記一筆 `CallRecord(success, prompt_tokens=5, cost>0, allocation 歸戶)`；(b) scope 外 / 未授權模型 → `model_mismatch`/`model_forbidden`；(c) 壞/缺 token → 401；(d) 缺 `input` → 400 `bad_request`。
- [X] T003 [US1] 新增 `src/ai_api/proxy/embeddings.py`：`POST /embeddings`，複製 `proxy/router.py` 的 chat 流程——body 驗 `{model, input}`、`run_preflight`、`upstream.aembedding(model=upstream_model, input=input, api_key=…, api_base=…, api_version=…)`、`usage.prompt_tokens` → `lookup_price_for_call` + `calculate_cost(prompt_tokens, completion_tokens=0)` → `record_call(success, prompt_tokens, total_tokens, cost)`；拒絕/錯誤沿用 `record_and_respond` + `_outcome_for_code`。
- [X] T004 [US1] 改 `src/ai_api/main.py`：`include_router(embeddings_router, prefix="/v1", tags=["proxy"])`（與 chat/responses 同層）。令 T002 (a)–(d) 轉綠。

**Checkpoint**：US1 可獨立驗收（embedding 可呼叫 + 計量歸戶 = MVP）。

---

## Phase 4: User Story 2 — 上游錯誤可診斷（P2）

**Goal**：embedding 上游失敗回帶原因錯誤、記 `upstream_error`、不無聲。

**Independent Test**：mock aembedding raise → 502 帶原因 + `CallRecord(upstream_error)`。

- [X] T005 [US2] 擴充 `tests/contract/test_embeddings.py`（先失敗）：mock `upstream.aembedding` `side_effect=RuntimeError("DeploymentNotFound")` → 502、`error.code==upstream_error`、訊息含上游原因；記一筆 `CallRecord(outcome=upstream_error)` 帶 model/allocation。
- [X] T006 [US2] 確認 `embeddings.py` 的上游 try/except 走 `record_and_respond("upstream_error", …, 502)`（同 chat），`logger.exception` 帶上下文；底層金鑰不入訊息。令 T005 轉綠。

**Checkpoint**：US2 可獨立驗收（錯誤可診斷）。

---

## Phase 5: User Story 3 — 詳情顯示如何呼叫（P2）

**Goal**：embedding 模型詳情顯 `/v1/embeddings` 範例；chat 模型仍顯 chat。

**Independent Test**：embedding 模型詳情含 `/v1/embeddings` 範例;非 embedding 不被取代。

- [X] T007 [P] [US3] 寫後端 `tests/contract/test_catalog_kind.py`（先失敗）：`GET /catalog/models/{slug}` 對 mode=embedding 模型回 `kind:"embedding"`、對一般 chat 模型回 `kind:"chat"`（`current_member` 可見）。
- [X] T008 [US3] 改 `src/ai_api/api/catalog.py`：`_to_detail`（必要時 `_to_summary`）加唯讀 `kind = model_kind(m)`（import `services.model_kind`）。令 T007 轉綠。
- [X] T009 [P] [US3] 寫 `frontend/src/__tests__/api-usage-example.test.tsx`（先失敗，或擴充既有）：embedding（傳 kind/isEmbedding）→ 顯 `/v1/embeddings` 範例;否則顯 chat（+ responses 若支援不變）。
- [X] T010 [US3] 改 `frontend/src/components/api-usage-example.tsx`：加 embedding 範例（`/v1/embeddings` curl/python/js，body `{model, input}`）+ prop（`kind` 或 `isEmbedding`）切換；改 `frontend/src/routes/catalog-detail.tsx`：ModelDetail 型別加 `kind`、依 `m.kind==="embedding"` 傳給 `ApiUsageExample`。令 T009 轉綠。

**Checkpoint**：US3 可獨立驗收（成員知道怎麼呼叫 embedding）。

---

## Phase 6: Polish & Cross-Cutting

- [X] T011 跑後端 `python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api/proxy/embeddings.py src/ai_api/api/catalog.py` 全綠；確認 chat/responses/計費/配額零回歸（SC-005）。
- [X] T012 [P] 前端 `cd frontend && npx tsc --noEmit && npm run build && npm test -- --run` 全綠（含 api-usage-example 新舊測試）。
- [X] T013 [P] 確認 `alembic heads` 無新增、依賴（pip/npm）無新增。
- [X] T014 依 `quickstart.md` 走 US1–US3 + 零回歸手動驗收（含真機打一次 `/v1/embeddings` 確認向量 + 用量記一筆）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **US1（T002–T004）** MVP（端點 + 計量）。
- **US2（T005–T006）** 依賴 US1（同檔 `embeddings.py` 的錯誤分支）。
- **US3（T007–T010）** 與 US1/US2 大致獨立（catalog 衍生欄 + 前端範例），可平行於 US2；前端 T010 依賴後端 T008 的 `kind` 欄。
- **Polish（T011–T014）** 最後。

## 平行機會
- 測試先寫：T007（後端 kind）、T009（前端範例）不同檔可平行起草。
- US3 與 US2 可平行（不同檔）。
- Polish：T012/T013 可平行。

## MVP 範圍
**US1（T001–T004）** 即 MVP：embedding 可呼叫 + 計量歸戶。US2（錯誤可診斷）、US3（範例顯示）為增量。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
