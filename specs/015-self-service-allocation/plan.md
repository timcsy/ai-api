# Implementation Plan: 自助領取憑證 (Self-Service Allocation)

**Branch**: `015-self-service-allocation` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-self-service-allocation/spec.md`

## Summary

讓成員自助領取 allocation：admin 逐 model 開放（`self_service_enabled` + `self_service_default_quota`），被 access policy 允許的成員透過 `POST /me/allocations` 一鍵領一張 `origin=self_service` 的 allocation（配額=該 model 預設）。領取資格沿用既有 `evaluate_visibility`；領到的 allocation 與手動建立等價（走 quota pool、撤回、計量）。撤回自助 allocation 會在 `self_service_reclaim_locks` 建一筆鎖，成員在 admin 解鎖前不能重領。前端在 member dashboard 加「可領取 model + 領取鈕」，admin 在 model 設定加自助開關與配額、在分配總覽加「解鎖」。

## Technical Context

**Language/Version**：Python 3.11+（後端）+ TypeScript strict / React 19（前端）
**Primary Dependencies**：FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2；複用既有 `AllocationService`、`evaluate_visibility`（model_access）、quota pool；前端既有 stack（shadcn/ui + TanStack Query）
**Storage**：PostgreSQL / SQLite；`model_catalog` +2 欄、`allocations` +`origin` 欄、新表 `self_service_reclaim_locks`
**Testing**：pytest（後端，目前 311 baseline）；Vitest（前端，目前 69 baseline）
**Target Platform**：Linux server（K8s）；dev uvicorn + Vite
**Performance Goals**：自助領取為 member 觸發的 cold path，目標 < 200ms p95（非 proxy hot path）
**Constraints**：資格判定**完全複用** `evaluate_visibility`，不重寫；不破壞既有 allocation / quota pool / 撤回契約
**Scale/Scope**：百人量級成員、< 50 model；後端 +1 表 +3 欄(含 enum) +3 endpoints；前端 +member dashboard 領取區 + admin 2 處

## Constitution Check

*GATE: 通過才進 Phase 0；Phase 1 後重檢。*

### I. Test-First (NON-NEGOTIABLE) ✅
- 資格判定：unit test（self_service off / 不被 access policy 允許 / 已持有 / 鎖定 → 各自拒絕；允許 → 通過）
- 領取：contract test `POST /me/allocations`（201 + 各拒絕碼）先寫
- 撤回鎖定：integration test（撤回自助 → 重領被拒 → admin 解鎖 → 可重領）
- admin 開放/解鎖：contract test 先

### II. API 契約優先 ✅
- 3 個新端點先寫 OpenAPI（`POST /me/allocations`、model self-service 設定、admin 解鎖）；既有端點不破壞

### III. 整合測試覆蓋外部依賴 ✅
- 端對端：admin 開放 → 成員領取 → 用 token 呼叫 `/v1` 成功 → admin 撤回 → 重領被拒
- 既有 311 backend + 69 frontend 零回歸（SC-005）

### IV. 可觀測性 ✅
- 領取 / 撤回鎖定 / 解鎖 / 開放設定變更皆寫 audit（新增 enum 值，details 帶 member + model）
- token 一次性顯示，不入 log（沿用既有 allocation 模式）

### V. 簡潔優先 (YAGNI) ✅
- 資格判定複用 `evaluate_visibility`，不另立邏輯
- 領取複用 `AllocationService.create`（加 `origin` 參數）
- 鎖定用一張極簡 join 表，admin 解鎖 = 刪該 row
- 不做審批流 / email 通知 / 自助調配額（spec 明確排除）

**Pass**：無 deviation。

## Project Structure

### Documentation (this feature)

```text
specs/015-self-service-allocation/
├── plan.md              # 本檔
├── research.md          # Phase 0：資格複用 / origin 放哪 / 鎖定儲存 / 配額來源 / 端點形態
├── data-model.md        # Phase 1：ModelCatalog +2、Allocation +origin、reclaim lock 表、migration 0012
├── quickstart.md        # Phase 1：4 驗收場景
├── contracts/
│   ├── me-allocations.yaml        # POST /me/allocations
│   └── admin-self-service.yaml    # model 開放設定 + 解鎖 + 鎖定列表
├── checklists/requirements.md     # 已完成
└── tasks.md             # /speckit.tasks 產生
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── model_catalog.py        # MODIFY: +self_service_enabled +self_service_default_quota
│   ├── allocation.py           # MODIFY: +origin (AllocationOrigin enum: admin/self_service)
│   └── self_service_lock.py    # NEW: SelfServiceReclaimLock(member_id, model_slug, ...)
├── services/
│   ├── allocations.py          # MODIFY: create() 接受 origin；revoke() 對 self_service 建鎖
│   └── self_service.py         # NEW: claim(member, model) 資格判定+建 allocation；unlock()；list_claimable()
├── api/
│   ├── me.py                   # MODIFY: +POST /me/allocations（current_member + require_csrf）
│   └── admin_self_service.py   # NEW: model 開放設定 + 解鎖 + 鎖定列表
alembic/versions/
└── 0012_self_service.py        # NEW: catalog 2 欄 + allocations.origin + lock 表 + 3 audit enum 值

frontend/src/
├── routes/
│   ├── dashboard.tsx           # MODIFY: 加「可自助領取 model」區 + 領取鈕 + token 一次性顯示
│   └── admin/
│       ├── model-detail.tsx (或 model-access) # MODIFY: 自助開關 + 預設配額
│       └── allocations.tsx     # MODIFY: 鎖定列表 + 解鎖（跨成員總覽既有頁）
tests/
├── unit/test_self_service_eligibility.py   # NEW
├── contract/test_me_allocations.py         # NEW
├── contract/test_admin_self_service.py     # NEW
└── integration/test_self_service_flow.py   # NEW（領取→呼叫→撤回→鎖定→解鎖）
```

**Structure Decision**：沿用既有 web app 結構。資格判定集中在新 `self_service.py` service（複用 `evaluate_visibility`），不散落在 endpoint。撤回鎖定的 hook 掛在 `AllocationService.revoke`（唯一撤回路徑，admin 端點與成員詳情都走它）。前端領取入口放 member dashboard（成員自己的頁），admin 設定放既有 model 設定處、解鎖放既有「觀測 → 分配」總覽。

## Complexity Tracking

無偏離 constitution，本節留空。
