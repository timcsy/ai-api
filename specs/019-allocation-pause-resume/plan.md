# Implementation Plan: 憑證暫停 / 恢復

**Branch**: `019-allocation-pause-resume` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-allocation-pause-resume/spec.md`

## Summary

為 allocation 生命週期加一個可逆的 `paused` 狀態：管理員可暫停一把進行中憑證（呼叫即時被擋）、之後恢復（同一把 token 立即又能用）。暫停只切 status，**不動 token、不建 reclaim lock、不改配額**——這是與 revoke（終局、換 token）的關鍵差異。proxy 沿用既有「逐次檢查當前狀態」執法點加入 `paused` 拒絕（回 `allocation_paused` / 計為 `rejected_paused`）。三個相關 enum 皆 `native_enum=False`（存字串），故**無需 migration、無新表**。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、shadcn/ui（皆既有，不新增套件）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**（`AllocationStatus`、`CallOutcome`、`AuditEventType` 皆 `Enum(..., native_enum=False)` 存 VARCHAR，加列舉值不需 schema 變更）
**Testing**: pytest（unit / contract / integration）、Vitest + RTL（前端）
**Target Platform**: web-service backend + SPA frontend
**Project Type**: web（backend + frontend）
**Performance Goals**: 暫停/恢復為單筆狀態切換；拒絕判定沿用既有 proxy 逐次狀態檢查，無額外查詢成本
**Constraints**: 暫停即時生效；保留同一 token；狀態機嚴格（active↔paused，不碰 revoked/quarantined）；既有行為零退化
**Scale/Scope**: 1 個新狀態值 + 2 個服務方法 + 2 個 admin 端點 + proxy 一處拒絕 + 前端按鈕

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First (NON-NEGOTIABLE)**: ✅ 先寫失敗測試。涵蓋服務層狀態機（pause active→paused / resume paused→active / 非法轉移拒絕）、proxy `paused` 拒絕（回 `allocation_paused`、計 `rejected_paused`）、admin 端點、稽核、前端 RTL。
- **II. Contract-First**: ✅ `POST /admin/allocations/{id}/pause`、`/resume` 介面契約先定（成功 / 狀態衝突 / 404），記於 `contracts/`。
- **III. 整合測試覆蓋外部依賴**: ✅ 以真實 DB session（contract in-memory SQLite + 必要時 testcontainers）驗證狀態轉移與 proxy 拒絕，非 mock 邊界。
- **IV. 可觀測性**: ✅ 暫停/恢復寫稽核（`allocation_paused`/`allocation_resumed`）；被擋呼叫記為 `rejected_paused`，可與 revoked/quota 區分；錯誤帶明確 code，不洩漏 token。
- **V. 簡潔優先 (YAGNI)**: ✅ 複用既有狀態欄位與 proxy 執法點；不新增表、不新增 migration、不做排程/成員自助暫停（spec 已排除）。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/019-allocation-pause-resume/
├── plan.md              # 本檔
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1（pause / resume 端點契約）
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── allocation.py     # 修改：AllocationStatus 加 `paused`
│   ├── call_record.py    # 修改：CallOutcome 加 `rejected_paused`
│   └── auth_audit.py     # 修改：AuditEventType 加 `allocation_paused` / `allocation_resumed`
├── services/
│   └── allocations.py    # 新增：pause() / resume()（比照 revoke，但只切 status，不動 token / 不建 lock；狀態機守衛 + 稽核）
├── proxy/
│   └── router.py         # 修改：status == "paused" → 拒絕（`allocation_paused` 403 / `rejected_paused`）
└── api/
    └── allocations.py    # 新增：POST /allocations/{id}/pause、/resume（比照 unquarantine，require_admin_token）

frontend/src/routes/admin/
├── allocations.tsx       # 修改：暫停/恢復鈕 + mutation（與撤回並列，文案區分）
└── member-detail.tsx     # 修改（次要）：成員詳情分配列也加暫停/恢復

tests/
├── contract/
│   └── test_allocation_pause_resume.py   # pause/resume 端點 + 狀態機 + 稽核
├── integration/
│   └── test_proxy_paused.py              # 暫停中呼叫被擋（rejected_paused）、恢復後同 token 可用
└── (前端) frontend/src/__tests__/admin-allocations-pause.test.tsx
```

**Structure Decision**: 沿用既有 web 佈局與 allocation 生命週期慣例（pause/resume 比照 `revoke`/`unquarantine` 的服務方法 + admin 端點寫法）；proxy 拒絕沿用既有 status 檢查點（`router.py` 已「先 lookup 後檢查狀態」）。

## Complexity Tracking

> 無 Constitution 違反，本節留空。
