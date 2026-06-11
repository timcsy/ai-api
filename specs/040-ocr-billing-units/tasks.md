# Tasks: 計費一般化（非 token 單位）+ OCR 端點

**Feature**: `040-ocr-billing-units` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/ocr-and-pricing.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 計費一般化數學、OCR 計量歸戶/拒絕/上游錯誤、價格端點每頁價、目錄 kind、token 零回歸，皆**先寫失敗測試再實作**。

**路徑慣例**：後端 `src/ai_api/`、migration `alembic/versions/`、測試 `tests/`、前端 `frontend/src/`。

**核心約束**：token 計費路徑**完全不動**（零回歸）；migration `0019` **純加欄**（token 欄不動、不改 nullability）；`unit` 為字串維度（這次只加 `page`）；不新增套件；`calculate_cost` 不改、新增 `calculate_unit_cost`。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract/test_embeddings.py tests/contract/test_admin_prices.py -q && ruff check src/ai_api` 綠；確認 `alembic heads` = `0018`（改動前基準）。

---

## Phase 2: Foundational（計費一般化——US1/US2 的阻塞前置）

> 計費層的加欄 + 通用計算是 OCR 端點（US1）與 admin 每頁價（US2）的共同地基，必須先完成。**token 路徑零回歸**為硬約束。

- [X] T002 [P] 寫 `tests/contract/test_pricing_units.py`（先失敗）：(a) `calculate_unit_cost(quantity, price_per_unit)` —— N×價、quantity/價為 None/0 → `Decimal(0)`；(b) `lookup_price_for_call` 對帶每頁價的 PriceList 列回傳 `price_unit="page"` + `price_per_unit`；(c) point-in-time：兩個 `effective_from` 的價列，依 call_time 取對的價。
- [X] T003 [P] 寫 `tests/integration/test_billing_generalization.py`（先失敗）：**token 零回歸**——既有 chat/embedding 風格的 token 計費（`calculate_cost`）結果與本變更前一致；且 `record_call(quantity=3, unit="page", cost_usd=…)` 能寫入並讀回（新欄）。
- [X] T004 新增 migration `alembic/versions/0019_billing_units.py`：`price_list` 加 `price_unit`(String(16) nullable)+`price_per_unit_usd`(Numeric(12,8) nullable)；`call_records` 加 `quantity`(Integer nullable)+`unit`(String(16) nullable)。**純 `add_column`**、down 對應 drop。`down_revision="0018_model_litellm_sync"`。
- [X] T005 改 `src/ai_api/models/price_list.py`（加 `price_unit`/`price_per_unit_usd` mapped 欄）、`src/ai_api/models/call_record.py`（加 `quantity`/`unit` mapped 欄）—— 皆 nullable、對齊 migration。
- [X] T006 改 `src/ai_api/services/pricing.py`：`Price` dataclass 加 `price_unit: str | None`、`price_per_unit: Decimal | None`；`lookup_price_for_call` 一併帶出；**新增** `calculate_unit_cost(quantity, price_per_unit) -> Decimal`。**`calculate_cost` 不動**。令 T002 轉綠。
- [X] T007 改 `src/ai_api/services/records.py`：`record_call` 加 `quantity: int | None = None`、`unit: str | None = None` 參數，寫入 `CallRecord`。令 T003 轉綠（token 呼叫端不傳＝行為不變）。

**Checkpoint**：計費層能存/算非 token 單位、token 路徑零回歸。

---

## Phase 3: User Story 1 — 成員呼叫 OCR + 按頁計費歸戶（P1）🎯 MVP

**Goal**：`POST /v1/ocr` 走同一條 preflight、`len(OCRResponse.pages)` 計量、按每頁價計費歸戶分配。

**Independent Test**：有效金鑰 + mock `aocr` 回 N 頁 → 200 + 記一筆 `CallRecord(unit="page", quantity=N, cost=N×每頁價, success, 歸戶)`；拒絕/壞金鑰擋下。

- [X] T008 [US1] 寫 `tests/contract/test_ocr.py`（先失敗）：(a) 有效金鑰 + mock `upstream.aocr` 回 `OCRResponse`（N 頁）+ seed 每頁價 → 200、記 `CallRecord(unit="page", quantity=N, cost=N×價, success, allocation 歸戶)`；(b) 無每頁價 → cost 0、仍記 N 頁；(c) 金鑰範圍外模型 → 403 `model_mismatch`/`model_forbidden`；(d) 缺/壞 token → 401；(e) 缺 `document` → 400 `bad_request`。
- [X] T009 [US1] 改 `src/ai_api/proxy/upstream.py`：加 `aocr(model, document, api_key, api_base, api_version, **kwargs)` wrapper → `litellm.aocr(...)`（沿用 `_extra` 注入憑證，同 aembedding）。
- [X] T010 [US1] 新增 `src/ai_api/proxy/ocr.py`：複製 `proxy/embeddings.py` 結構——`POST /ocr`，body 驗 `{model, document}`、`run_preflight`、`upstream.aocr`、`pages = usage_info.pages_processed if present else len(resp.pages)`、查每頁價（`price.price_unit=="page"` 時取 `price_per_unit`）、`calculate_unit_cost` → `record_call(quantity=pages, unit="page", cost_usd=cost, outcome=success)`；回 `OCRResponse.model_dump()`；拒絕沿用 `record_and_respond` + `_outcome_for_code`/`_error_payload`。
- [X] T011 [US1] 改 `src/ai_api/main.py`：`include_router(ocr_router, prefix="/v1", tags=["proxy"])`。令 T008 (a)–(e) 轉綠。

**Checkpoint**：US1 可獨立驗收（OCR 可呼叫 + 按頁計費歸戶 = MVP，計費一般化端到端證明）。

---

## Phase 4: User Story 2 — admin 設定/覆寫每頁價 + 可稽核（P2）

**Goal**：admin 能為 OCR 模型設/覆寫每頁價，計費按平台價、point-in-time。

**Independent Test**：admin 建每頁價 → GET 帶 `price_unit/price_per_unit`；改價後新呼叫新價、舊紀錄不變；`price_unit` 無 `price_per_unit` → 400。

- [X] T012 [US2] 擴充 `tests/contract/test_admin_prices.py`（先失敗）：(a) `POST /admin/prices` 帶 `price_unit:"page"`+`price_per_unit:"0.003"`（token 欄 0）→ 201、`GET /admin/prices` 該列帶 `price_unit/price_per_unit`；(b) 給 `price_unit` 但缺 `price_per_unit` → 400；(c) token 價建立路徑不變（回歸）。
- [X] T013 [US2] 改 `src/ai_api/api/admin_prices.py`：`PriceCreateRequest` 加選填 `price_unit: str | None`、`price_per_unit: str | None`（給 unit 必給 price，否則 400）；`create_price` 寫入新欄；`GET /prices` + `/prices/history` 序列化加 `price_unit`/`price_per_unit`（token 列為 null）。令 T012 轉綠。
- [X] T014 [P] [US2] 改 `frontend/src/routes/admin/prices.tsx`（或對應價格 UI）：新增價格表單加「每單位價」選填欄（單位 + 每單位價，預設 token）；列表/歷史顯示每頁價。型別加 `price_unit?`/`price_per_unit?`。
- [X] T015 [P] [US2] 寫/擴充 `frontend/src/__tests__/admin-prices.test.tsx`：填每頁價送出 → 打 `/admin/prices` 帶 `price_unit/price_per_unit`；列表顯示每頁價。

**Checkpoint**：US2 可獨立驗收（admin 可管非 token 價、可稽核、point-in-time）。

---

## Phase 5: User Story 3 — OCR 上游錯誤可診斷（P2）

**Goal**：OCR 上游失敗回帶原因錯誤、記 `upstream_error`、不無聲。

**Independent Test**：mock `aocr` raise → 502 帶原因 + `CallRecord(upstream_error)`。

- [X] T016 [US3] 擴充 `tests/contract/test_ocr.py`（先失敗）：mock `upstream.aocr` `side_effect=RuntimeError("DeploymentNotFound")` → 502、`error.code==upstream_error`、訊息含上游原因；記一筆 `CallRecord(outcome=upstream_error)` 帶 model/allocation；底層金鑰不入訊息。
- [X] T017 [US3] 確認 `proxy/ocr.py` 上游 try/except 走 `record_and_respond("upstream_error", …, 502)`（同 embeddings）、`logger.exception` 帶上下文、`redact_string` 去敏。令 T016 轉綠。

**Checkpoint**：US3 可獨立驗收（OCR 錯誤可診斷）。

---

## Phase 6: User Story 4 — 目錄正確標 OCR + 顯示呼叫範例（P3）

**Goal**：OCR 模型詳情 `kind=ocr` + 顯 `/v1/ocr` 範例；chat/embedding 不變。

**Independent Test**：OCR 模型 `kind=="ocr"` + 顯 OCR 範例；chat/embedding kind 與範例不變。

- [X] T018 [P] [US4] 擴充 `tests/contract/test_catalog_kind.py`（先失敗）：`GET /catalog/models/{slug}` 對 `mode="ocr"` 模型回 `kind:"ocr"`（chat/embedding 維持原 kind）。
- [X] T019 [US4] 改 `src/ai_api/services/model_kind.py`：`Kind` 加 `"ocr"`；`mode=="ocr"` → `"ocr"`。令 T018 轉綠（`catalog.py` 的 `kind` 衍生欄已存在，無需改）。
- [X] T020 [P] [US4] 改 `frontend/src/components/api-usage-example.tsx`：加 OCR 範例（`kind==="ocr"` → `/v1/ocr` curl/python，body `{model, document}`）；改 `frontend/src/routes/catalog-detail.tsx`：依 `m.kind==="ocr"` 傳給 `ApiUsageExample`（沿用 embedding 的 kind 切換）。
- [X] T021 [P] [US4] 擴充 `frontend/src/__tests__/api-usage-example.test.tsx`：OCR（傳 kind/ocr）→ 顯 `/v1/ocr` 範例；非 OCR 不被取代。

**Checkpoint**：US4 可獨立驗收（成員知道怎麼呼叫 OCR）。

---

## Phase 7: Polish & Cross-Cutting

- [X] T022 後端全綠：`python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api/proxy/ocr.py src/ai_api/services/pricing.py src/ai_api/services/records.py`；確認 chat/responses/embedding/token 計費/配額零回歸（SC-002）。
- [X] T023 [P] 前端全綠：`cd frontend && npx tsc --noEmit && npm run build && npm test -- --run`。
- [X] T024 [P] 確認 `alembic heads` = `0019`（單一 head）、`alembic upgrade head` + `downgrade` 可逆、依賴（pip/npm）無新增。
- [X] T025 依 `quickstart.md` 走 US1–US4 + 零回歸手動驗收（真機：`/v1/ocr` 壞 token→401〔端點已註冊、走 `location /v1`〕、`alembic current`=`0019`、既有 token 計費不變）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **Foundational（T002–T007，計費一般化）** 阻塞 US1/US2。
- **US1（T008–T011）** 依賴 Foundational（`calculate_unit_cost`、`record_call` 新參數）。
- **US2（T012–T015）** 依賴 Foundational（PriceList 新欄）；可平行於 US1。
- **US3（T016–T017）** 依賴 US1（同檔 `ocr.py` 錯誤分支）。
- **US4（T018–T021）** 與 US1/US2/US3 大致獨立（kind + 前端範例），可平行；前端 OCR 範例呈現不依賴端點實作。
- **Polish（T022–T025）** 最後。

## 平行機會
- Foundational：T002、T003 不同檔可平行起草。
- **US2 可平行於 US1**（不同檔：admin_prices vs proxy/ocr）。
- US4 可平行於 US1–US3。
- Polish：T023/T024 可平行。

## MVP 範圍
**Foundational + US1（T001–T011）** 即 MVP：計費層一般化 + OCR 可呼叫並按頁計費歸戶（端到端證明）。US2（admin 價）、US3（錯誤）、US4（範例）為增量。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
