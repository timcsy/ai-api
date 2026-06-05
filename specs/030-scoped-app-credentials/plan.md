# Implementation Plan: Scoped application credentials（憑證綁一組分配，M:N）

**Branch**: `030-scoped-app-credentials` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-scoped-app-credentials/spec.md`

## Summary

把 `Credential` 從「綁單一分配（1:N）」重構為「**成員擁有、可命名的應用 key，scope = 一組分配（M:N）**」。技術核心兩件：(1) schema：`credentials` 去 `allocation_id`、加 `member_id`，新增關聯表 `credential_allocations`（含 denormalized `resource_model`，`unique(credential_id, resource_model)` 保證歸戶無歧義）；(2) proxy 熱路徑：token → credential → **依 request 的 model 在 scope 內挑中分配**（`preflight.py` 既有流程中 `requested_model` 早已備妥），挑不到即 `model_mismatch`。額度/歸戶仍 per-allocation。既有單分配 token 等同「scope 含一筆分配的 key」→ 零回歸。前端把憑證清單**升成員層**、device-flow 改多選、移除舊 Codex 分頁。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、TanStack Query、shadcn/ui（**皆既有，不新增套件**）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**schema 重構 + migration `0017`**（改 `credentials` + 新 `credential_allocations`）
**Testing**: pytest（contract + integration，含 Postgres 跑 migration）、vitest（前端）
**Target Platform**: Linux/K8s（後端）；既有前端
**Project Type**: web（既有 backend `src/ai_api/` + frontend `frontend/`）
**Performance Goals**: proxy 熱路徑解析 ≤ 既有（token→credential→挑分配為 1~2 個 indexed 查詢）
**Constraints**: 額度/歸戶仍 per-allocation（不移到 token）；token 仍 show-once + hash-only；**既有 token 零回歸**；`credentials` 被 `device_authorizations.credential_id`（階段 19）FK 參照 → migration **必須 in-place ALTER（不可 drop+rename 整表）**
**Scale/Scope**: 後端改 1 表 + 1 新表 + service/proxy 解析 + 端點；前端清單升層 + 多選 + 移除舊分頁

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（不可妥協）**：✅ proxy 解析、scope CRUD、migration 先寫失敗測試再實作。**最高優先固化**：① **既有單分配 token 零回歸**（migration 後解析/歸戶不變）② 多 model key 各自歸戶 + scope 外 `model_mismatch` ③ 擁有者邊界（成員不得綁他人分配）。
- **II. 契約優先**：✅ `contracts/credentials.openapi.yaml`（member `/me/credentials` + scope 編輯；admin 治理；device-flow approve 改 `allocation_ids`）；契約測試為合併關卡。
- **III. 整合測試覆蓋外部依賴**：✅ migration `0017`（含 device_authorizations FK 並存）**在 Postgres 整合測試驗**；多 model 歸戶/額度走整合測試。
- **IV. 可觀測性**：✅ scope 增刪 + 撤回留稽核（`credential_scope_added`/`credential_scope_removed`/`credential_revoked`，VARCHAR enum 免 migration）。
- **V. 簡潔優先（YAGNI）**：✅ 採業界標準 scoped-key 模型；denormalize `resource_model` 進關聯表換取 DB 級唯一性與單查詢解析（避免 trigger / 應用層競態）；不引入額度於 token 層。

**結論：無違規。**唯一需謹慎處：proxy 熱路徑改動 + migration in-place（見 research.md 風險）。

## Project Structure

### Documentation (this feature)

```text
specs/030-scoped-app-credentials/
├── plan.md  ├── research.md  ├── data-model.md  ├── quickstart.md
├── contracts/credentials.openapi.yaml
└── tasks.md（/speckit.tasks 產出）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── credential.py               # 改：去 allocation_id、加 member_id；scope 經關聯表
│   ├── credential_allocation.py    # 新：CredentialAllocation 關聯（credential_id, allocation_id, resource_model）
│   └── allocation.py               # 改：credentials 關係改 secondary（scope 反向）
├── services/
│   ├── allocations.py              # 改：lookup_credential_by_token + resolve_scope_allocation；add_credential(name, allocation_ids)；scope 增刪；list 升成員層
│   └── device_flow.py              # 改：approve 接受多筆 allocation_id
├── proxy/
│   ├── preflight.py                # 改：token→credential→依 requested_model 挑分配（None→model_mismatch）
│   ├── auth.py / guard.py          # 改：resolve_allocation 走 model-aware；guard 退為防禦性
├── api/
│   ├── me.py                       # 改/加：/me/credentials（GET/POST/DELETE/rotate）+ scope PATCH；保留舊 /me/allocations/{id}/credentials（back-compat）
│   ├── credentials.py              # 新（或併 allocations.py）：admin /admin/.../credentials 治理
│   └── device.py / install.py      # device-flow 多選；install 腳本寫對應 model（接 model 資訊）
alembic/versions/0017_scoped_credentials.py   # 新：in-place 改 credentials + 新 join + backfill

frontend/src/
├── components/
│   ├── app-credentials-card.tsx    # 新（由 device-credentials-card 演進）：成員層「我的應用/金鑰」清單 + 建立(命名+多選分配)+撤回/rotate+編輯 scope
│   └── api-usage-example.tsx       # 改：移除舊 Codex 分頁（收尾 A）
├── routes/
│   ├── dashboard.tsx               # 改：掛成員層應用清單
│   ├── allocation-detail.tsx       # 改：原 per-allocation 憑證卡 → 顯示「哪些 app key 含此分配」(唯讀) + 「用此分配建 app key」入口
│   └── device-authorize.tsx        # 改：分配下拉 → 多選
tests/
├── contract/  test_scoped_credentials.py / test_proxy_multimodel.py / test_credential_owner_isolation.py / test_device_multi_alloc.py
└── integration/ test_credential_migration_0017.py（Postgres：1:N→M:N 零回歸）
```

**Structure Decision**: 沿用既有 web 結構。`Credential` 由「屬於分配」改為「屬於成員、scope 經 `CredentialAllocation` 關聯」；proxy 解析改 model-aware（在 `preflight.py` 既有 `requested_model` 之後挑分配）。member 端點升成員層（`/me/credentials`），舊 per-allocation 端點保留為相容層（回「scope 含此分配的 key」）。

## Complexity Tracking

> 無憲章違規，免填。最大技術風險（migration in-place + 熱路徑）記於 research.md，以 Postgres 整合測試 + 零回歸契約緩解。
