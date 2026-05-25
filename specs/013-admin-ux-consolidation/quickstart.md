# Quickstart：Admin UX Consolidation 驗收場景

每個對應一個 user story。手動跑這 5 個流程即驗收 SC-001 ~ SC-006。

## 前置條件
- Phase 5 已 deploy（/admin/* 11 個頁面已存在）
- Phase 5.1 已 deploy（新 6 個入口可用）

## 場景 1：新 admin 第一天上手（US1 / SC-001）

1. 用空白 DB 啟動服務
2. Bootstrap admin 登入 → 自動到 `/admin`
3. 看到 onboarding checklist「進度 0/4」
4. **不看外部文件**，照頁面提示依序：
   - 點「去 Provider 憑證」→ 加一筆 Azure key → 回首頁，進度 1/4
   - 點「去 Catalog 管理」→ 加一個 model → 回首頁，進度 2/4
   - 點「去成員管理」→ 加一個 member → 回首頁，進度 3/4
   - 點「去分配管理」→ 給該 member 建 allocation → 回首頁
5. 進度 4/4 → 首頁切換為 **dashboard 模式**，顯示用量摘要 / 最近 audit
6. 用該 allocation token curl proxy 應 200

**通過判準**：全程 10 分鐘內，admin 完全不需要外部文件，每步 CTA 顯眼可循。

## 場景 2：給 alice 開通某 model 端對端（US2 / SC-002）

前置：catalog 有 `azure/gpt-4o-mini`（restricted + allow `["eng"]`），alice 是 member 無 tag。

1. 進 `/admin/model` → 點 `azure/gpt-4o-mini`
2. 在 detail 頁的「健康診斷」區塊看到「以 X 視角預覽」面板，選 alice → 顯示「不可見：alice 的 tag 不命中 [eng]」+ 「加 eng tag 給 alice」按鈕
3. 點該按鈕 → 一鍵完成
4. 重新預覽 → 顯示「可見」
5. 在同頁點「給 alice 建 allocation」→ 內嵌 dialog → 一鍵建立

**通過判準**：從 step 1 到 step 5 共 **2 個頁面**（model list + model detail），步驟 ≤ 3。

## 場景 3：tag 群組規則雙向（US3）

1. 進 `/admin/tag` → 點 vip
2. 在 detail 頁同時看到「3 個 member 持有」「2 個 model 將 vip 列為 allowed」
3. 點某 member → 跳 member detail
4. 點某 model → 跳 model detail

**通過判準**：所有跳轉都在 1 click 完成，不需中介頁。

## 場景 4：診斷「為何 X 看不到 Y」（US4 / SC-003）

1. 從任一入口（member detail / model detail）打開「以 X 視角預覽」
2. 輸入 (bob, azure/gpt-5.4-mini) → 15 秒內見答案 + reason_chain
3. 答案中失敗的 check 旁有「修補」按鈕

**通過判準**：「為何看不到」問題從 UI 出來不超過 15 秒，每個失敗原因有具體修補 CTA。

## 場景 5：撤回 / 監控 / 異常處理（US5）

1. 進 `/admin/member` → 點某可疑 member
2. 在該 member detail 看：
   - 最近一週 anomaly 紀錄
   - 該 member 的 allocations（含一鍵 revoke）
   - 該 member 最近 audit 事件
3. 進 `/admin/observability` → 用量 / 配額池 / Rebalance / 稽核 是 4 個 tab，URL 各為 `/admin/observability/usage` 等可分享

**通過判準**：日常維運不需切 4 個獨立 nav。

## 場景 6：舊 deep-link 不壞（SC-005）

依序訪問：
- `/admin/catalog-manage` → 應跳 `/admin/model`
- `/admin/model-access` → 應跳 `/admin/model`
- `/admin/catalog` → 應跳 `/admin/model`
- `/admin/allocations` → 應跳 `/admin/member`
- `/admin/tags` → 應跳 `/admin/tag`
- `/admin/usage` → 應跳 `/admin/observability/usage`
- `/admin/quota-pool` → 應跳 `/admin/observability/quota`
- `/admin/rebalance-log` → 應跳 `/admin/observability/rebalance`
- `/admin/audit` → 應跳 `/admin/observability/audit`

**通過判準**：9 個舊 URL 全部 redirect 到新位置，無 404。

## 場景 7：API contract 不破壞（SC-006）

```bash
uv run pytest tests/contract/ -v
```

**通過判準**：全綠（無 endpoint 簽名變動）。
