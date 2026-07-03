# Implementation Plan: 用量可觀測性 v2（逐筆記錄檢視 + 逐筆含成本 + 逐筆圖）

**Branch**: `056-per-call-records` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)

## Technical Context

- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）；FastAPI、SQLAlchemy 2.x async、Pydantic v2；TanStack Query、shadcn/ui、**recharts**（既有）
- **零 migration**：`CallRecord` 已有 `cost_usd`/`quantity`/`unit`（增量②/0019）；本功能只補「對外輸出 + 篩選 + 介面/圖」
- 對應原則 2（可追蹤，逐筆含成本）+ 原則 6（admin 自助看逐筆）

## 現況與缺口（盤點結論）

- admin 逐筆端點 `GET /admin/allocations/{id}/calls`（records.py）**per-allocation** 存在，但**前端無頁面**、且**跨成員/時間篩選不足**。
- `CallRecordOut` 只帶 tokens/狀態/錯誤——**缺 cost_usd / quantity / unit**。
- 成員 `/me/allocations/{id}/calls` + allocation-detail 有清單但**無成本欄、無逐筆圖**。
- 所有圖皆日/時彙總——**無逐筆散點**。

## 設計

### 後端
1. **`CallRecordOut` 補欄位**（`api/schemas.py`）：`cost_usd: Decimal|None`、`quantity`/`unit`、（順帶 `reasoning_tokens`/`cached_tokens` 若已存）。未定價 → `cost_usd=None`。
2. **新 admin 逐筆端點** `GET /admin/records`（`api/records.py` 或新檔）：篩選 `member_id? / allocation_id? / subject? / from? / to? / outcome? / limit(≤200) / before(游標)`；keyset 游標分頁；回 `{items: CallRecordOut[], next_before}`。服務層 `records.list_records(filters)`（`services/records.py` 或既有）——複用既有 keyset 排序鍵 `(started_at, id)`。
3. **成員逐筆補成本**：`/me/allocations/{id}/calls` 的序列化改用（或對齊）擴充後的 `CallRecordOut`（含 cost/quantity/unit）。
4. 逐筆圖不需新端點——前端直接把逐筆清單當資料點畫。

### 前端
5. **admin 逐筆頁**：觀測（observability）加分頁 **「逐筆記錄」**（`routes/admin/records.tsx`）——篩選（成員下拉、分配、時間範圍、結果）+ 表格（時間/模型/tokens/**花費**/狀態/錯誤）+ 逐筆散點圖。路由掛在 `/admin/observability/records` + tab。
6. **逐筆散點元件**（`components/per-call-scatter.tsx`，recharts `ScatterChart`）：x=時間、y=花費↔tokens 可切換、每點一次呼叫、`Tooltip` 顯示該筆細節。admin 與成員共用。
7. **成員 allocation-detail**：呼叫清單加「花費」欄 + 嵌入逐筆散點（自己的分配）。

### 界線（FR-005）
- admin `/admin/records` 預設限時間窗（如預設近 7 天）+ `limit≤200` + 游標；圖以清單同批資料點（不另抓全量）。標示「顯示此區間前 N 筆」。

## Project Structure（新增/改動）

```
backend/
  src/ai_api/api/schemas.py        # CallRecordOut + cost_usd/quantity/unit
  src/ai_api/api/records.py        # NEW GET /admin/records（跨成員/時間/結果篩選 + 游標）
  src/ai_api/services/records.py   # list_records(filters) keyset（複用排序鍵）
  src/ai_api/api/me.py             # /me/.../calls 序列化補成本
tests/
  tests/contract/test_admin_records.py     # 篩選/游標/含成本/授權
  tests/contract/test_me_calls_cost.py     # 成員逐筆含成本
frontend/
  src/routes/admin/records.tsx             # NEW admin 逐筆頁（篩選+表格+散點）
  src/routes/admin/observability.tsx       # +「逐筆記錄」tab
  src/App.tsx                              # +route
  src/components/per-call-scatter.tsx      # NEW 逐筆散點（admin+成員共用）
  src/routes/allocation-detail.tsx         # 成員：加花費欄 + 逐筆散點
  src/__tests__/admin-records.test.tsx, per-call-scatter.test.tsx
```

## Constitution Check

- **零 migration / 零回歸**：只加輸出欄 + 新唯讀端點 + 前端；既有彙總不動。✅
- **TDD**：admin records 端點（篩選/游標/成本/授權）+ 成員逐筆成本 + 前端逐筆頁/散點 先測。✅
- **不新增套件**（recharts 已有）；**授權沿用**（admin token / 成員 CSRF+session、僅自己分配）。✅
- **未定價語意一致**：cost=None 顯示「—」，不當 0（呼應計費一般化原則）。✅

## Phase 分解見 tasks.md
