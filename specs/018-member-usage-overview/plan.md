# Implementation Plan: 成員自助用量總覽

**Branch**: `018-member-usage-overview` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-member-usage-overview/spec.md`

## Summary

成員在自己的儀表板看到跨所有分配的整體用量（token / 估算花費 / 呼叫次數），並可按 model / 分配拆分、選時間區間，嚴格只看自己。技術路徑：在既有 `aggregate_usage` 加一個 `member_id` 可選過濾（三個分支皆已 join `Allocation`，僅需在 base_filters 加一條），新增 `GET /me/usage`（`current_member` scope，回 summary + 可選 breakdown），前端儀表板加用量摘要區塊。複用呼叫紀錄逐筆 point-in-time `cost_usd`，不重新計價。不新增資料表、不改既有授權。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、TanStack Query、shadcn/ui（皆既有，不新增套件）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**
**Testing**: pytest（unit / integration）、Vitest + RTL（前端）
**Target Platform**: web-service backend + SPA frontend
**Project Type**: web（backend + frontend）
**Performance Goals**: 聚合於資料層完成（SQL `GROUP BY` + `SUM`），不逐筆拉回；摘要查詢單次 round-trip
**Constraints**: 嚴格 member-scope（範圍由 session 身份決定，非請求參數）；花費口徑與 admin 一致；只計成功呼叫
**Scale/Scope**: 一個聚合函式加參數 + 一個唯讀端點 + 一塊儀表板 UI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First (NON-NEGOTIABLE)**: ✅ 先寫失敗測試。涵蓋 `aggregate_usage(member_id=...)` 過濾與隔離、`/me/usage` summary / breakdown / 預設區間 / 只計成功 / 未定價旗標 / 資料隔離（A 不見 B）、前端 RTL 摘要渲染。
- **II. Contract-First**: ✅ `GET /me/usage` 介面契約先定（query、回應 envelope、錯誤），記於 `contracts/`。
- **III. 整合測試覆蓋外部依賴**: ✅ 聚合以真實 DB session 驗證（非 mock 邊界），比照既有 `test_aggregation.py`。
- **IV. 可觀測性**: ✅ 端點 member-scope，回應不含他人資料、不洩漏密鑰；錯誤帶明確 code。
- **V. 簡潔優先 (YAGNI)**: ✅ 複用 `aggregate_usage`（只加一個可選參數），不另寫平行聚合、不新增表、不新增匯出/告警（spec 已排除）。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/018-member-usage-overview/
├── plan.md              # 本檔
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1（/me/usage 契約）
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/
├── services/
│   └── usage.py          # 修改：aggregate_usage 加 member_id 可選過濾；
│                         #       加「未定價呼叫計數」供 FR-006 低估提示
└── api/
    └── me.py             # 新增：GET /me/usage（current_member scope）

frontend/src/
├── routes/
│   └── dashboard.tsx     # 修改：頂部用量摘要（P1）+ 拆分/區間（P2）+ 配額視角（P3）
└── lib/                  # 視需要：用量數字格式化（複用既有）

tests/
├── integration/
│   ├── test_me_usage.py           # /me/usage 端點（summary / breakdown / 隔離 / 區間）
│   └── test_usage_member_scope.py # aggregate_usage(member_id) 過濾與隔離
frontend/src/__tests__/
└── dashboard-usage.test.tsx       # 摘要渲染 RTL
```

**Structure Decision**: 沿用既有 web（backend + frontend）佈局。後端只動 `services/usage.py` 與 `api/me.py`，前端只動 `dashboard.tsx`，與現行慣例一致（比照 admin `api/usage.py` + `routes/admin/usage.tsx`）。

## Complexity Tracking

> 無 Constitution 違反，本節留空。
