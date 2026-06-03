# Phase 1：Quickstart — admin 視覺化

以整合測試 + 前端煙霧情境定義驗收。

## 後端聚合（contract / integration）

### 情境 1：平台級每日時序（US1，FR-003/004）
- seed 跨多分配、跨多天的呼叫
- `GET /admin/usage/timeseries?bucket=day&from=&to=`
- **預期**：回每日一個 point，tokens/cost/call_count = 該日**所有分配**之和（非單一分配）

### 情境 2：provider 維度聚合（US2，FR-009）
- seed 用到不同 provider 的 model（catalog 已標 provider）的呼叫
- `GET /admin/usage?group_by=provider&from=&to=`
- **預期**：每 provider 一列，數字 = 該 provider 旗下所有 model 之和（JOIN model_catalog 正確）

### 情境 3：heatmap 分桶（US2，FR-010）
- seed 集中在特定 weekday+hour（UTC+8）的呼叫
- `GET /admin/usage/heatmap?from=&to=`
- **預期**：對應 (weekday, hour) 格 value 較高；分桶以 UTC+8；回 ≤168 格

### 情境 4：隔離原因 surface（US4，FR-014/015/017）
- 觸發一筆 `allocation_quarantined`（details 含 last_hour_calls=1100, baseline=100, reason=ratio）
- `GET /admin/allocations/{id}/quarantine-reason`
- **預期**：回 reason=ratio / last_hour_calls=1100 / baseline=100；message 含「1100」「100」
- **缺 details 的舊資料** → message=「原因未記錄」，不報錯（FR-017）

### 情境 5：既有維度零退化（SC-007）
- 跑既有 `group_by=member/allocation/model/tag` 用量測試
- **預期**：全綠、數字行為不變

### 情境 6：admin-only（FR：viz 端點權限）
- 非 admin 呼叫 timeseries / heatmap / quarantine-reason
- **預期**：401/403

## 前端煙霧（部署後手動）

### 情境 7：首頁三圖 + 警示優先（US1，FR-007/008）
- 開首頁 → 看到 daily spend bar / model donut / top allocations bar
- **隔離警示卡在所有圖表之上、最顯眼**
- 圖表數量 ≤ 3；每張圖可點元素 → 跳對應詳情頁
- daily spend 可切 token / 花費

### 情境 8：用量頁 provider donut + heatmap（US2）
- 開用量頁 → provider 占比 donut + 24×7 heatmap，軸標清楚

### 情境 9：時段選擇器（US3）
- 切「本季」→ 該頁所有圖表一起更新；切「自訂」可指定起訖
- 更新中有載入指示

### 情境 10：暫停/隔離原因顯眼（US4）
- 隔離分配的徽章 hover → 顯示觸發數據；解除頁顯示同資料（不必查稽核）

### 情境 11：Top 5 tags 卡（US5）
- 首頁 Top 5 tags by spend 卡顯示；點 tag → 跳用量頁該 tag 視圖

### 情境 12：空狀態（FR-021/SC-006）
- 全新 / 無資料區間 → 每張圖友善空狀態，不報錯不空白

### 情境 13：bundle 體積（SC-003）
- `npm run build` 成功；確認 recharts 為唯一新圖表依賴；gzip 增量 < 150KB

---

## 測試命名建議

| 情境 | 測試檔 | 函式 |
|------|--------|------|
| 1 | `tests/contract/test_usage_viz.py` | `test_platform_timeseries_sums_all_allocations` |
| 2 | 同上 | `test_group_by_provider` |
| 3 | `tests/integration/test_usage_viz_agg.py` | `test_heatmap_buckets_by_weekday_hour_utc8` |
| 4 | `tests/contract/test_usage_viz.py` | `test_quarantine_reason_from_audit_details` / `_absent_details` |
| 5 | 既有 usage 測試 | （沿用） |
| 6 | `tests/contract/test_usage_viz.py` | `test_viz_endpoints_admin_only` |
| 7–13 | 前端 vitest + 手動煙霧 | chart wrapper 資料映射 + 空狀態單元測試 |
