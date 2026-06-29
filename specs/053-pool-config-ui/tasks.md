---
description: "Task list for 配額池設定移到前端（admin 可編輯 T／保底 + 建議值）"
---

# Tasks: 配額池設定移到前端（admin 可編輯 T／保底 + 建議值）

**Input**: Design documents from `/specs/053-pool-config-ui/`
**Prerequisites**: spec.md、plan.md、research.md、data-model.md、contracts/quota-pool-config.md、quickstart.md（皆已產出）

**Tests**: constitution 強制 TDD——測試先於實作（紅→綠）。後端擴充既有 `tests/contract/test_quota_pool_api.py` + `tests/integration/test_quota_pool_rebalance.py`；前端新增 pool-config 測試。

**檔案協調**：後端 `api/quota_pool.py`、`services/quota_pool.py` 多個 story 共改 → 同檔序列。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 基線：`python -m pytest tests/contract/test_quota_pool_api.py tests/integration/test_quota_pool_rebalance.py tests/unit/test_compute_rebalance.py -q` + `cd frontend && npx vitest run src/__tests__/quota-pool*.test.tsx 2>/dev/null || true` 確認起點綠（之後比對零回歸）。

---

## Phase 2: Foundational（阻斷性前置——所有 story 都依賴）

**Purpose**: 把 T／保底搬到 DB 單例 + 單一真理讀取入口 + 首讀 lazy-seed；這是 US1/US2/US3 的共同地基（零行為變更）。

- [X] T002 在 `tests/integration/test_quota_pool_rebalance.py`（或新 `test_pool_config.py`）寫**失敗整合測試**（testcontainers Postgres）：① 全新 DB（無 `pool_config` 列）呼叫 `get_pool_config` → 回現行 `settings.pool_*` 值且**建立列**（lazy-seed）；② `apply_rebalance` 採用的 T／保底 = `get_pool_config` 的值（非直接讀 settings）；③ PUT 改值後 `apply_rebalance` 用新值。先紅。
- [X] T003 新建 `src/ai_api/models/pool_config.py`：`PoolConfig` 單例（`id` PK + `CHECK (id = 1)`、`total_tokens_per_month` int、`floor_per_allocation` int、`updated_at` `DateTime(timezone=True)`、`updated_by` str nullable），比照 `models/notification.py` 單例慣例；於 `models/__init__.py` 匯出。
- [X] T004 新建 `alembic/versions/0021_pool_config.py`：create table `pool_config`（純加表，down_revision=0020）；upgrade/downgrade 對稱。
- [X] T005 在 `src/ai_api/services/quota_pool.py` 新增 `get_pool_config(db) -> PoolConfig`：get-or-create——無列時用 `get_settings().pool_total_tokens_per_month`/`pool_floor_per_allocation` 建列（lazy-seed）、commit、回傳。
- [X] T006 [改讀取點＝單一真理] `services/quota_pool.py::apply_rebalance` 與 `api/quota_pool.py::get_pool_status` 改用 `get_pool_config(db)` 取 T／保底，**不再直接讀 `settings.pool_*`**（config.py 的 `pool_*` 保留為 lazy-seed 來源）。
- [X] T007 跑 T002 的整合測試轉綠 + `alembic upgrade head`/`downgrade` 驗 0021 對稱；確認既有 `test_quota_pool_rebalance.py` 零回歸。

**Checkpoint Foundational**: T／保底由 DB 單例供應、首讀 seed 自 env、rebalance 與監控同源。

---

## Phase 3: User Story 1 — admin 介面設定 T／保底即時生效（Priority: P1）🎯 MVP

**Goal**: admin 在監控頁設 T／保底、儲存持久化、下次再分配採用；留稽核。

**Independent Test**: PUT 設值 → GET 顯示新值 → 手動再分配以新值算。

- [X] T008 [US1] 在 `tests/contract/test_quota_pool_api.py` 加**失敗契約測試**：`PUT /admin/quota-pool/config {T,floor}` → 200 持久化、`GET /admin/quota-pool/status` 的 `config` 即新值、且寫稽核 `pool_config_updated`。先紅。
- [X] T009 [US1] 在 AuditEventType 加 `pool_config_updated`（`native_enum=False`、無 migration）。
- [X] T010 [US1] 在 `api/quota_pool.py` 新增 `PUT /quota-pool/config`：收 {total_tokens_per_month, floor_per_allocation}、更新 `PoolConfig`（set `updated_at`/`updated_by`）、寫稽核、回新 config。
- [X] T011 [US1] `api/quota_pool.py::get_pool_status` 回應加 `config` 區塊（來自 `get_pool_config`）。
- [X] T012 [US1] `frontend/src/routes/admin/quota-pool.tsx` 加編輯表單（T／保底輸入 + 儲存，呼叫 PUT、成功後 invalidate status query）；新增 `frontend/src/__tests__/quota-pool-config.test.tsx` 渲染/儲存測試。
- [X] T013 [US1] 跑 `pytest tests/contract/test_quota_pool_api.py -q` + 前端該測試轉綠。

**Checkpoint US1**: admin 可在 UI 設值、生效於再分配、可稽核。

---

## Phase 4: User Story 2 — 介面給「該設多少」建議 + 原因（Priority: P1）

**Goal**: 依近月用量算建議 T／保底 + 原因，一鍵套用。

**Independent Test**: GET 回 suggestion（近月用量、建議 T、建議保底、N）；前端建議區可套用。

- [X] T014 [US2] 在 `tests/contract/test_quota_pool_api.py` 加失敗測試：`GET /admin/quota-pool/status` 回 `suggestion`（含 `recent_month_tokens`、`suggested_total`≈近月×2、`suggested_floor`）與 `pool_members` N。先紅。
- [X] T015 [US2] 在 `services/quota_pool.py` 加 `suggest_pool_config(db)`：用 `services/usage.py::aggregate_usage`（近月 total_tokens）+ 池內成員數 N 算建議（T=round(近月×2)、保底=可用基本額量級）。
- [X] T016 [US2] `get_pool_status` 回應加 `suggestion` + `pool_members`。
- [X] T017 [US2] `quota-pool.tsx` 加建議區（顯示近月用量/建議值/原因 + 「套用建議」填入表單）；測試斷言建議顯示 + 套用。
- [X] T018 [US2] 跑相關 contract + 前端測試轉綠。

**Checkpoint US2**: 建議值就地可見、可一鍵套用。

---

## Phase 5: User Story 3 — 防呆驗證（Priority: P2）

**Goal**: T<保底×N 擋下、負數擋下、T<近月用量警告；顯示 N + 生效時機。

**Independent Test**: PUT 違規值被擋/警告；頁面顯示 N 與「下次再分配生效」。

- [X] T019 [US3] 在 `tests/contract/test_quota_pool_api.py` 加失敗測試：PUT `T < floor×N` → 422 `invalid_pool_config` 且未改 DB；PUT 負數 → 422；T < 近月用量 → GET `warning` 非 null（不擋）。先紅。
- [X] T020 [US3] 在 PUT handler 加驗證（`T≥floor×N`、`T≥0`、`floor≥0`，違反 422）；`get_pool_status` 在 T<近月用量時回 `warning` 字串。
- [X] T021 [US3] `quota-pool.tsx` 表單加前端驗證（同規則、即時提示）+ 顯示池內成員數 N + 「設定於下次再分配生效」標註；測試斷言。
- [X] T022 [US3] 跑相關測試轉綠。

**Checkpoint US3**: 設錯有護欄、生效時機清楚。

---

## Phase 6: Polish & 上線

- [X] T023 全套零回歸：`python -m pytest tests/ -q` + `ruff check .` + `uv run mypy src/ai_api`；前端 `cd frontend && npx vitest run`（全套）+ `npx tsc --noEmit; echo $?`（看真退出碼）+ `npm run build`。〔呼應「本機關卡逐字對齊 CI、別讓 pipe 吃退出碼」〕
- [ ] T024 PR + squash-merge（CI 全綠）。**後端+前端兩 image bump**；**有 migration → `--set migrationJob.enabled=true`**：helm `--reuse-values` + `--set image.tag=sha-<new>` + `--set frontend.image.tag=sha-<new>` + storedResponseCleanup。部署後驗 `alembic current=0021`、`GET /admin/quota-pool/status` 回 config/suggestion。
- [ ] T025 真機驗收：admin 在監控頁設 T／保底 → 按手動再分配 → 各分配配額更新；建議套用可用；T<floor×N 被擋。
- [ ] T026 知識同步：`knowledge/vision.md` 階段 39 標 ✅（rev 待定）+ 現狀/狀態同步；`knowledge/experience.md` 蒸餾「把 config 從 env 搬 DB 時，**所有讀取點都要改指向單一入口**（否則顯示≠執法 drift）+ 首讀 lazy-seed 保零行為變更」。

---

## Dependencies & Execution Order

- **Setup（T001）** → 之前。
- **Foundational（T002–T007）**：阻斷全部——model + migration + `get_pool_config` + 改讀取點 + lazy-seed。US1/US2/US3 全依賴它。
- **US1（T008–T013）**：依賴 Foundational；MVP（沒它 admin 不能設）。
- **US2（T014–T018）**：依賴 Foundational（`get_pool_config` + status）；與 US1 多在同檔（`api/quota_pool.py`/`quota-pool.tsx`）→ 接 US1 之後序列。
- **US3（T019–T022）**：依賴 US1 的 PUT（在其上加驗證）。
- **Polish（T023–T026）**：全部後。

### 平行機會
- Foundational 內：T003（model）∥ T004（migration）可先後但獨立；T002（測試）先。
- 後端 `api/quota_pool.py` 是 US1/US2/US3 共改檔 → 該檔任務序列；前端 `quota-pool.tsx` 同理。
- 後端與前端任務可跨子系統並行。

## Implementation Strategy

- **地基優先**：Foundational（DB 單例 + 單一真理 + lazy-seed）是這刀的風險核心（零行為變更），先穩。
- **MVP = Foundational + US1**：admin 能在 UI 設值並生效即達主要價值；US2 建議、US3 護欄疊加。
- **單一真理鐵律**：T／保底只剩 DB 一個可改處；env 退 bootstrap；監控顯示值＝rebalance 採用值（追全所有讀取點）。
- 後端+前端兩 image、一個 PR、有 migration（migrationJob.enabled=true）。
