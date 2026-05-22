# Implementation Plan: 階段 3c — Adaptive Quota Pool

**Branch**: `006-quota-pool` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-quota-pool/spec.md`

## Summary

延續既有 Python 3.11 + FastAPI + SQLAlchemy + Postgres，無新外部依賴：

- **資料模型**：新表 `RebalanceLog`；Allocation 加 `quota_locked`；
  AuthAuditLog enum 加 4 個新事件
- **演算法**：`services/quota_pool.py` 純函式 `compute_rebalance(...)`
  （給定 T、floor、reserved、池內 list[(id, usage)] → 回傳 list[(id, new_quota)]）
  + 守恆 assertion；副作用 service `apply_rebalance(...)` 包在 transaction
- **CLI**：`cli/run_rebalance.py`（CronJob 入口），呼叫 `apply_rebalance(trigger='cron')`
- **API**：`POST /admin/quota-pool/rebalance` / `GET /admin/quota-pool/status`
  / `GET /admin/quota-pool/rebalance-log` / `GET .../{id}`
- **Helm**：新 CronJob template `cronjob-rebalance.yaml`（每月 1 日 UTC 00:00）

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**：無新增（SQLAlchemy 2 async、FastAPI、stdlib `decimal`、`datetime`）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）
  - 新表 `rebalance_log`
  - `allocations` 加 `quota_locked` 欄位
**Testing**: pytest 既有；新增 unit + contract + integration
**Target Platform**: 同既有（K8s + CronJob）
**Project Type**: web-service（不變）
**Performance Goals**：
  - rebalance ≤ 5 秒對 1000 active allocation（單一 transaction，不擋代理呼叫）
  - API 端點 `<200ms` p95
**Constraints**：
  - 守恆 `Σq == T` 不可妥協（SC-001）
  - 失敗整批 rollback（SC-003）
  - cron 同月不重複跑（FR-012）
**Scale/Scope**：≤ 1000 active allocations、≤ 12 RebalanceLog/年（每月 1 筆 cron + 偶有手動）

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | spec SC-008；演算法純函式 unit test 先寫；整合測試含 rollback 場景 | ✅ |
| II. Contract-First | OpenAPI 新增 4 個端點；先於實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | rebalance 在真實 Postgres（testcontainers）上跑：守恆驗證、rollback 模擬、cron UNIQUE 衝突 | ✅ |
| IV. 可觀測性 | RebalanceLog 即 audit；失敗寫 AuthAuditLog；演算法版本欄位讓未來改算法可追溯 | ✅ |
| V. YAGNI | 無 EWMA、無多池、無跨月借貸、無 UI；spec NON-GOAL 已列 | ✅ |

**符合 experience.md 教訓**：
- 「async lazy-load」：rebalance 查 Allocation 全 SQL Core，無 ORM lazy load
- 「datetime tz-aware」：自然月起訖一律 tz-aware UTC
- 「SQLAlchemy 多分支 select 型別衝突」：本階段查詢結構單一，不會踩
- 「拒絕路徑先 bind context」：rebalance 失敗時 audit 含 trigger 與失敗原因

**初次評估通過**，無 Complexity Tracking。

## Project Structure

### Documentation

```text
specs/006-quota-pool/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md            # /speckit.tasks 產出
```

### Source Code

```text
src/ai_api/
├── api/
│   └── quota_pool.py             # 新：4 個 admin 端點
├── services/
│   └── quota_pool.py             # 新：compute_rebalance + apply_rebalance
├── models/
│   ├── allocation.py             # 既有；加 quota_locked
│   ├── rebalance_log.py          # 新
│   └── auth_audit.py             # 既有；event_type enum 加 4 個新值
├── cli/
│   └── run_rebalance.py          # 新：CronJob 入口
├── config.py                     # 既有；加 pool_total_tokens_per_month + pool_floor_per_allocation
└── main.py                       # 既有；註冊新 router

alembic/versions/
└── 0005_quota_pool.py            # 新

deploy/helm/ai-api/
├── values.yaml                   # 加 rebalanceCron 設定
└── templates/
    └── cronjob-rebalance.yaml    # 新

tests/
├── contract/
│   ├── test_quota_pool_status.py
│   ├── test_quota_pool_log.py
│   └── test_quota_pool_manual_trigger.py
├── integration/
│   ├── test_quota_pool_rebalance.py        # 主流程 + 守恆
│   ├── test_quota_pool_rollback.py         # rollback 場景
│   └── test_quota_pool_cron_dedup.py       # cron UNIQUE
└── unit/
    └── test_compute_rebalance.py           # 演算法純函式
```

**Structure Decision**: 沿用 Phase 1+2+3a 的 single-project layout。
`services/quota_pool.py` 分純函式 `compute_rebalance` 與有副作用的
`apply_rebalance`，前者 100% unit-testable（演算法正確性），後者
整合測試（DB transaction、rollback）。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | unit + contract + integration 三層測試先於實作 → ✅ |
| Contract-First | `contracts/openapi.yaml` 4 端點完整定義 → ✅ |
| 整合測試覆蓋外部依賴 | rollback 場景需 Postgres real transaction；cron UNIQUE 也需 DB → ✅ |
| 可觀測性 | RebalanceLog 與 AuthAuditLog 雙寫 → ✅ |
| YAGNI | 無新 service、無新 deps、Helm 只多一個 CronJob template → ✅ |

通過，可進入 `/speckit.tasks`。
