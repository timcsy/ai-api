# Implementation Plan: 成本制配額（跨端點統一額度上限）

**Branch**: `046-cost-quota` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/046-cost-quota/spec.md`

## Summary

為每筆分配新增選填的「每月花費上限（USD）」，與既有「每月 token 上限」並列、任一超過即擋。**以花費（USD）為跨單位共同分母**，讓 token 與所有非 token 端點（OCR/圖片/語音/即時字幕/search/rerank）共用同一道月度上限——補上「非 token 用量繞過配額」的治理缺口（原則 1）。即時字幕長連線在**連線進行中**沿用既有撤回 watcher 週期核對累計花費、超額主動中止（原則 3）。花費上限為**獨立硬上限、不進自適應配額池**（階段 3c 只再分配 token 額度）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2（後端）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0020`**——`allocations` 加一個 nullable 欄 `quota_cost_usd_per_month`（純加欄）。累計來源沿用既有 `call_records.cost_usd`（0019 已有）。
**Testing**: pytest（contract / integration / unit）、vitest（前端）
**Target Platform**: Linux server（K8s）/ 瀏覽器（SPA）
**Project Type**: web（backend + frontend）
**Performance Goals**: 配額前置檢查不顯著增加 proxy 延遲（多一個 `sum(cost_usd)` 聚合查詢，命中既有複合索引 `idx_callrecord_allocation_time (allocation_id, started_at)`）
**Constraints**: 既有 token 配額路徑零回歸；花費以 `Decimal` 計（避免浮點誤差）；realtime 連線中把關容差 = 一個 re-check 週期
**Scale/Scope**: 後端少量（quota 服務 + preflight + realtime watcher + admin/usage 序列化）+ 前端兩處顯示/編輯；單一新 migration、無新套件、無新表

## Constitution Check

> constitution 原則：I Test-First（非協商 TDD）、II 契約優先、III 整合測試覆蓋外部依賴且 CI 可重現、IV 可觀測性、V YAGNI。

| 原則 | 評估 | 結論 |
|---|---|---|
| **I. Test-First** | 先寫失敗測試（contract：cost 超額被擋；integration：混合 token+非 token 累計、realtime 連線中超額；unit：`current_month_cost`、`is_over_cost_quota`）再實作 | ✅ 遵循 |
| **II. 契約優先** | 先定契約再實作：① admin 分配 create/update 多收選填 `quota_cost_usd_per_month`；② proxy 新拒絕碼 `cost_quota_exceeded`（403）；③ `/me/usage`+admin usage 每分配多 `cost_used_this_month`+`quota_cost_usd_per_month`；④ realtime 連線中超額 close（policy violation + reason）。見 `contracts/cost-quota.md` | ✅ 遵循 |
| **III. 整合測試覆蓋外部依賴 + CI 可重現** | cost 配額以真端點 contract 測（sqlite）；realtime 連線中把關沿用階段 32 的 **mock provider WS** in-loop 測（CI 可重現）；自適應池隔離以既有整合測試風格驗。**無新外部依賴** | ✅ 遵循 |
| **IV. 可觀測性** | cost 超額拒絕走既有 `record_call`（新 outcome `rejected_cost_quota_exceeded`）+ 結構化日誌；realtime 連線中中止 log 原因 | ✅ 遵循 |
| **V. YAGNI** | 只加一個 nullable 欄 + 既有 quota 檢查旁加一道；**重用** preflight 管線、realtime watcher、quota 服務、admin 配額 UI、用量顯示路徑；**刻意不**把 cost 納入自適應池（不為「未來可能」加再分配邏輯） | ✅ 遵循 |

**Deviations**: 無。零新套件、零新表、零新抽象；單一 additive migration。

## Project Structure

### Documentation (this feature)

```
specs/046-cost-quota/
├── spec.md              # 已完成
├── plan.md              # 本檔
├── research.md          # Phase 0（本次產出）
├── data-model.md        # Phase 1（本次產出）
├── quickstart.md        # Phase 1（本次產出）
├── contracts/
│   └── cost-quota.md    # Phase 1（本次產出）
└── checklists/
    └── requirements.md  # 已完成（16/16）
```

### Source Code (repository root)

```
src/ai_api/
├── models/allocation.py         # + quota_cost_usd_per_month（nullable Numeric）
├── models/call_record.py        # CallOutcome + rejected_cost_quota_exceeded（VARCHAR enum，無 migration）
├── services/quota.py            # + current_month_cost() + is_over_cost_quota()
├── proxy/preflight.py           # run_preflight 加一道 cost 檢查（與 token 並列）
├── proxy/router.py              # _outcome_for_code 映 cost_quota_exceeded
├── proxy/realtime.py            # 連線中 watcher 擴充：committed_month_cost + 本連線 running cost ≥ cap → close
├── api/allocations.py + schemas.py  # admin create/update 收選填 quota_cost_usd_per_month
├── api/me.py + api/usage.py     # 每分配序列化 cost_used_this_month + cost 上限
alembic/versions/0020_cost_quota.py   # 純加欄
frontend/src/
├── 配額編輯 Dialog（admin）       # + 每月花費上限欄
├── 分配卡 + usage 顯示            # 本月花費 / 上限
tests/
├── unit/test_quota.py           # current_month_cost / is_over_cost_quota
├── contract/test_cost_quota.py  # 混合端點累計超額被擋、token 零回歸
├── integration/test_realtime_relay.py  # + 連線中花費超額 close（mock provider WS）
└── integration/test_quota_pool_*.py    # 自適應池不碰 cost 上限（既有風格）
```

**Structure Decision**: 沿用既有 web（backend `src/ai_api/` + frontend `frontend/src/`）單體結構。本功能是「核心治理層」增量——主要落在 `services/quota.py` + `proxy/preflight.py` + `proxy/realtime.py`，前端只在既有配額編輯與用量顯示處加欄。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
