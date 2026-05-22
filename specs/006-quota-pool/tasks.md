# Tasks: 階段 3c — Adaptive Quota Pool

**Input**: Design documents from `/specs/006-quota-pool/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: TDD enforced（constitution + SC-008）— unit test (pure algorithm) → contract → integration。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

- [ ] T001 [P] `src/ai_api/config.py`：新增 `pool_total_tokens_per_month: int = Field(default=0, alias="POOL_TOTAL_TOKENS_PER_MONTH")` 與 `pool_floor_per_allocation: int = Field(default=1000, alias="POOL_FLOOR_PER_ALLOCATION")`
- [ ] T002 [P] `.env.example`：加 `POOL_TOTAL_TOKENS_PER_MONTH` 與 `POOL_FLOOR_PER_ALLOCATION` 範例註解

---

## Phase 2: Foundational

### Models + Migration（所有 US 共用）

- [ ] T003 建立 `src/ai_api/models/rebalance_log.py`：`RebalanceLog` ORM model（schema 依 data-model.md）
- [ ] T004 修改 `src/ai_api/models/allocation.py`：加 `quota_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)`
- [ ] T005 修改 `src/ai_api/models/auth_audit.py`：`AuditEventType` enum 加 `quota_pool_rebalanced`、`rebalance_failed`、`pool_exhausted_by_reserved`、`pool_idle` 4 個值
- [ ] T006 修改 `src/ai_api/models/__init__.py`：export `RebalanceLog`
- [ ] T007 建立 Alembic migration `alembic/versions/0005_quota_pool.py`：
  - CREATE TABLE `rebalance_log`（含 partial UNIQUE on `period_yyyymm WHERE triggered_by='cron'`，Postgres）；SQLite 用 `UNIQUE(period_yyyymm, triggered_by)` 替代
  - ALTER `allocations` ADD `quota_locked` (bool default false, NOT NULL)
  - `auth_audit_log.event_type` enum 擴充（沿用 0003/0004 batch_alter 模式）

### 服務骨架（避免循環 import）

- [ ] T008 [P] 建立 `src/ai_api/services/quota_pool.py` 骨架：
  - `compute_rebalance(...)` 純函式 stub（先回固定值）
  - `apply_rebalance(...)` async stub（先 raise NotImplementedError）
  - module-level docstring 解釋分層意圖（依 research.md §1）

**Checkpoint**：`uv run alembic upgrade head` 通過；既有 140 tests 仍綠（無回歸）。

---

## Phase 3: US1 — 自動再分配 + 守恆 (P1)

**Goal**：純演算法 → DB apply → 守恆驗證。
**Independent Test**：unit test 對 boundary case 全綠；integration test seed 3 個 allocation 跑出 450/310/240。

### Tests First

- [ ] T009 [US1] 建立 `tests/unit/test_compute_rebalance.py`：覆蓋 boundary case
  - cold start（Σ usage = 0）→ 均分 + 每人 ≥ floor
  - 一般情況 T=1000、floor=100、3 人 usage=5:3:2 → [450, 310, 240]
  - 守恆驗證：assert `sum(q) + sum(reserved) == T`
  - 零頭加給用量最高者（並列取 id 字典序大者）
  - 池內 0 人 → 回空 list（pool_idle 由上層處理）
- [ ] T010 [US1] 建立 `tests/integration/test_quota_pool_rebalance.py`：
  - seed Member + 3 allocation + CallRecord（上月用量比 5:3:2）
  - 呼叫 `apply_rebalance(db, trigger='admin:test')` → 3 人 quota 為 450/310/240
  - RebalanceLog 寫入一筆，含 details

### Algorithm

- [ ] T011 [US1] `src/ai_api/services/quota_pool.py`：實作 `compute_rebalance(T, floor, reserved_quotas, pool)` 純函式（依 research.md §1+§2）：
  - cold start 處理
  - 線性比例 + floor
  - 零頭加給最高用量者（並列 id 大者）
  - 內部 assert 守恆

### Apply layer

- [ ] T012 [US1] `src/ai_api/services/quota_pool.py`：實作 `apply_rebalance(db, *, trigger)` async：
  - 在 `db.begin()` transaction 內
  - 用 `previous_month_range_utc(now)` 算上月窗
  - SQL aggregation 取 pool 上月用量（依 data-model.md Q1）
  - SQL aggregation 取 reserved（依 Q2；NULL quota 視為 0 並記 warning）
  - 呼叫 `compute_rebalance(...)`
  - UPDATE 每個池內 allocation 的 `quota_tokens_per_month`（WHERE 條件加 `quota_locked=false AND is_service_allocation=false` 防 race）
  - 最終守恆 assertion（雙保險）
  - INSERT RebalanceLog（含 details JSON）
  - 寫 audit `quota_pool_rebalanced`
- [ ] T013 [US1] 加 `previous_month_range_utc(now)` helper（`src/ai_api/services/quota_pool.py` 或共用 utils）

**Checkpoint**：T009-T010 測試全綠。

---

## Phase 4: US2 — Rollback (P1)

**Goal**：任何失敗整批 rollback、不留痕、audit 一筆。

### Tests First

- [ ] T014 [US2] 建立 `tests/integration/test_quota_pool_rollback.py`：
  - mock `compute_rebalance` 故意回傳「總和 ≠ T」結果 → 守恆 assert 失敗
  - 驗證：所有 allocation 的 quota 維持失敗前的值
  - 驗證：`rebalance_log` 表 0 筆新紀錄
  - 驗證：`auth_audit_log` 有一筆 `rebalance_failed` 含原因

### Impl

- [ ] T015 [US2] `apply_rebalance`：包 try/except — 任何例外 → 寫 audit `rebalance_failed`（在新 transaction，避免被 rollback）→ re-raise
- [ ] T016 [US2] 守恆 assertion 失敗的錯誤型別獨立（`RebalanceConservationError`）方便上層分辨

**Checkpoint**：T014 通過。

---

## Phase 5: US3 — 服務型 / Locked 豁免 (P1)

**Goal**：rebalance 不動 `is_service_allocation` 或 `quota_locked` 的 allocation。

### Tests First

- [ ] T017 [US3] 在 `tests/integration/test_quota_pool_rebalance.py` 加 case：
  - 設 alice `is_service_allocation=true quota=500`、bob `quota_locked=true quota=200`、carol（池內）
  - T=1000 → rebalance 後 alice/bob 不變、carol=300
- [ ] T018 [US3] 在同檔加 case：reserved 占用 > T → 拋 `RebalanceConservationError` 並寫 audit `pool_exhausted_by_reserved`

### Impl

- [ ] T019 [US3] `apply_rebalance`：在 UPDATE SQL 加 `WHERE quota_locked=false AND is_service_allocation=false` 與 `status='active' AND status!='quarantined'`（防 race）
- [ ] T020 [US3] reserved > T 時 raise 專屬例外並寫 audit `pool_exhausted_by_reserved`

---

## Phase 6: US4 — 新加入者拿 floor (P2)

**Goal**：月中新建 allocation 在月初 rebalance 拿 floor，不參與比例。

### Tests First

- [ ] T021 [US4] 在 `tests/integration/test_quota_pool_rebalance.py` 加 case：
  - alice 上月用量 100、bob 月中（10 天前）建立無歷史 → rebalance：alice 拿 `floor + (T - 2·floor) × 1.0`、bob 拿 `floor`

### Impl

說明：T013 helper 已用嚴格自然月窗，bob 上月用量自然為 0；既有
`compute_rebalance` 在「usage=0 但 Σusage>0」時應只給 floor（不分到 distributable）。

- [ ] T022 [US4] 驗證並調整 `compute_rebalance`：當 `usage_i=0` 但 `Σusage>0` 時，該成員只拿 `floor`；distributable 全部按比例分給有用量者（不包含 0 用量者）

---

## Phase 7: US5 — 手動觸發 API (P2)

**Goal**：`POST /admin/quota-pool/rebalance` 立即跑。

### Tests First

- [ ] T023 [US5] 建立 `tests/contract/test_quota_pool_manual_trigger.py`：
  - 200 路徑：呼叫後回 RebalanceLogSummary，新 quota 已套用
  - 409 路徑：T=0 → `pool_disabled`；reserved>T → `pool_exhausted_by_reserved`
  - 401 路徑：無 admin token

### Impl

- [ ] T024 [US5] 建立 `src/ai_api/api/quota_pool.py`：實作 4 個端點
  - `POST /admin/quota-pool/rebalance` → 呼叫 `apply_rebalance(trigger=f'admin:{token_id}')`
  - 例外映射到 409 結構化錯誤
- [ ] T025 [US5] `src/ai_api/main.py`：註冊 `quota_pool.router`，prefix=`/admin`

---

## Phase 8: US6 — Status + Log 查詢 (P2)

**Goal**：`GET /admin/quota-pool/status` + `GET /rebalance-log` + `GET /rebalance-log/{id}`。

### Tests First

- [ ] T026 [US6] 建立 `tests/contract/test_quota_pool_status.py`：
  - 空池：T=0 disabled、member_count=0
  - 有 reserved + 池內：欄位數值正確
- [ ] T027 [US6] 建立 `tests/contract/test_quota_pool_log.py`：
  - list 端點：limit / 排序 / 不含 details
  - detail 端點：含 details；404 不存在 id

### Impl

- [ ] T028 [US6] `src/ai_api/api/quota_pool.py`：
  - `GET /admin/quota-pool/status` — 計算 reserved/distributable/member_count；`last_rebalance_at` 由 RebalanceLog 最新一筆取得
  - `GET /admin/quota-pool/rebalance-log?limit=N`
  - `GET /admin/quota-pool/rebalance-log/{id}` — 含 details；不存在回 404
- [ ] T029 [US6] schemas（Pydantic）：`PoolStatus`、`RebalanceLogSummary`、`RebalanceLogDetail`（依 openapi.yaml）

---

## Phase 9: Proxy 整合（無新 US，但 SC-006 要求）

**Goal**：rebalance 改動的 quota 立即被 proxy 拿到。

- [ ] T030 確認：`src/ai_api/proxy/router.py` 既有 quota 檢查（Phase 3a T024）每次都重 SELECT allocation；不快取。寫測試 `tests/integration/test_quota_pool_proxy_immediacy.py` 驗 SC-006：rebalance 後立即一次 proxy 呼叫使用新 quota

---

## Phase 10: CronJob + CLI (FR-012/014)

### Tests First

- [ ] T031 建立 `tests/integration/test_quota_pool_cron_dedup.py`：
  - 跑 `apply_rebalance(trigger='cron')` 兩次同月 → 第二次無新 RebalanceLog；UNIQUE constraint 自動處理 + 接住 IntegrityError 回 no-op
  - 跑 `apply_rebalance(trigger='cron')` 再跑 `apply_rebalance(trigger='admin:x')` → 兩筆都寫入

### Impl

- [ ] T032 `src/ai_api/services/quota_pool.py`：cron 重跑去重邏輯（接 `IntegrityError` 回 `RebalanceLog` already-done 物件或 None）
- [ ] T033 建立 `src/ai_api/cli/run_rebalance.py`：CLI entry point，呼叫 `apply_rebalance(trigger='cron')`
- [ ] T034 建立 `deploy/helm/ai-api/templates/cronjob-rebalance.yaml`：類似 anomaly_detector，排程 `0 0 1 * *`（每月 1 日 UTC 00:00）；`values.yaml` 加 `rebalanceCron: {enabled: true, schedule: "0 0 1 * *"}`

---

## Phase 11: Polish

- [ ] T035 [P] 跑 `uv run pytest -q` 確認既有 140 tests + 新增測試全綠
- [ ] T036 [P] 跑 `uv run ruff check .` + `uv run mypy src/ai_api` 全綠
- [ ] T037 [P] 更新 `knowledge/vision.md`：階段 3c checkbox 由 `[ ]` → `[x]`
- [ ] T038 PR 描述附 quickstart §4 + §5 + §7 的執行紀錄

---

## Dependencies

```
Phase 1 (Setup: config + .env)
   │
   ▼
Phase 2 (Foundational: models + migration + service skeleton)
   │
   ├─→ Phase 3 (US1 — algorithm + apply + conservation)
   │      │
   │      ├─→ Phase 4 (US2 — rollback)
   │      ├─→ Phase 5 (US3 — service/locked exemption)
   │      └─→ Phase 6 (US4 — new member floor)
   │
   ├─→ Phase 7 (US5 — manual trigger API, depends on Phase 3 apply)
   ├─→ Phase 8 (US6 — status + log queries, depends on Phase 3 model + apply)
   │
   └─→ Phase 9 (proxy integration, depends on Phase 3+5)
        │
        ▼
   Phase 10 (CronJob + CLI)
        │
        ▼
   Phase 11 (polish)
```

**Story dependencies**：
- **US1** 是基礎；其他 US 都需要 `apply_rebalance` 至少可跑
- US2/US3/US4 各自獨立，可並行
- US5/US6 依賴 US1+US2（rollback 行為要對才能回 409）
- Phase 9 整合驗證需所有 US 完成

---

## Parallel Execution Opportunities

- **Phase 1**：T001 / T002 並行
- **Phase 2**：T003 / T004 / T005 不同檔可並行；T006 / T007 / T008 依賴前面
- **Phase 4-6 (US2/US3/US4)**：在 US1 完成後可並行開發（皆改 `services/quota_pool.py`，要 sequential commit 避免衝突）
- **Phase 7-8 (US5/US6)**：API endpoint 並行（同檔 `api/quota_pool.py`，sequential edits）
- **Phase 11**：T035 / T036 / T037 並行

---

## Implementation Strategy

### MVP

**Phase 1+2+3** 完成 = MVP（US1：守恆 + 演算法可跑）。
**Phase 4+5** 完成 = 真正可上線（rollback + 豁免）。

### TDD Discipline

每個 user story 內：unit/integration test commit → impl commit。SC-008 延續
git 歷史「test < impl」順序。

### Risk Hot Spots

1. **零頭分配的並列 id 取法不確定** → 測試覆蓋並列情境（兩個 allocation 相同 max usage，id 不同）
2. **SQLite partial UNIQUE 不支援** → migration 用 dialect-aware 寫法
3. **服務型 / locked 的 quota=NULL（unlimited）混入 reserved 計算** → 視為 0 並寫 audit warning
4. **rebalance 與 admin PATCH quota 撞 race** → 用 `WHERE quota_locked=false ...` 過濾；守恆 assert 兜底
5. **proxy 在 rebalance 中途呼叫** → 既有 Phase 3a quota check 每次重查 allocation，不快取，故 rebalance commit 後立即生效（T030 驗證）

---

## Format Validation

✅ 全部 38 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / 整合 / Polish 無 [US] 標籤
✅ Phase 3-8 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
