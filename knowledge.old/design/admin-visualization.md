# 設計：Admin 視覺化強化（階段 14）

> Spec：[`specs/024-admin-visualization/`](../../specs/024-admin-visualization/)
> （spec.md / plan.md / research.md / data-model.md / contracts/admin-viz.openapi.yaml）
> 完成：2026-06-03

讓首頁與用量頁的資訊密度與決策力提升一個檔次，但**不淹掉**既有差異化
（quarantine 警示、設定清單、系統資訊）。每張圖回答一個會驅動決策的具體問題，
否則就是 chart-junk。

## 關鍵決策（research 8 條摘要）

1. **圖表 lib 選 recharts**——這是全平台**第一個** charting 依賴（先前 vision 誤寫
   「沿用既有 recharts」，實為錯誤假設；`usage-summary.tsx` 一直是純 CSS bar）。recharts
   React 19 相容、宣告式、gzip 增量 ~100KB（< 150KB 預算）。**只導入這一個**，全平台統一，
   避免 bundle 膨脹與風格不一。

2. **共用 `<Chart>` wrapper**（`components/ui/chart.tsx`）——封裝 `ResponsiveContainer` +
   固定高度 + 統一空狀態 + 載入 skeleton。「同一概念兩份必 drift」，所有圖共用一個 wrapper
   與一份色盤（`CHART_COLORS`）。

3. **heatmap 用 CSS grid，不用 recharts**——168 格（7×24）用 `<div>` 上色比硬塞 recharts
   便宜得多，也更好控軸標。

4. **平台級時序 = `usage_timeseries(allocation_id=None)`**——既有 per-allocation 函式的
   `allocation_id` 改 `str | None`，None 時不加 allocation filter 即平台級加總；既有呼叫不受影響
   （最小改動、零退化）。

5. **provider 維度 = JOIN model_catalog**——`group_by="provider"` 分支 INNER JOIN
   `model_catalog ON slug == CallRecord.model`、`GROUP BY provider`。未進 catalog 的 model
   不計入（provider 未知）。獨立變數名 `provider_stmt`/`provider_rows`（多分支 select 型別教訓）。

6. **heatmap 分桶以 UTC+8**——`started_at + 8h` 後取 weekday/hour，反映台灣本地作息（課堂場景）。
   weekday `0=Sunday`，同時對齊 Postgres `dow` 與 SQLite `%w`，dialect-aware。

7. **隔離原因 surface 自既有稽核 details**——不新增表。`GET /allocations/{id}/quarantine-reason`
   查最近一次 `allocation_quarantined`/`allocation_paused` 事件的 `details`
   （`last_hour_calls`/`baseline_per_hour`/`reason`），組 zh-TW 訊息。舊事件無 details →
   「原因未記錄」、不報錯（FR-017）。前端在分配列徽章 click → popover 就地顯示，**不必點進稽核紀錄**。

8. **佈局不淹警示（FR-008）**——首頁圖表區一律放在 quarantine/paused 警示 + 系統資訊**之下**，
   首頁**最多 3 張圖**（Top 5 tags 是「卡片」非「圖表」，放圖表區之後，不佔圖額度）。
   vitest 斷言 chart 數 ≤3、警示 DOM 順序在圖之前。

## 端點（皆 admin-only，非 admin → 401/403）

| 端點 | 用途 |
|------|------|
| `GET /admin/usage/timeseries?bucket=day\|hour` | 平台級時序（所有分配加總） |
| `GET /admin/usage/heatmap` | weekday x hour 熱度（UTC+8，≤168 格） |
| `GET /admin/usage?group_by=provider` | provider 占比（隨既有 /usage 端點） |
| `GET /admin/allocations/{id}/quarantine-reason` | 隔離/暫停觸發數據 |

**無新表、無 migration**——純查詢層 + 既有稽核 details。

## 交付

- 後端：`services/usage.py`（provider 分支、`HeatCell`+`usage_heatmap`、`usage_timeseries`
  改 optional）、`api/usage.py`（3 新端點）
- 前端：`components/ui/chart.tsx`、`lib/time-range.ts`、`components/time-range-select.tsx`、
  `components/admin-home-charts.tsx`（首頁三圖 + Top 5 tags 卡）、
  `components/admin-usage-charts.tsx`（provider donut + heatmap）、
  `components/quarantine-reason-badge.tsx`
- 測試：`tests/contract/test_usage_viz.py`、`tests/integration/test_usage_viz_agg.py`、
  `frontend/src/__tests__/home-charts.test.tsx`、`time-range-select.test.tsx`

## 後續（第二版，未做）

Allocation 詳情 30 天 line + 配額燃燒投影、Member 跨 allocation donut、月底支出投影、PNG export。
