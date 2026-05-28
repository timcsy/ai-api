---
description: "Task list for Responses API / Agent (Codex) compatibility"
---

# Tasks: Responses API / Agent 工具（Codex）相容

**Input**: Design documents from `/specs/021-responses-api/`
**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/responses.md

**Tests**: 本專案憲章原則 I（Test-First，不可協商）→ **所有測試任務為必要**，且每項
實作前須有先行失敗測試（Red → Green → Refactor）。

**Organization**: 依 user story 分階段，每階段為可獨立交付與測試的增量。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔案、無未完成相依）
- **[Story]**: US1=Codex MVP、US2=精確計費、US3=多 provider、US4=server-side 狀態

## Path Conventions

單一後端專案：`src/ai_api/`、`tests/`、`alembic/versions/`、`deploy/` 於 repo root。

---

## Phase 1: Setup（共用基礎）

**Purpose**: 確立基線，確認相依與環境就緒（不新增套件）。

- [X] T001 確認 `litellm` 釘選版本（`pyproject.toml` / `uv.lock`）提供 `aresponses` 且支援 `stream=True`；於 `specs/021-responses-api/research.md` R1 註記實測版本號
- [X] T002 跑既有測試套件確立綠燈基線（`pytest -q` + `cd frontend && npx vitest run`），作為後續重構安全網

---

## Phase 2: Foundational（阻塞性前置）

**Purpose**: 資料層 + 共用 pipeline + 上游包裝——所有 user story 都依賴。

**⚠️ CRITICAL**: 本階段完成前，任何 user story 不可開工。

### 資料層（migration 0013）— Test-First

- [X] T003 [P] 撰寫失敗測試：`call_records` 具 `reasoning_tokens`/`cached_tokens`、`price_list` 具 `cached_input_per_1k_tokens_usd`、`stored_responses` 表存在，且 migration up/down 在 Postgres 可逆，於 `tests/integration/test_migration_0013.py`
- [X] T004 [P] [US1/US2] 於 `src/ai_api/models/call_record.py` 新增 `reasoning_tokens`、`cached_tokens`（nullable Integer）
- [X] T005 [P] [US2] 於 `src/ai_api/models/price_list.py` 新增 `cached_input_per_1k_tokens_usd`（nullable Numeric(12,8)）
- [X] T006 [P] [US4] 建立 `src/ai_api/models/stored_response.py`（`response_id` PK / `allocation_id` / `provider` / `upstream_response_id` / `created_at` / `expires_at`，皆 tz-aware）並於 `src/ai_api/models/__init__.py` 匯出
- [X] T007 撰寫 `alembic/versions/0013_responses_api.py`（加 2 欄 call_records + 1 欄 price_list + 建 stored_responses 表 + 索引；Postgres-safe、downgrade 對稱），使 T003 轉綠

### 共用前置 pipeline（重構，行為保持）

- [X] T008 抽出共用前置 pipeline 至 `src/ai_api/proxy/preflight.py`（bearer → allocation lookup+bind → 狀態 → quota → model binding → model access → credential 解析；拒絕路徑在 raise 前綁定 `allocation_id`），回傳已驗證呼叫上下文
- [X] T009 重構 `src/ai_api/proxy/router.py` 的 `/chat/completions` 改用 `preflight.py`；跑既有 proxy 測試確認全綠（行為保持，無新行為）

### 上游包裝與能力閘

- [X] T010 [P] 撰寫 `upstream.aresponses()` 單元測試（mock litellm，驗證參數透傳含 `stream`/`tools`/`reasoning`/`include`/`store`/`previous_response_id`），於 `tests/unit/test_upstream_aresponses.py`
- [X] T011 [P] 於 `src/ai_api/proxy/upstream.py` 新增 `aresponses()` 包裝（litellm library form，透傳 credential 與上述參數），使 T010 轉綠
- [X] T012 [P] 撰寫能力閘單元測試：模型 `capabilities` 含 `"responses"` 才放行，於 `tests/unit/test_responses_capability.py`
- [X] T013 [P] 實作能力閘輔助函式（判斷 model_catalog `capabilities` 是否含 `"responses"`）於 `src/ai_api/proxy/responses.py`，使 T012 轉綠

**Checkpoint**: 資料層、共用 pipeline、上游包裝就緒——user story 可開工。

---

## Phase 3: User Story 1 - 開發者用平台憑證跑 Codex agent 任務 (Priority: P1) 🎯 MVP

**Goal**: `POST /v1/responses` 可用——含 SSE streaming、tool calls、推理；每次呼叫
套用 preflight 並歸戶計費；Codex 真機可完成多輪 agent 任務。

**Independent Test**: 用有效憑證設定 Codex（base URL + 憑證），跑含工具呼叫的多輪
任務，回應即時逐步顯示、任務完成、用量出現在對應分配。

### Tests for User Story 1 ⚠️（先寫，須先失敗）

- [X] T014 [P] [US1] 契約測試：`/v1/responses` 各前置拒絕路徑回正確 code 且帶 `allocation_id`（unauthorized / revoked / quota_exceeded / model_mismatch / model_forbidden / provider_not_allowed）、未標記 responses 的模型回 `model_not_responses_capable`，於 `tests/contract/test_responses.py`
- [X] T015 [P] [US1] 整合測試：非串流成功呼叫經 mock 上游回傳 + 歸戶 `record_call`，於 `tests/integration/test_responses_basic.py`
- [X] T016 [P] [US1] 整合測試：串流（mock 上游 SSE 事件序列）逐步轉發 + 終局 `response.completed` 擷取 usage + 歸戶；client 斷線仍記已產生用量，於 `tests/integration/test_responses_stream.py`
- [X] T017 [P] [US1] 負向測試：回應 / 串流 / 錯誤訊息 / 日誌皆不含 provider key，於 `tests/contract/test_responses_no_key_leak.py`

### Implementation for User Story 1

- [X] T018 [US1] 實作 `POST /v1/responses`（非串流）於 `src/ai_api/proxy/responses.py`：請求驗證（`model` string、`input` 存在）→ preflight → 能力閘 → `upstream.aresponses()` → usage 對應（input→prompt / output→completion / total）→ `record_call`，使 T014/T015 轉綠
- [X] T019 [US1] 實作串流路徑：`stream=true` 以 FastAPI `StreamingResponse`（`text/event-stream`）轉發 SSE，迴圈中 tee `response.completed` 取 usage，`finally` 確保斷線也 `record_call`，使 T016 轉綠
- [X] T020 [US1] 確保錯誤封包沿用 `{error:{code,message,request_id}}` 且 message 經 redact（無 key 外洩），使 T017 轉綠
- [X] T021 [US1] 於 app 註冊 `/v1/responses` 路由（`src/ai_api/main.py` 或既有 router include）
- [X] T022 [US1] 部署：`deploy/nginx/default.conf.template` 對 `/v1/responses` 加 `proxy_buffering off` + 適當 `proxy_read_timeout`；確認 Traefik ingress 不緩衝 SSE（必要時加 annotation 於 `deploy/helm/ai-api/templates/`）
- [X] T023 [US1] 標記至少一個 Azure 模型支援 responses（`deploy/catalog/*.yaml` 補 `responses` capability）並以 CLI idempotent 載入驗證

**Checkpoint**: US1 完整——可經 quickstart.md 用 Codex 真機驗證（SC-001/005/006/007）。

---

## Phase 4: User Story 2 - 用量精確分項計費（reasoning / cached） (Priority: P2)

**Goal**: Responses 呼叫的 reasoning / cached token 精確落帳與計費；用量總覽可見分項。

**Independent Test**: 對會產生 reasoning 與 cached 命中的請求發一次呼叫，確認四類
token 分別記錄、cached 套折扣、reasoning 計入輸出不漏算。

### Tests for User Story 2 ⚠️（先寫，須先失敗）

- [X] T024 [P] [US2] 單元測試：`calculate_cost` 對 `(prompt−cached)×input + cached×cached_price + completion×output` 計算正確；cached_price 缺時 fallback input 價，於 `tests/unit/test_pricing_cached.py`
- [X] T025 [P] [US2] 整合測試：含 `output_tokens_details.reasoning_tokens` 與 `input_tokens_details.cached_tokens` 的 usage 正確對應落 `call_records` 並計價，於 `tests/integration/test_responses_billing.py`
- [X] T026 [P] [US2] 整合測試：缺價目時用量仍記錄、花費標未定價，於 `tests/integration/test_responses_billing.py`（同檔不同案例）

### Implementation for User Story 2

- [X] T027 [US2] 擴充 `src/ai_api/services/pricing.py` 的 `calculate_cost`：新增 `cached_tokens` 與 `cached_price` 參數，依公式計（reasoning 已含 output 不重複），使 T024 轉綠
- [X] T028 [US2] 擴充 `src/ai_api/services/records.py` 的 `record_call`：接受 `reasoning_tokens`/`cached_tokens` 並寫入
- [X] T029 [US2] 於 `src/ai_api/proxy/responses.py` 補 usage 分項對應（reasoning/cached）+ 取點對時 cached 價並計費，使 T025/T026 轉綠
- [X] T030 [P] [US2] 擴充 `src/ai_api/services/usage.py` 的 `aggregate_usage` 可選加總 reasoning/cached（既有三欄零退化），含對應測試於 `tests/integration/test_usage_member_scope.py` 新增案例
- [X] T031 [P] [US2] 前端用量總覽顯示 reasoning/cached 分項（`frontend/src/...` 相關元件 + vitest）

**Checkpoint**: US1 + US2 皆可獨立運作；計費精確（SC-002）。

---

## Phase 5: User Story 3 - 所有 provider 皆可經 Responses 呼叫 (Priority: P3)

**Goal**: Azure/OpenAI 高保真、Anthropic/Gemini 經 litellm 橋接皆可呼叫並計費；
未標記模型回不支援。

**Independent Test**: 分別對 OpenAI/Azure 與一個非 OpenAI 模型發起呼叫，皆成功
回應並計費；非 OpenAI 的進階能力等效降級但不報錯。

### Tests for User Story 3 ⚠️（先寫，須先失敗）

- [X] T032 [P] [US3] 整合測試：對非 OpenAI provider 模型（mock litellm 橋接）發 Responses 呼叫成功並計費，於 `tests/integration/test_responses_multiprovider.py`
- [X] T033 [P] [US3] 整合測試：未標記 `responses` capability 的模型回 `model_not_responses_capable`（跨 provider），於 `tests/integration/test_responses_multiprovider.py`（同檔）

### Implementation for User Story 3

- [X] T034 [US3] 確認 `upstream.aresponses()` 對非 OpenAI provider 經 litellm 橋接的 model 前綴/credential 解析正確（沿用既有 `provider/model` 規則），使 T032 轉綠
- [X] T035 [P] [US3] 為其他 provider 的支援模型補 `responses` capability（`deploy/catalog/*.yaml`），缺者維持不支援，使 T033 轉綠

**Checkpoint**: US1–US3 皆獨立可用（SC-003）。

---

## Phase 6: User Story 4 - Server-side 對話狀態（store / previous_response_id） (Priority: P4)

**Goal**: `store=true` 保存回應並回傳可接續 id；`previous_response_id` 接續且嚴格
歸屬隔離；逾期回找不到。

**Independent Test**: 以 store 取得 id 接續對話成功；以他人分配 id 接續被拒；逾期 id 回過期。

### Tests for User Story 4 ⚠️（先寫，須先失敗）

- [X] T036 [P] [US4] 整合測試：`store=true` 寫入 `stored_responses` 並回傳 `response_id`；以該 id 接續成功，於 `tests/integration/test_stored_responses.py`
- [X] T037 [P] [US4] 整合測試：分配 A 的 `response_id` 被分配 B 接續→ `response_forbidden`（歸屬隔離）；不存在/逾期→ `response_not_found`，於 `tests/integration/test_stored_responses.py`（同檔）
- [X] T038 [P] [US4] 單元測試：TTL 清理刪除 `expires_at ≤ now`，於 `tests/unit/test_stored_responses_cleanup.py`

### Implementation for User Story 4

- [X] T039 [US4] 建立 `src/ai_api/services/stored_responses.py`：store 寫入、`previous_response_id` 歸屬+provider+逾期查驗、id 翻譯、TTL 清理（查詢用 selectinload、delete 前先 cache 欄位），使 T036/T037/T038 轉綠
- [X] T040 [US4] 於 `src/ai_api/proxy/responses.py` 接線：`store=true` 成功後寫入、回傳平台 `response_id`；收到 `previous_response_id` 先歸屬查驗再翻譯轉發
- [X] T041 [US4] 新增逾期清理 cronjob（`deploy/helm/ai-api/templates/cronjob-*.yaml` 沿用既有模式）

**Checkpoint**: 全部 user story 獨立可用（SC-004）。

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: 跨 story 收尾與真機驗證。

- [ ] T042 跑 `specs/021-responses-api/quickstart.md` 的 Codex 真機驗證（多輪 + 工具 + 推理；`curl -N` 確認串流逐步抵達、無緩衝逾時）
- [X] T043 [P] 全測試綠 + ruff + mypy/型別檢查；Postgres 整合測試（CI）確認 migration
- [X] T044 [P] 更新 `docs/`（如 deployment / API 使用）說明 `/v1/responses` 與 Codex 設定
- [X] T045 同步 `knowledge/vision.md` 階段 11 checklist 勾選 + 將實作教訓（如 litellm 保真度、SSE 不緩衝）補入 `knowledge/experience.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**：無相依，先跑。
- **Foundational (P2)**：依賴 Setup；**阻塞所有 user story**。
- **User Stories (P3–P6)**：皆依賴 Foundational。US1 為 MVP；US2/US3/US4 在 Foundational 後可平行（若人力允許），US2 需 US1 的端點存在以驗計費、US4 需 US1 端點接線。
- **Polish (P7)**：依賴所欲交付的 story 完成。

### User Story Dependencies

- **US1 (P1)**：Foundational 後即可——MVP，無其他 story 相依。
- **US2 (P2)**：邏輯上補在 US1 端點之上（計費分項）；資料欄位已於 Foundational 備妥。
- **US3 (P3)**：補在 US1 之上（多 provider 路徑驗證），可與 US2 平行。
- **US4 (P4)**：補在 US1 端點接線之上；`stored_responses` 表已於 Foundational 備妥。

### Within Each User Story

- 測試先行且須先失敗 → 模型 → 服務 → 端點 → 整合。

### Parallel Opportunities

- T003–T006（不同檔的 model/migration 測試與類別）可平行。
- T010–T013（upstream / capability）可平行。
- 各 story 內標 [P] 的測試可平行先寫。
- Foundational 完成後，US2/US3/US4 可由不同人平行推進。

---

## Parallel Example: User Story 1

```bash
# 先平行寫 US1 測試（須先失敗）：
Task: "契約測試 /v1/responses 前置拒絕 in tests/contract/test_responses.py"
Task: "整合測試 非串流成功 in tests/integration/test_responses_basic.py"
Task: "整合測試 串流 + usage + 斷線 in tests/integration/test_responses_stream.py"
Task: "負向測試 無 key 外洩 in tests/contract/test_responses_no_key_leak.py"
```

---

## Implementation Strategy

### MVP First（僅 US1）

1. Phase 1 Setup → 2. Phase 2 Foundational（關鍵，阻塞）→ 3. Phase 3 US1 →
4. **STOP & VALIDATE**：quickstart Codex 真機驗證 → 5. 可部署/示範（MVP！）

### Incremental Delivery

Setup + Foundational → US1（MVP，Codex 可用）→ US2（精確計費）→ US3（多 provider）
→ US4（server-side 狀態）。每個 story 獨立加值、不破壞前者。

---

## Notes

- [P] = 不同檔、無相依。
- 每項實作前先有失敗測試（憲章原則 I）；commit 順序須測試先於實作。
- 重構 `/chat/completions`（T009）以既有測試為安全網，確保行為保持。
- 真機 SSE 驗證（T042）為 US1 驗收門檻，不可只靠單測（經驗：部署完成≠跑得起來）。
- 若真機發現 litellm 對 Codex 某欄位失真 → 啟動 research R1 fallback（Azure 狙擊式 raw pass-through）。
