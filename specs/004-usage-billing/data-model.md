# Phase 1 Data Model: 階段 3a — 用量觀測與費用計算

## 概覽

```
PriceList (new)            Allocation (extended)         CallRecord (extended)
                              + quota_tokens_per_month     + cost_usd
                              + is_service_allocation
```

---

## PriceList（新表）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | ULID(text) | ✓ | PK |
| `provider` | text(64) | ✓ | 例 `azure`, `anthropic` |
| `model` | text(128) | ✓ | 例 `gpt-4o-mini` |
| `input_per_1k_tokens_usd` | numeric(12,8) | ✓ | 每 1000 input token 的 USD |
| `output_per_1k_tokens_usd` | numeric(12,8) | ✓ | 每 1000 output token 的 USD |
| `effective_from` | timestamptz | ✓ | 自此時間起該價目生效 |
| `created_at` | timestamptz | ✓ | 載入時間 |
| `created_by` | text(128) | ✓ | 如 `cli:timmy` |
| `source_note` | text | ✗ | 來源說明，例「Azure pricing snapshot 2026-05」 |

**Constraints**：
- UNIQUE `(provider, model, effective_from)`
- INDEX `idx_pricelist_lookup` on `(provider, model, effective_from desc)` — 查詢主要路徑

**State transition**：immutable。修改價目 = 載入新 yaml 並設新 `effective_from`。

---

## Allocation（擴充）

新增欄位：

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `quota_tokens_per_month` | int | NULL | NULL = unlimited；非 NULL = 每月上限 |
| `is_service_allocation` | bool | false | 服務型分配標記 |

**驗證規則**：
- `quota_tokens_per_month` ≥ 0（NULL 不限）
- `is_service_allocation` 為 true 時建議 `quota_tokens_per_month` 設 NULL（unlimited），但非強制

---

## CallRecord（擴充）

新增欄位：

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `cost_usd` | numeric(10,6) | NULL | 寫入時 point-in-time 計算；無價目時 NULL |

**計算規則**（記錄時）：
```
cost_usd = (prompt_tokens / 1000.0) * input_per_1k
         + (completion_tokens / 1000.0) * output_per_1k
```
若 prompt/completion tokens 為 NULL 視為 0；若找不到 PriceList 即 NULL。

**新 outcome 值**：`rejected_quota_exceeded`（加進既有 enum）

---

## Settings（擴充）

| 欄位 | 型別 | 預設 | 用途 |
|---|---|---|---|
| `cors_origins` | list[str] | `[]` | CORS allowlist；非空時啟用 |

---

## Query Patterns

### Q1: 當月配額累計
```sql
SELECT COALESCE(SUM(total_tokens), 0)
FROM call_records
WHERE allocation_id = :id
  AND outcome = 'success'
  AND started_at >= :month_start_utc
```
- 使用既有 `idx_callrecord_allocation_time` index

### Q2: by member usage（過去 30 天）
```sql
SELECT m.id, m.email, m.display_name,
       SUM(c.total_tokens) AS total_tokens,
       SUM(c.prompt_tokens) AS prompt_tokens,
       SUM(c.completion_tokens) AS completion_tokens,
       SUM(COALESCE(c.cost_usd, 0)) AS total_cost_usd,
       COUNT(*) AS call_count
FROM call_records c
JOIN allocations a ON a.id = c.allocation_id
JOIN members m ON m.id = a.member_id
WHERE c.started_at >= :from AND c.started_at < :to
  AND c.outcome = 'success'
GROUP BY m.id, m.email, m.display_name
ORDER BY total_tokens DESC
```

### Q3: by allocation timeseries（day bucket）
```sql
SELECT date_trunc('day', started_at) AS day,
       SUM(total_tokens) AS tokens,
       SUM(COALESCE(cost_usd, 0)) AS cost_usd,
       COUNT(*) AS call_count
FROM call_records
WHERE allocation_id = :id
  AND started_at >= :from AND started_at < :to
  AND outcome = 'success'
GROUP BY day
ORDER BY day
```

> SQLite 沒有 `date_trunc`；用 `strftime('%Y-%m-%d', started_at)` 替代。
> 抽象到 `services/usage.py` 內部 helper，依 dialect 選擇。

### Q4: price lookup
```sql
SELECT *
FROM price_list
WHERE provider = :provider
  AND model = :model
  AND effective_from <= :call_time
ORDER BY effective_from DESC
LIMIT 1
```

---

## Migration 0004 概要

1. CREATE TABLE `price_list` (含 indexes)
2. ALTER `allocations` ADD `quota_tokens_per_month`, `is_service_allocation`
3. ALTER `call_records` ADD `cost_usd`
4. 擴充 `call_records.outcome` enum，加 `rejected_quota_exceeded`
   （以 batch_alter_table 重定義 Enum，沿用 Phase 2.5 0003 的模式）
