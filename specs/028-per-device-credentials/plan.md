# Implementation Plan: 憑證模型重構（每分配多 per-device 憑證）

**Branch**: `028-per-device-credentials` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-per-device-credentials/spec.md`

## Summary

把 `Credential` 從「`allocation_id` 當主鍵（強制 1:1）」改為**一分配多筆**：新增獨立 `id` 主鍵、`name`（裝置名）、
`last_used_at`、`revoked_at`（軟撤回）。token 驗證（`lookup_by_token`）邏輯不變（fingerprint 唯一 → 找到那把 →
回 allocation），既有 token **零回歸**。新增 member 自助 + admin 的「裝置/憑證」add/list/revoke。**migration 0015**
把每筆既有憑證原樣保留為一把預設具名憑證。額度/歸戶仍綁分配層。

## Technical Context

**Language/Version**: Python 3.11+（後端為主）/ TypeScript strict + React 19（前端裝置清單）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2（皆既有）；前端既有 stack——**不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0015`**（`credentials` 表改主鍵 + 加欄；保留既有資料）
**Testing**: pytest contract（add/list/revoke + owner-isolation + 既有 token 零回歸）；**integration（Postgres）**：
migration 後既有 token 仍解析、多憑證並存、撤一把不連坐；前端 vitest（裝置清單 + 遮罩複製面板）
**Target Platform**: 既有 web（後端 + 前端）
**Performance Goals**: 不退步；`last_used_at` 更新採**節流**（僅當距上次 > N 分鐘才寫）避免每次呼叫寫 DB
**Constraints**: **既有 token 零回歸**（auth-critical 路徑）；額度/歸戶/分配語意不變；hash-only 維持；不新增依賴
**Scale/Scope**: 1 個 model 改 + 1 個 migration + service add/revoke/list + 約 4 member/admin 端點 + 裝置清單 UI；無 device-flow（階段 19）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（不可妥協）**：schema/service/endpoint 皆可測 → 先寫失敗測試（Red）：
  (a) 一分配多憑證皆可呼叫且歸同一分配；(b) **撤一把、其他仍可用**；(c) **owner-isolation**（成員不得操作他人憑證）；
  (d) **既有 token 零回歸**（migration 後舊 token 仍解析）。✅ 通過
- **II. 契約優先**：member/admin 的 credential add/list/revoke 端點先以 OpenAPI 定義再實作；既有 proxy/auth 契約不變。✅ 通過
- **III. 整合測試覆蓋外部依賴**：**改主鍵的 migration** 必須在 **Postgres** 整合測試驗（SQLite 改 PK 需 Alembic batch
  模式；「本機 SQLite 過 ≠ Postgres 過」既有教訓）：seed 舊式資料 → 跑 migration → 舊 token 仍解析、多憑證 lookup 正確。✅ 通過
- **IV. 可觀測性**：撤回憑證 MUST 留**稽核紀錄**（沿用既有 audit event）；token 仍只存雜湊，不洩明文。✅ 通過
- **V. 簡潔優先（YAGNI）**：複用既有 token 產生/雜湊/驗證/領取/稽核；軟撤回只加一欄；**不做**數量上限、不做 device-flow
  （階段 19）、不做可還原。✅ 通過

**結論**：無憲章違反。對應已更新的**原則 1**（唯一性在分配層、一分配多獨立憑證、撤一把不影響其他）+ **原則 2** 可追蹤性。

## Project Structure

### Documentation (this feature)

```text
specs/028-per-device-credentials/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/credentials.openapi.yaml
└── checklists/requirements.md（16/16）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/credential.py            # 主鍵改 id；加 name / last_used_at / revoked_at；allocation_id 改一般 FK
├── models/allocation.py            # credential（scalar）→ credentials（list）
├── services/allocations.py         # lookup_by_token 加 revoked_at IS NULL；add_credential/revoke_credential/list；
│                                   #   rotate_token 改 per-credential 語意；建立分配時建第一把具名憑證
├── api/me.py                       # 新增 /me/allocations/{id}/credentials（GET/POST/DELETE，owner-scoped）；rotate-token 相容
├── api/allocations.py              # admin：GET/DELETE /admin/allocations/{id}/credentials/{cid}
├── api/schemas.py                  # CredentialOut（含 name/last_used_at/status）+ 請求 schema
alembic/versions/
└── 0015_per_device_credentials.py  # 改主鍵 + 加欄（batch 模式）；既有列 → 一把名為「預設」的憑證
frontend/src/
├── routes/admin/allocations.tsx + dashboard/allocation-detail  # 「裝置/憑證」清單（add/list/revoke）
└── components/                     # 遮罩+複製的 token 顯示面板（reuse；新增裝置時顯示一次）
tests/
├── contract/test_me_credentials.py / test_admin_credentials.py
└── integration/test_credential_migration.py（Postgres：既有 token 零回歸 + 多憑證）
```

**Structure Decision**：web 專案，核心在後端（model + migration + service + 端點）+ 前端裝置清單。複用既有 token/auth/稽核。

## 關鍵設計（細節見 research）

- **token 驗證零回歸**：`lookup_by_token` 僅多一個 `revoked_at IS NULL`；fingerprint 唯一 → 仍 1 把命中 → 回 allocation。
- **撤回 = 軟撤回**（`revoked_at`）：保留稽核、被撤即排除於 lookup → 立即失效；不刪列。
- **rotate 再定義**：舊「rotate 整把」改為 per-credential（rotate = 撤該把 + 發新把，或保留端點映射到某把）；新增 add/revoke。
- **migration**：`credentials` 改主鍵（`id`）需 Alembic **batch_alter_table**（SQLite 重建表）；既有每列補 `id` + `name="預設"`，
  **不動 token_fingerprint** → 既有 token 不失效。Postgres 整合測試必驗。
- **last_used_at**：成功驗證時節流更新（> N 分鐘才寫），避免每次呼叫寫 DB。

## Complexity Tracking

> 無憲章違反，本節不適用。
