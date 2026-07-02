# Implementation Plan: 異常偵測 v2

**Branch**: `054-anomaly-controls` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)

## Technical Context

- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
- FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2（後端）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
- PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration 0022**——單例表 `anomaly_config`（`CHECK id=1`）
- 對應願景「異常偵測 v2」；服務原則 6（admin 自助）、5（單一真理）、2（可追蹤）

## 前例與架構決策

- **單例設定 + lazy-seed**：完全比照階段 39 `pool_config`（`services/quota_pool.py::get_pool_config`）。新增 `get_anomaly_config(db)`：get-or-create、首讀從 `settings.anomaly_*` seed → 首次零行為變更；DB 成為門檻/開關的**單一真理**，env 退為 bootstrap。
- **偵測讀取點單一化**：`services/anomaly.py` 的 `detect_and_quarantine` + `evaluate_allocation` 改讀 `anomaly_config`，不再直接讀 `get_settings().anomaly_*`（追全所有讀取點，呼應「單一真理不 drift」教訓）。
- **停用/暫停語意**：`detect_and_quarantine` 開頭判斷「是否執法」——`auto_quarantine_enabled == False` 或 `pause_until` 在未來 → 照掃描、照寫 `anomaly_detector_run` 稽核（含 `enforced=false`），但**跳過 `alloc.status=quarantined`**。`pause_until` 過期＝視為啟用（不需背景清理，讀時判斷）。
- **稀疏 baseline 聰明放寬**：`evaluate_allocation` 在 `baseline_total < cfg.baseline_min_calls` 時走絕對門檻分支（等同現行 cold-start 邏輯），不套比例規則。
- **解除可達性**：解除端點/選單已存在；US3 只在首頁隔離提示加「解除」直達（呼叫既有 `unquarantineMut`）。

## Project Structure（本功能新增/改動）

```
backend/
  src/ai_api/models/anomaly_config.py        # NEW 單例 model（CHECK id=1）
  src/ai_api/models/__init__.py              # 匯出 AnomalyConfig
  src/ai_api/models/auth_audit.py            # +AuditEventType.anomaly_config_updated
  src/ai_api/services/anomaly.py             # get_anomaly_config + 讀取點改寫 + 稀疏 baseline 分支 + 停用略過
  src/ai_api/api/anomaly.py                  # NEW GET/PUT /admin/anomaly/config
  src/ai_api/api/__init__.py 或 main         # 掛 router
  alembic/versions/0022_anomaly_config.py    # NEW create table
tests/
  tests/contract/test_anomaly_config.py      # NEW GET/PUT/驗證/稽核/lazy-seed（SQLite app_client）
  tests/unit/test_anomaly_evaluate.py        # 稀疏 baseline 分支 + 停用略過（純函式/服務）
frontend/
  src/routes/admin/anomaly.tsx（或整併既有頁）# 設定：開關 + 暫停到期 + 門檻
  src/routes/admin/home.tsx / dashboard       # 隔離提示一鍵解除（US3）
  src/__tests__/anomaly-config.test.tsx       # NEW
```

## Constitution Check

- **TDD**：契約測試（GET/PUT/驗證/稽核/lazy-seed）+ 單元（稀疏 baseline、停用略過）先行。✅
- **單一真理**：門檻/開關唯一可改處在 DB；env 退 bootstrap（原則 5）。✅
- **不新增套件**、**純加表 migration**（零回歸：token/既有偵測路徑不變）。✅
- **可追蹤**：開關/門檻/解除變更皆稽核。✅

## Phase 分解見 tasks.md
