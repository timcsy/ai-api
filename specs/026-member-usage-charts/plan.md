# Implementation Plan: 成員自助用量視覺化（成員端圖表）

**Branch**: `026-member-usage-charts` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/026-member-usage-charts/spec.md`

## Summary

讓非管理員成員在自己的 dashboard 看到**自己用量**的兩張圖（每日趨勢 bar + 各 model 花費 donut）+
時段選擇器，嚴格只看自己（owner-scoping 取自 session）。

技術取向：**最大化複用、最小化新增**。
- **donut 零新後端**——`/me/usage?group_by=model` 已存在（member-scoped via `current_member`）。
- **唯一新後端**——member-scoped 時序：把 `usage_timeseries` 加一個 `member_id` 過濾（JOIN Allocation），
  新增 `GET /me/usage/timeseries`（範圍取自 session、不吃 client id）。
- **前端**複用既有 `<Chart>`/`CHART_COLORS`/`<TimeRangeSelect>`，新增一個 `MemberUsageCharts` 元件，
  就地放進成員 dashboard 的用量區；沿用階段 16 RWD 規範（base `grid-cols-1`、`min-w-0`）。
- **零新依賴、無新表、無 migration。**

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2（後端，既有）；Tailwind、shadcn/ui、
recharts、TanStack Query（前端，既有）——**不新增任何套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——以成員為範圍聚合既有用量
**Testing**: pytest（contract + integration，含 owner-isolation）；vitest + RTL（前端資料映射 / 空狀態）+
360px 手動驗收（純視覺，沿用階段 16 research R6）
**Target Platform**: 現代瀏覽器（桌機 + 手機最小 360px）
**Project Type**: web（`src/ai_api/` 後端 + `frontend/`）
**Performance Goals**: 無新目標；查詢沿用既有用量索引（`started_at`、`allocation_id`）
**Constraints**: **資料隔離（FR-002）為硬約束**——範圍只從 session 取、絕不含跨成員聚合；零新依賴；
桌機 + admin 既有圖零回歸
**Scale/Scope**: 1 個新端點 + 1 個 service 函式擴充 + 1 個前端元件 + dashboard 接線；2 張圖

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（不可妥協）**：後端 member-scoped 時序與 **owner-isolation** 是可測行為 → 先寫失敗 contract/
  integration（Red）：(a) 時序 = 該成員各憑證當日和；(b) **成員只拿得到自己的**（隔離）；(c) 無 `/me` 端點
  能以參數查他人。前端圖表資料映射 / 空狀態以 vitest；純視覺以 360px 手動清單。✅ 通過
- **II. 契約優先**：新端點 `GET /me/usage/timeseries` 先以 OpenAPI 定義（`contracts/`）再實作；既有
  `/me/usage` 不變。✅ 通過
- **III. 整合測試覆蓋外部依賴**：無外部依賴；但**隔離正確性**以 Postgres 整合測試驗（dev SQLite vs prod
  Postgres 一致），沿用既有測試基建。✅ 通過
- **IV. 可觀測性**：唯讀呈現，不涉密鑰／PII（成員只看自己用量，無新洩漏面）。✅ 通過
- **V. 簡潔優先（YAGNI）**：donut 複用既有端點；時序只加一個 `member_id` 過濾（非新函式），沿用「下放
  admin 能力 = 同一聚合 + 擁有者檢查」既有模式；2 張圖、不新增表/依賴。✅ 通過

**結論**：無憲章違反，無需 Complexity Tracking。對應新原則 **6 可達性**（成員自助掌握消耗）與原則
**1 憑證隔離 / 2 可追蹤性**（只看自己）。

## Project Structure

### Documentation (this feature)

```text
specs/026-member-usage-charts/
├── plan.md              # 本檔
├── research.md          # Phase 0：決策（donut 複用、時序加 member_id、owner-scoping、複用前端基建）
├── data-model.md        # Phase 1：無資料模型（記錄聚合範圍與隔離不變式）
├── quickstart.md        # Phase 1：隔離驗收（A 拿不到 B）+ 一致性 + 360px 清單
├── contracts/
│   └── me-usage-timeseries.openapi.yaml  # Phase 1：新端點契約
├── checklists/requirements.md            # spec 品質檢核（16/16）
└── tasks.md             # Phase 2（/speckit.tasks 產出，非本指令）
```

### Source Code (repository root)

```text
src/ai_api/
├── services/usage.py    # usage_timeseries 加 member_id 過濾（JOIN Allocation）
└── api/me.py            # 新增 GET /me/usage/timeseries（current_member、_validate_range）

frontend/src/
├── components/
│   ├── member-usage-charts.tsx   # 新增：每日趨勢 bar + 各 model donut（複用 <Chart>/CHART_COLORS）
│   └── usage-summary.tsx         # （沿用；圖表放其旁或併入用量區）
├── routes/dashboard.tsx          # 接上 <MemberUsageCharts> + <TimeRangeSelect>（用量區）
└── __tests__/                    # vitest：member-usage-charts 資料映射/空狀態
tests/
├── contract/                     # /me/usage/timeseries 契約 + 隔離
└── integration/                  # member-scoped 時序正確性（Postgres）
```

**Structure Decision**：web 專案，後端僅動 `services/usage.py` + `api/me.py`，前端新增 1 元件 + dashboard 接線。
無新表、無 migration、無新依賴。

## Complexity Tracking

> 無憲章違反，本節不適用。
