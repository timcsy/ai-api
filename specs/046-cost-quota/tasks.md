# Tasks: 成本制配額（跨端點統一額度上限）

**Input**: Design documents from `specs/046-cost-quota/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cost-quota.md, quickstart.md

**Tests**: 包含（Constitution 原則 I Test-First 非協商）——契約/整合/單元測試先寫且先失敗，再實作。

**Organization**: 按 user story（P1/P2/P3）分階段，每個 story 獨立可測。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同檔案、無未完成依賴，可並行
- **[Story]**: US1 / US2 / US3（對映 spec 的 P1/P2/P3）

---

## Phase 1: Setup（資料與列舉基礎）

- [X] T001 在 `src/ai_api/models/allocation.py` 加 `quota_cost_usd_per_month: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)`（Phase 33；既有 token 欄不動）
- [X] T002 新 migration `alembic/versions/0020_cost_quota.py`：`op.add_column("allocations", quota_cost_usd_per_month Numeric(10,6) nullable)`（純加欄，含 downgrade `drop_column`）；本機驗 `alembic upgrade head` + `downgrade`
- [X] T003 [P] 在 `src/ai_api/models/call_record.py` 的 `CallOutcome` 加 `rejected_cost_quota_exceeded = "rejected_cost_quota_exceeded"`（`Enum(native_enum=False)` → 無 migration）

**Checkpoint**: 分配可存花費上限、新拒絕 outcome 可用——Foundational 可開工

---

## Phase 2: Foundational（阻塞所有 user story）

**⚠️ CRITICAL**: 本階段未完成前，US1–US3 無法開工（三者都要 `current_month_cost`）

- [X] T004 [P] 單元測試（先失敗）：`tests/unit/test_quota.py` 加 `current_month_cost`（成功、本月、`coalesce(cost_usd,0)` 之 Decimal 總和；未定價以 0 計）與 `is_over_cost_quota`（cap None→False、`spent >= cap`→True）
- [X] T005 在 `src/ai_api/services/quota.py` 實作 `current_month_cost(db, allocation_id) -> Decimal`（對稱 `current_month_usage`，`sum(CallRecord.cost_usd)`，命中既有索引）+ `is_over_cost_quota(allocation, spent)`

**Checkpoint**: 花費累計與判斷可用——US1/US2/US3 皆可獨立進行

---

## Phase 3: User Story 1 - admin 設花費上限、超額即擋（Priority: P1）🎯 MVP

**Goal**: 設了花費上限的分配，token 與非 token 累計花費達上限後，後續呼叫一律被擋；未設者零回歸。

**Independent Test**: 為分配設上限，混送 chat + OCR 使累計達上限 → 後續 403 `cost_quota_exceeded`；未設上限者行為不變。

### Tests for User Story 1 ⚠️（先寫、先失敗）

- [X] T006 [P] [US1] 契約測試：設花費上限、混合 token+非 token 累計達上限 → 後續呼叫 403 `cost_quota_exceeded` 且落一筆 `rejected_cost_quota_exceeded`（`tests/contract/test_cost_quota.py`）
- [X] T007 [P] [US1] 契約測試：未設花費上限 → 非 token 呼叫不被擋、token 配額行為零回歸（同檔）
- [X] T008 [P] [US1] 契約測試：同設 token+花費兩種上限 → 先達到者擋（兩種各驗一次）（同檔）
- [X] T009 [P] [US1] 契約測試：未定價模型呼叫 → 不增加累計、不被花費上限擋（同檔）

### Implementation for User Story 1

- [X] T010 [US1] `src/ai_api/proxy/preflight.py`：在既有 token 配額檢查後並列一道 cost 檢查（`quota_cost_usd_per_month` 非 None 且 `current_month_cost >= cap` → `PreflightRejection("cost_quota_exceeded", …, 403, allocation)`）
- [X] T011 [US1] `src/ai_api/proxy/router.py` 的 `_outcome_for_code` 加 `"cost_quota_exceeded": CallOutcome.rejected_cost_quota_exceeded`（拒絕仍走既有 `record_call`、綁 allocation）
- [X] T012 [US1] admin 分配 create/update 收選填 `quota_cost_usd_per_month`（`src/ai_api/api/allocations.py` + `src/ai_api/api/schemas.py`，`>= 0` 驗證、null 清除、變更留稽核）+ 分配序列化回傳此欄
- [X] T013 [P] [US1] 前端：admin 配額編輯 Dialog 加「每月花費上限（USD）」欄（`frontend/src/` 既有配額編輯處），含一句「只治理已定價用量」說明

**Checkpoint**: MVP 成立——admin 能設、所有同步端點受治理、未設者零回歸

---

## Phase 4: User Story 2 - 即時字幕連線中超額即被中止（Priority: P2）

**Goal**: realtime 長連線進行中累計花費超過上限 → 約定時間內主動 close，已累計時長落帳。

**Independent Test**: 低上限 + 持續送音訊使累計超額 → N 秒內被 close + 落帳（mock provider WS）。

### Tests for User Story 2 ⚠️（先寫、先失敗）

- [X] T014 [P] [US2] 整合測試：realtime 連線中累計花費超過上限 → N 秒內 close（policy violation）+ 已累計時長落帳（`tests/contract/test_realtime_transcription.py`，沿用既有 mock provider WS + 直接呼叫 `handle_realtime` + 注入 `check_active`/低 `revoke_interval`）

### Implementation for User Story 2

- [X] T015 [US2] `src/ai_api/proxy/realtime.py`：加 `session_running_cost(sess, price)`（= `session_quantity(sess, price.unit) × price.per_unit`）+ 擴充旁路 watcher——每 tick 核對 `current_month_cost(allocation) + running >= cap` → 翻 `close_reason`、停 relay
- [X] T016 [US2] `src/ai_api/proxy/realtime.py`：cost 觸發的 close 走既有「任何 close 路徑都落帳」（必要時加 `close_reason="cost_exceeded"` 並映 close code/outcome；確認 `_bill_session` 不漏記）

**Checkpoint**: US1 + US2——長連線也被花費上限即時把關

---

## Phase 5: User Story 3 - 成員/admin 看「本月花費 / 上限」（Priority: P3）

**Goal**: 成員與 admin 都看得到每分配「本月已花 / 上限」。

**Independent Test**: 設上限後，成員用量頁、admin 分配詳情皆顯示「本月花費 / 上限」。

### Tests for User Story 3 ⚠️（先寫、先失敗）

- [X] T017 [P] [US3] 序列化/契約測試：`/me/usage`（與 admin 用量）每分配回 `cost_used_this_month`（Decimal 字串）+ `quota_cost_usd_per_month`（`tests/contract/test_me_usage.py`）

### Implementation for User Story 3

- [X] T018 [US3] `src/ai_api/api/me.py` + `src/ai_api/api/usage.py`：每分配序列化加 `cost_used_this_month`（`current_month_cost`）+ `quota_cost_usd_per_month`（成員只看自己、嚴格隔離沿用既有）
- [X] T019 [P] [US3] 前端：分配卡 + 用量頁顯示「本月花費 $X / 上限 $Y」+ 接近上限提示（`frontend/src/` 既有用量/分配顯示處）

**Checkpoint**: 三個 user story 全部獨立可用

---

## Phase 6: Polish & Cross-Cutting

- [X] T020 [P] 整合測試：自適應配額池跑一輪後，各分配 `quota_cost_usd_per_month` **不變**（只 token 額度被再分配）（`tests/integration/test_quota_pool_rebalance.py`，SC-005）
- [X] T021 全綠關卡：`ruff check .` + mypy + 完整 `pytest tests/` 零回歸 + 前端 tsc/vitest/build；**既有配額 contract 測試 git diff 為空**（SC-003）
- [X] T022 部署後煙霧（quickstart.md）：有 migration → `--set migrationJob.enabled=true`；`kubectl exec <pod> -- python3 -m alembic current` 顯 `0020`；admin 設一個低上限對自己分配真打驗一次（同步端點 + realtime 連線中各一）

---

## Dependencies & Execution Order

- **Setup（T001–T003）**：無依賴；T003 與 T001/T002 可並行（不同檔）
- **Foundational（T004–T005）**：依賴 Setup；**BLOCKS 所有 user story**
- **US1（P1）/ US2（P2）/ US3（P3）**：皆依賴 Foundational；三者彼此獨立可並行（US1 改 preflight、US2 改 realtime、US3 改 usage 序列化，不同檔）
  - 建議順序 US1（MVP）→ US2 → US3，但無硬依賴
- **Polish（T020–T022）**：依賴所需 user story 完成

### Within Each User Story
- 測試先寫且先失敗 → 實作 → 重構
- 同 story 內：跨檔測試/前端標 [P]；改同一檔（preflight、realtime.py）的實作任務為順序

### Parallel Opportunities
- T001 / T003（Setup）可並行
- 各 story 測試任務（T006–T009、T014、T017）標 [P] 可並行先寫
- 前端任務（T013、T019）與後端不同檔，可並行
- 三個 user story 因落在不同檔（preflight / realtime / usage），整體可並行推進

---

## Implementation Strategy

### MVP First（User Story 1）
1. Setup（T001–T003）→ 2. Foundational（T004–T005）→ 3. US1（T006–T013）→ **STOP & VALIDATE**（混合端點累計超額被擋、token 零回歸＝MVP）→ 視情況先上線。

### Incremental Delivery
1. Setup + Foundational → 花費累計可算
2. US1 → 同步端點花費治理（MVP，可上線）
3. US2 → 長連線連線中把關（realtime 治理完整）
4. US3 → 成員/admin 可見性
5. Polish（自適應池隔離測試 + 全綠 + 部署煙霧）

### 零回歸鐵證
- 既有配額相關 contract 測試**斷言不改全綠、git diff 為空**（SC-003）；只設 token 上限者行為 byte-identical。

## Notes
- [P] = 不同檔、無依賴；改 `preflight.py` / `realtime.py` 同檔的實作任務為順序。
- 加欄位（`quota_cost_usd_per_month`）要追到所有 sink（preflight、admin API/UI、用量顯示、**自適應池要刻意排除**）——對照 `quota_tokens_per_month` 既有出現點（experience「加欄位追到所有 sink」）。
- migration 後跑 Postgres 整合測試固化零回歸（experience「SQLite 寬鬆、Postgres 嚴格」）。
- 改 `CallOutcome`（T003）後重跑完整 `pytest tests/`（experience「動列舉/對映後全套件重跑」）。
