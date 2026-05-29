# Tasks: 階段 3a — 用量觀測與費用計算

**Input**: Design documents from `/specs/004-usage-billing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: TDD enforced（constitution Principle I + spec SC-008）。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`<repo-root>`

---

## Phase 1: Setup

- [ ] T001 在 `src/ai_api/config.py` 新增 `cors_origins: list[str] = Field(default=[], alias="CORS_ORIGINS")`
- [ ] T002 [P] 更新 `.env.example` 加 `# CORS_ORIGINS='["http://localhost:5173"]'` 註解範例
- [ ] T003 [P] 建立 `deploy/prices/azure-2026-05.yaml` 範例價目（azure / gpt-4o-mini / gpt-4o 兩條）
- [ ] T004 [P] 建立 `deploy/prices/azure-2026-06-double.yaml` — 漲價測試用（input × 2、effective_from 一個月後）

---

## Phase 2: Foundational

### Models 擴充

- [ ] T005 [P] 修改 `src/ai_api/models/allocation.py`：加 `quota_tokens_per_month: Mapped[int | None]` + `is_service_allocation: Mapped[bool]`
- [ ] T006 [P] 修改 `src/ai_api/models/call_record.py`：加 `cost_usd: Mapped[Decimal | None]` (Numeric(10,6))；`CallOutcome` enum 加 `rejected_quota_exceeded`
- [ ] T007 [P] 建立 `src/ai_api/models/price_list.py`：PriceList ORM 模型（依 data-model.md，含 UNIQUE 與 lookup index）
- [ ] T008 修改 `src/ai_api/models/__init__.py` re-export `PriceList`

### Migration

- [ ] T009 建立 `alembic/versions/0004_usage_billing.py`：
   1. CREATE TABLE `price_list` + indexes
   2. ALTER `allocations` ADD `quota_tokens_per_month` (int nullable) + `is_service_allocation` (bool default false)
   3. ALTER `call_records` ADD `cost_usd` (numeric(10,6) nullable)
   4. 擴充 `call_records.outcome` enum 加 `rejected_quota_exceeded`（沿用 0003 的 batch_alter 模式）

### Foundational services

- [ ] T010 [P] 建立 `src/ai_api/services/pricing.py` 骨架：`lookup_price_for_call(provider, model, ts)` + `calculate_cost(prompt_tokens, completion_tokens, price)` 純函式
- [ ] T011 [P] 建立 `src/ai_api/services/quota.py` 骨架：`current_month_start_utc(now)` + `current_month_usage(allocation_id)` + `is_over_quota(allocation, current_usage)`
- [ ] T012 [P] 建立 `src/ai_api/services/usage.py` 骨架：`aggregate_usage(group_by, from_, to, service_only)` + `usage_timeseries(allocation_id, bucket, from_, to)` 骨架

**Checkpoint**：Phase 1+2+2.5 既有 97 tests 仍綠（無回歸）。

---

## Phase 3: US5 — PriceList YAML loader (P1)

**Goal**：CLI 載入 YAML 入 PriceList 表；point-in-time 不可回溯。

### Tests for US5

- [ ] T013 [P] [US5] 單元測試 `tests/unit/test_price_lookup.py`：
   - lookup 找到最新適用價目
   - lookup 找不到回 None
   - calculate_cost 邊界（NULL tokens、0 tokens）
- [ ] T014 [P] [US5] 整合測試 `tests/integration/test_us5_pricelist_pit.py`：
   - 載入 yaml v1 → 跑呼叫 → CallRecord.cost_usd 為 X
   - 載入 yaml v2（2x price） → 跑新呼叫 → 新 CallRecord.cost_usd 為 2X；舊筆不變
   - 違反 UNIQUE → 載入 exit 1

### Implementation for US5

- [ ] T015 [P] [US5] 實作 `lookup_price_for_call` 與 `calculate_cost` 於 `src/ai_api/services/pricing.py`
- [ ] T016 [US5] 建立 `src/ai_api/cli/load_prices.py`：parse YAML、驗 schema、逐筆 INSERT，違反 UNIQUE 即 rollback + exit 1；正常結束印 `loaded N entries`
- [ ] T017 [US5] 修改 `src/ai_api/proxy/router.py`：success 路徑在 `record_call` 之前查 PriceList，傳 `cost_usd` 給 `record_call`
- [ ] T018 [US5] 修改 `src/ai_api/services/records.py` 的 `record_call`：接受 `cost_usd` 參數，寫入 CallRecord

**Checkpoint**：成本資料開始累積，後續 US1/US2/US6 都依賴此。

---

## Phase 4: US3 — 月配額 (P1)

**Goal**：每月 token 上限；超過拒絕。

### Tests for US3

- [ ] T019 [P] [US3] 單元測試 `tests/unit/test_quota_check.py`：
   - `current_month_start_utc(2026-05-15T12:00Z)` → `2026-05-01T00:00:00Z`
   - `is_over_quota` 邊界：quota=NULL 永遠 false；quota=100 / usage=99 → false；usage=100 → true
- [ ] T020 [P] [US3] 契約測試 `tests/contract/test_quota_patch.py`：
   - PATCH 設 `quota_tokens_per_month=100` → 200
   - PATCH 設 `quota_tokens_per_month=null` → 200（unlimited）
- [ ] T021 [P] [US3] 整合測試 `tests/integration/test_us3_quota_enforcement.py`：
   - 種 99 tokens、quota=100 → 呼叫成功
   - 種 100 tokens、quota=100 → 第 N+1 次呼叫回 403 `quota_exceeded`
   - quota=null → 不擋

### Implementation for US3

- [ ] T022 [P] [US3] 實作 `current_month_usage` + `is_over_quota` 於 `src/ai_api/services/quota.py`
- [ ] T023 [US3] 修改 `src/ai_api/api/allocations.py`：擴充 PATCH endpoint 接受 `quota_tokens_per_month` + `is_service_allocation`（暫忽略後者，US4 一起接）
- [ ] T024 [US3] 修改 `src/ai_api/api/schemas.py` 的 `AllocationOut`：加 quota / is_service_allocation 欄位
- [ ] T025 [US3] 修改 `src/ai_api/proxy/router.py`：allocation lookup 後、model_binding 之前，插入 `quota.is_over_quota` 檢查；超過即 `record_and_respond("quota_exceeded", ..., 403)`
- [ ] T026 [US3] 修改 `src/ai_api/proxy/router.py` 的 `_outcome_for_code`：加 `quota_exceeded → CallOutcome.rejected_quota_exceeded`

---

## Phase 5: US1 — Aggregate usage 查詢 (P1)

**Goal**：by member / allocation / model 聚合。

### Tests for US1

- [ ] T027 [P] [US1] 契約測試 `tests/contract/test_usage_endpoint.py`：
   - `from/to/group_by` 必填驗證
   - 區間 > 90 天 → 400 `range_too_wide`
   - `from >= to` → 400 `invalid_time_range`
   - 三種 group_by 各回正確 shape
- [ ] T028 [P] [US1] 整合測試 `tests/integration/test_aggregation.py`：
   - 種 3 個 Member、各 2 個 allocation、各跑 10 次呼叫（已有 cost）→ 三種 group_by 聚合結果手算對得上

### Implementation for US1

- [ ] T029 [P] [US1] 實作 `aggregate_usage` 於 `src/ai_api/services/usage.py`（SQL Core JOIN + GROUP BY，依 data-model.md Q2）
- [ ] T030 [US1] 建立 `src/ai_api/api/usage.py`：`GET /admin/usage` endpoint
- [ ] T031 [US1] 註冊 usage router 於 `src/ai_api/main.py`（prefix `/admin`, dependencies admin token）

---

## Phase 6: US2 — Timeseries 查詢 (P1)

**Goal**：單分配每日/每小時 bucket。

### Tests for US2

- [ ] T032 [P] [US2] 契約測試 `tests/contract/test_usage_timeseries.py`：
   - `bucket=hour` + 區間 > 7 天 → 400 `range_too_wide_for_bucket`
   - 404 當 allocation 不存在
   - 200 回 `{allocation_id, bucket, points: [...]}`
- [ ] T033 [P] [US2] 整合測試 `tests/integration/test_timeseries.py`：種 3 天資料每天 5 筆呼叫 → bucket=day 回 3 點 + 每點 tokens=5×N

### Implementation for US2

- [ ] T034 [P] [US2] 實作 `usage_timeseries` 於 `src/ai_api/services/usage.py`（dialect-aware：Postgres date_trunc、SQLite strftime）
- [ ] T035 [US2] 加 `GET /admin/allocations/{id}/usage-timeseries` endpoint 於 `src/ai_api/api/usage.py`

---

## Phase 7: US4 — Service allocation flag (P2)

**Goal**：標記服務型分配；usage 查詢可過濾。

### Tests for US4

- [ ] T036 [P] [US4] 契約測試擴充 `tests/contract/test_quota_patch.py`：PATCH `is_service_allocation=true` → 200，回應含此欄位
- [ ] T037 [P] [US4] 契約測試擴充 `tests/contract/test_usage_endpoint.py`：`?service_only=true` 只回服務型分配

### Implementation for US4

- [ ] T038 [US4] 修改 `src/ai_api/api/allocations.py` 的 PATCH endpoint：完整支援 `is_service_allocation` 欄位
- [ ] T039 [US4] 修改 `src/ai_api/services/usage.py`：`aggregate_usage` 加 `service_only` filter；group_by=allocation 時 result item 帶 `is_service_allocation`

---

## Phase 8: US6 — CSV / JSON 匯出 (P2)

**Goal**：用量資料匯出。

### Tests for US6

- [ ] T040 [P] [US6] 單元測試 `tests/unit/test_csv_writer.py`：CSV header + quoting 含 `,` / 換行 / `"` 的欄位正確處理
- [ ] T041 [P] [US6] 契約測試 `tests/contract/test_usage_export.py`：
   - `.csv` → `Content-Type: text/csv`
   - `.json` → `Content-Type: application/json`
   - 區間 > 90 天 → 400

### Implementation for US6

- [ ] T042 [US6] 加 `GET /admin/usage.csv` + `GET /admin/usage.json` endpoints 於 `src/ai_api/api/usage.py`（用 `StreamingResponse` + stdlib `csv`）

---

## Phase 9: US7 — CORS 預備 (P2)

**Goal**：CORS allowlist + 動態 SameSite。

### Tests for US7

- [ ] T043 [P] [US7] 契約測試 `tests/contract/test_cors.py`：
   - allowlist 內 origin OPTIONS preflight → 200 + ACAO
   - 非 allowlist origin → 無 ACAO header
   - cors_origins 非空時 cookie 設 `SameSite=None; Secure`
   - cors_origins 空時 cookie 設 `SameSite=Lax`

### Implementation for US7

- [ ] T044 [US7] 修改 `src/ai_api/main.py`：當 `settings.cors_origins` 非空時加 `CORSMiddleware`（allow_credentials=True）
- [ ] T045 [US7] 修改 `src/ai_api/api/auth.py` 的 `_set_session_cookie`：根據 `settings.cors_origins` 是否非空切換 SameSite 與 Secure

---

## Phase 10: Polish

- [ ] T046 跑全套測試 `uv run pytest -q`，確認既有 97 tests 全綠 + 新增測試全綠
- [ ] T047 [P] 在 `tests/contract/test_no_key_leak_global.py` 加 `quota_exceeded` 情境
- [ ] T048 [P] 更新 `README.md`：加「Phase 3a 用量觀測與費用計算」段落
- [ ] T049 [P] 修改 `deploy/helm/ai-api/templates/secret.yaml` 加 `CORS_ORIGINS` 鍵；`values.yaml` 加對應預設
- [ ] T050 跑 quickstart §1~§6 逐項驗證，把結果寫入 `specs/004-usage-billing/quickstart-run-notes.md`
- [ ] T051 對 `quickstart-run-notes.md` 標 SC-001~SC-008 通過情形
- [ ] T052 在 `knowledge/vision.md` 把階段 3 的 checkbox（屬於 3a 的成功標準）由 `[ ]` → `[x]`，並加註「3a 完成；3b UI 待開」

---

## Dependencies

```
Phase 1 Setup
   │
   ▼
Phase 2 Foundational (Alembic 0004 + service skeletons)
   │
   ├─→ Phase 3 (US5 PriceList CLI)            ←─ FIRST P1; provides cost data
   │       │
   │       ▼
   │  Phase 4 (US3 Quota)                     ←─ 依 cost? 不依 — 只用 token counts。
   │                                             可與 US5 並行；建議 US5 先做
   │       │
   ├─→ Phase 5 (US1 Aggregate)                ←─ 依 US5 cost 資料才有意義
   │       │
   │       ▼
   │  Phase 6 (US2 Timeseries)
   │
   ├─→ Phase 7 (US4 Service flag)             ←─ 與 US1/US3 共用 Allocation；獨立
   ├─→ Phase 8 (US6 CSV/JSON)                 ←─ 依 US1 service 完成
   └─→ Phase 9 (US7 CORS)                     ←─ 完全獨立 (config + middleware)

Phase 10 Polish
```

**Story dependencies**：
- **US5 (PriceList)** 應第一個做 — 提供 cost data 給 US1/US2/US6
- **US3 (Quota)** 與 US5 互不相依，可並行
- **US1/US2** 需 US5 完成才能驗 cost 聚合
- **US4** 與 US3 共用 Allocation schema 修改；建議合併實作
- **US7 CORS** 完全獨立

---

## Parallel Execution Opportunities

- **Phase 1**：T002 / T003 / T004 並行
- **Phase 2**：T005 / T006 / T007 並行；T010 / T011 / T012 並行
- **Phase 3 (US5)**：T013 / T014 測試並行；T015 / T016 / T017 順序（router 改完 records 改完才行）
- **Phase 4 (US3)**：T019 / T020 / T021 測試並行；T022 與 T023~T026 部分可並行
- **Phase 5 (US1)**：T027 / T028 測試並行；T029 / T030 / T031 順序
- **Phase 6 (US2)**：T032 / T033 並行；T034 / T035 順序
- **Phase 7 (US4)**：T036 / T037 並行；T038 / T039 不同檔案可並行
- **Phase 8 (US6)**：T040 / T041 並行；T042 收尾
- **Phase 9 (US7)**：T043 → T044 → T045 大致順序但 T044/T045 不同檔案可並行
- **Phase 10**：T047 / T048 / T049 並行

---

## Implementation Strategy

### MVP 建議優先序

1. **Phase 1+2**（基底）
2. **US5 PriceList CLI** — 沒成本資料就沒有用量觀測的意義
3. **US3 月配額** — 預算保護先上
4. **US1 Aggregate** — 第一個面向使用者的查詢功能
5. **US2 Timeseries**
6. **US4 Service flag** — 與 US3 schema 共用，順手做
7. **US6 CSV/JSON 匯出**
8. **US7 CORS 預備** — 為階段 3b 做準備，可最後做

### TDD 紀律

每個 story 內測試任務先 commit（失敗 commit），再 commit 實作（綠 commit）。
SC-008 要求 git 歷史可驗證 test < impl 順序。

### Risk Hot Spots

1. **聚合 SQL 跨 dialect**：Postgres `date_trunc` vs SQLite `strftime`。
   T034 必須抽 helper 並在兩種 backend 都測。
2. **配額檢查放錯位置**：必須在 `lookup_by_token` 後（要 allocation_id）+
   `model_binding` 之前（拒絕配額不必再做 model 檢查）— T025 加在錯地方會
   讓 quota 紀錄歸錯 allocation。
3. **CORS + SameSite 邏輯翻轉**：CORS 空 → Lax；非空 → None+Secure。寫反
   會在跨域時 cookie 不帶。T045 整合測試必跑兩種設定。
4. **CSV BOM**：UTF-8 BOM 加錯位置會讓 JSON parser 也踩到 — 只在 CSV 路徑
   加，不要在 base StringIO。

---

## Format Validation

✅ 全部 52 個任務符合 `- [ ] T### [P?] [USx?] 描述 + 路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-9 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
