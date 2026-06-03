# Phase 1：資料模型

**本功能不新增任何資料表、不新增 migration。** 全部以既有表查詢聚合。前端新增 recharts 依賴。

## 既有表（沿用，不改）

- `call_records`（聚合來源：tokens / cost / started_at / model / allocation_id）
- `allocations`（member_id / is_service_allocation / status / subject_snapshot）
- `model_catalog`（**provider** 欄，有 index）— provider 維度 JOIN 來源
- `member_tags`（tag 聚合，階段 15）
- `auth_audit_log`（隔離/暫停事件 + `details`：last_hour_calls / baseline_per_hour / reason）

## 查詢層概念（非持久化）

### 1. 平台級每日時序（FR-003/004）

```text
-- usage_timeseries 既有，allocation_id 改 optional：None 時不加 allocation filter
SELECT date_trunc('day', started_at) AS ts,  -- PG；SQLite strftime
       SUM(total_tokens), SUM(cost_usd), COUNT(*)
FROM call_records
WHERE outcome='success' AND started_at >= :from AND started_at < :to
  [AND allocation_id = :allocation_id]   -- 僅 per-allocation 端點帶
GROUP BY ts ORDER BY ts
```
回 `list[TimeseriesPoint]`（既有 dataclass：ts / tokens / cost / call_count）。

### 2. provider 維度（FR-009）

```text
SELECT model_catalog.provider AS group_key, SUM(...), COUNT(*)
FROM call_records
JOIN allocations ON allocations.id = call_records.allocation_id
JOIN model_catalog ON model_catalog.slug = call_records.model
WHERE outcome='success' AND started_at range...
GROUP BY model_catalog.provider ORDER BY SUM(total_tokens) DESC
```
回既有 `UsageItem`（group_key=provider、display_name=provider）。新 `GroupBy` 值 `"provider"`。

### 3. hour × weekday heatmap（FR-010）

```text
-- 以 UTC+8 分桶（對台灣 admin 直覺，與通知 email 一致）
SELECT weekday, hour, SUM(total_tokens) AS value, COUNT(*) AS cnt
FROM call_records
WHERE outcome='success' AND started_at range...
GROUP BY weekday, hour    -- weekday 0-6, hour 0-23（取自 started_at + 8h）
```
新 dataclass `HeatCell(weekday: int, hour: int, tokens: int, call_count: int)`；回 ≤168 格。

### 4. 隔離/暫停原因（FR-014~017）

```text
-- 該分配最近一次 allocation_quarantined / allocation_paused 稽核事件
SELECT event_type, details, created_at
FROM auth_audit_log
WHERE target_type='allocation' AND target_id=:id
  AND event_type IN ('allocation_quarantined','allocation_paused')
ORDER BY created_at DESC LIMIT 1
```
回 `{event_type, reason, last_hour_calls, baseline_per_hour, occurred_at}`（從 details 取，缺則 null →
前端顯示「原因未記錄」）。

## 型別變更（code-level，無 schema）

- `services/usage.py`：
  - `GroupBy` 加 `"provider"`
  - `usage_timeseries` 的 `allocation_id: str` → `allocation_id: str | None = None`
  - 新增 `HeatCell` dataclass + `usage_heatmap()` 函式
  - 新增 `aggregate_usage` 的 provider 分支
- `api/usage.py`：3 個新端點（見 contracts）
- 新增 `services/allocations.py` 或 `api/allocations.py` 的 `quarantine-reason` 查詢

## 前端依賴

- `recharts@^2.15`（package.json 新增；React 19 相容）

## 驗證規則

| 規則 | 對應 FR | 實作位置 |
|------|---------|----------|
| 平台時序 = 跨所有分配聚合 | FR-003 | `usage_timeseries(allocation_id=None)` |
| provider 聚合 JOIN catalog 正確 | FR-009 | provider 分支整合測試 |
| heatmap 分桶 UTC+8 正確 | FR-010 | heatmap 整合測試 |
| 隔離原因取自既有稽核 details | FR-014/015 | quarantine-reason 端點；缺則「原因未記錄」FR-017 |
| 首頁 ≤3 圖、警示在上 | FR-007/008 | 前端佈局（vitest 驗 DOM 順序 / 數量） |
| 只導一個圖表 lib | FR-001 | package.json 僅 recharts |
| 不新增表/migration | SC-007 | 純查詢層 + 前端 |
