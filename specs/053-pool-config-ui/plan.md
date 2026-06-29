# Implementation Plan: 配額池設定移到前端（admin 可編輯 T／保底 + 建議值）

**Branch**: `053-pool-config-ui` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/053-pool-config-ui/spec.md`

## Summary

把配額池的 T／保底從 `settings`（Helm/env）搬到 **DB 單例 `pool_config`**（比照 `notification_config` 的 `CHECK id=1` 單例前例），由 admin 在「配額池監控」頁編輯。新增**讀取唯一入口** `get_pool_config(db)`：DB 有列就用，無列則**首讀 lazy-seed** 自現行 `settings.pool_*`（首次零行為變更）。把現有**兩個讀取點**（`api/quota_pool.py::get_pool_status`、`services/quota_pool.py::apply_rebalance`）改成讀這個入口——成為單一真理。新增 `PUT /quota-pool/config`（驗證 + 稽核）與建議值（讀 `aggregate_usage` 近月用量算 T／保底建議）。前端 `quota-pool.tsx` 加編輯表單 + 建議區。migration **0021**（純加單例表）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2（後端）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration 0021**——單例表 `pool_config`（`CHECK id=1`，欄：`total_tokens_per_month`、`floor_per_allocation`、`updated_at`、`updated_by`）。純加表。
**Testing**: pytest（contract + integration + unit；含「apply_rebalance 讀 DB」「PUT 驗證」「lazy-seed 自 env」整合測試，testcontainers Postgres）；Vitest（前端表單 + 建議區）
**Target Platform**: Linux distroless（K8s）；前端 nginx SPA
**Project Type**: web（backend + frontend）
**Constraints**: 單一真理（DB；env 僅 bootstrap）、首讀 seed 零行為變更、`T ≥ 保底×N` 硬擋、`T < 近月用量` 警告不擋、T=0 仍停用
**Scale/Scope**: 1 單例表 + 1 service 讀取入口 + 2 讀取點改寫 + 2 端點（PUT config、建議）+ 1 前端頁擴充

## Constitution Check

- **I. Test-First**：✅ 先寫 contract/integration 測試（GET 含 config+suggestion、PUT 驗證 T≥floor×N／負數、apply_rebalance 改讀 DB、lazy-seed 自 env）紅 → 再實作。
- **II. 契約優先**：✅ Phase 1 出 `contracts/quota-pool-config.md`（GET status 擴充 + PUT config + 建議欄位 + 錯誤格式）；屬**既有 admin API 擴充**（GET status 加欄、新增 PUT），非破壞。
- **III. 整合測試覆蓋外部依賴**：✅ DB 為邊界——以 testcontainers Postgres 驗 migration 0021 + 單例 get-or-create + apply_rebalance 讀 DB。
- **IV. 可觀測性**：✅ PUT 寫稽核（新 `AuditEventType.pool_config_updated`，VARCHAR enum、無 migration）。
- **V. 簡潔優先（YAGNI）**：✅ 單例表（非多列設定系統）；建議為唯讀計算欄、非新模型；env 退 bootstrap、不保留第二可編輯路徑。

**結論**：無違反、無 Complexity Tracking、Technical Context 無 NEEDS CLARIFICATION。

## Phase 0：研究（research.md）

- **R1 單例表**：`pool_config`（`CHECK id=1`）比照 `notification_config`。欄 `total_tokens_per_month`/`floor_per_allocation`（int）+ `updated_at`/`updated_by`。
- **R2 單一真理讀取入口**：新增 `get_pool_config(db)`（get-or-create）；`apply_rebalance` 與 `get_pool_status` 改呼叫它、**不再直接讀 `settings.pool_*`**（追全所有 sink，呼應「加欄要追所有讀寫點」）。
- **R3 首讀 lazy-seed**：DB 無列時用 `settings.pool_total_tokens_per_month`/`pool_floor_per_allocation` 建初始列 → 首次零行為變更；env 自此僅當 bootstrap，DB 為 live 真理（原則 5）。
- **R4 建議值**：讀 `services/usage.py::aggregate_usage`（近月 total_tokens）+ 池內成員數 N；建議 T = `round(近月×2)`、建議保底 = 讓零用量成員有可用底的量級（informed default，UI 文字說明），附約束 T≥保底×N。唯讀，folded into GET status 或獨立 GET。
- **R5 驗證與生效**：PUT 擋 `T<保底×N`（422/409）+ 負數；`T<近月用量`回 soft warning 欄位（不擋）；生效於下次 rebalance（不即時改寫既有配額）——UI 標明。
- **R6 稽核**：新增 `AuditEventType.pool_config_updated`（非 native enum、無 migration）。

## Phase 1：設計與契約

- **data-model.md**：`pool_config` 單例（欄、CHECK id=1、驗證規則 T≥floor×N、T≥0、floor≥0）；標注 migration 0021 純加表 + lazy-seed 來源。建議為唯讀 DTO。
- **contracts/quota-pool-config.md**：`GET /admin/quota-pool/status`（擴充：回目前 config + 建議 + N + soft-warning）、`PUT /admin/quota-pool/config`（body {T, floor}；驗證/錯誤；稽核）；維持既有 `POST /quota-pool/rebalance`、`GET rebalance-log` 不變。
- **quickstart.md**：admin 設值 → 手動再分配 → 配額更新；建議套用；驗證擋 T<floor×N。
- **agent context**：`update-agent-context.sh claude`（無新技術，預期僅記階段資訊）。

## Project Structure

```text
src/ai_api/
├── models/
│   └── pool_config.py        # 【新】PoolConfig 單例（CHECK id=1）；models/__init__.py 匯出
├── services/
│   └── quota_pool.py         # 【改】get_pool_config(db) get-or-create + lazy-seed；apply_rebalance 改讀它
│                             #      + suggest_pool_config(db)（用 aggregate_usage + N）
├── api/
│   └── quota_pool.py         # 【改】get_pool_status 改讀 DB + 回建議/N/warning；新增 PUT /quota-pool/config（驗證+稽核）
├── (audit enum)              # 【改】AuditEventType.pool_config_updated（VARCHAR、無 migration）
└── config.py                 # 不刪 pool_*（退為 bootstrap 預設來源）

alembic/versions/
└── 0021_pool_config.py       # 【新】單例表 pool_config（純加表）

frontend/src/
├── routes/admin/quota-pool.tsx   # 【改】編輯表單（T/保底 + 驗證 + 「下次再分配生效」）+ 建議區（一鍵套用）
└── __tests__/                    # 【新/改】pool-config 表單 + 建議 + 驗證測試

tests/
├── contract/test_quota_pool_config.py   # 【新】GET 擴充 / PUT 驗證 / 稽核
└── integration/                         # 【新/改】migration 0021 + lazy-seed + apply_rebalance 讀 DB（Postgres）
```

**Structure Decision**: 沿用既有 web 結構。後端核心＝單例表 + 單一讀取入口（兩個既有 sink 改指向它）；前端擴充既有 `quota-pool.tsx`。後端改動 → 重建 backend image；前端 → frontend image；**有 migration → 部署帶 `migrationJob.enabled=true`**。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
