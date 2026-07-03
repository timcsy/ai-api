---
description: "Task list for 用量可觀測性 v2（逐筆記錄檢視 + 逐筆含成本 + 逐筆圖）"
---

# Tasks: 用量可觀測性 v2

**Prerequisites**: spec.md、plan.md
**Tests**: TDD。**零 migration、零回歸**（既有彙總可觀測性測試全綠為底線）。

## Phase 1: Setup
- [X] T001 基線：`pytest tests/ -q -k "records or usage or calls or me_alloc"` + 前端 `vitest run src/__tests__/*usage* src/__tests__/*alloc*` 綠（零回歸起點）。

## Phase 2: Foundational — 逐筆輸出含成本（US2 底層，阻斷 US1/US3 顯示）
- [X] T002 [test][US2] `tests/contract/test_me_calls_cost.py`：一筆已定價呼叫 → `/me/allocations/{id}/calls` 該筆含 `cost_usd`+`quantity`/`unit`；未定價 → `cost_usd=null`。先紅。
- [X] T003 [US2] `api/schemas.py::CallRecordOut` 加 `cost_usd: Decimal|None`、`quantity`、`unit`（+ 既有 reasoning/cached tokens 若有）。
- [X] T004 [US2] 成員 `/me/allocations/{id}/calls` + admin per-alloc `/admin/allocations/{id}/calls` 序列化帶新欄；未定價→None。
- [X] T005 [US2] 跑 T002 綠 + 既有逐筆/彙總測試零回歸。

## Phase 3: US1 — 管理員逐筆記錄檢視（P1，主缺口）
- [X] T006 [test][US1] `tests/contract/test_admin_records.py`：`GET /admin/records` 依 `member_id/allocation_id/from/to/outcome` 篩選、游標 `before` 分頁（不重複/不遺漏）、含成本；非 admin→401；預設時間窗/上限。先紅。
- [X] T007 [US1] `services/records.py::list_records(filters)`：CallRecord 依篩選 + keyset 排序鍵 `(started_at desc, id)`、`limit+1` 探測 next。
- [X] T008 [US1] `api/records.py` 新增 `GET /admin/records`（require_admin_token；回 `{items, next_before}`）。
- [X] T009 [US1] 跑 T006 綠。

## Phase 4: US3 — 逐筆呼叫圖表（P2）
- [X] T010 [test][US3] `frontend .../per-call-scatter.test.tsx`：給逐筆資料 → 每筆一點、y 可切 花費↔tokens、tooltip 顯示該筆細節。先紅。
- [X] T011 [US3] `components/per-call-scatter.tsx`（recharts `ScatterChart`：x=時間、y=cost|tokens 切換、Tooltip 帶 model/tokens/花費/狀態）。
- [X] T012 [US3] 跑 T010 綠。

## Phase 5: 前端整合（admin 頁 + 成員頁）
- [X] T013 [US1/US3] `routes/admin/records.tsx`：篩選（成員下拉、分配、時間範圍、結果）+ 表格（時間/模型/tokens/花費/狀態/錯誤）+ 逐筆散點；`observability.tsx` 加「逐筆記錄」tab；`App.tsx` 加 `/admin/observability/records` route；`admin-records.test.tsx`。
- [X] T014 [US2/US3] `routes/allocation-detail.tsx`（成員）：呼叫清單加「花費」欄 + 嵌入逐筆散點（自己的分配）。
- [X] T015 前端全套 `vitest run` + `tsc --noEmit; echo $?` + `npm run build` 綠。

## Phase 6: Polish & 上線
- [X] T016 全套零回歸：`pytest tests/ -q` + `ruff check .` + `uv run mypy src/ai_api`；前端全套 vitest + tsc(退出碼) + build。
- [X] T017 PR + squash-merge（CI 綠）。前後端兩 image、**無 migration**；部署 ccsh + tew（ccsh 走 SSH 隧道；helm 不接 rollout-status 於同指令）。部署後驗 admin 逐筆頁 + 成員逐筆含成本 + 散點。
- [X] T018 知識同步：experience 蒸餾「逐筆可觀測性：後端逐筆端點/資料早有，缺的是對外輸出補成本 + admin UI 頁 + 逐筆散點；彙總圖看不出離群單次呼叫」；vision 視需要加一筆。

## Dependencies
- Foundational（T002–T005，逐筆含成本）阻斷顯示層。US1（T006–09 admin 端點）依賴 schema 已含成本；US3（T010–12 散點元件）獨立可先做（吃資料即可）。前端整合（T013–14）依賴後端端點 + 散點元件。
- **MVP＝Foundational + US1**（admin 看得到含成本的逐筆清單）。US3 散點、成員頁其後。
