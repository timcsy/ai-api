# Phase 1 Data Model: 階段 3c — Adaptive Quota Pool

## 概覽

```
RebalanceLog (new)               Allocation (extended)
  - id, period_yyyymm              + quota_locked
  - triggered_by, timestamps
  - T_before/after, counts
  - details (JSON)
```

無新主領域實體；rebalance 結果是 Allocation 的更新 + RebalanceLog 一筆紀錄。

---

## RebalanceLog（新表）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) ULID | ✓ | PK |
| `period_yyyymm` | text(6) | ✓ | rebalance 處理的「上月」識別，例 `202605`（rebalance 在 2026-06-01 跑時填）|
| `triggered_by` | text(64) | ✓ | `cron` / `admin:<id>` / `member:<id>` |
| `started_at` | timestamptz | ✓ | rebalance 起跑時間 |
| `finished_at` | timestamptz | ✓ | commit 時間 |
| `T_before` | int | ✓ | 跑前的 settings.pool_total_tokens_per_month |
| `T_after` | int | ✓ | 跑後（通常與 before 相同，除非 admin 中途改設定） |
| `scanned` | int | ✓ | 全部 active allocation 數 |
| `changed` | int | ✓ | 實際 UPDATE 的池內 allocation 數 |
| `algorithm_version` | text(16) | ✓ | 例 `v1` |
| `details` | JSON | ✓ | per-allocation 變更紀錄（research.md §7 schema） |

**Constraints**：
- Partial UNIQUE on `period_yyyymm` WHERE `triggered_by = 'cron'`
  （SQLite 退化為 `(period_yyyymm, triggered_by)` UNIQUE — `cron` 本身固定字串
  故等效。具體實作差異交給 0005 migration）
- Index on `started_at desc`（list 查詢用）

---

## Allocation（擴充）

新欄位：

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `quota_locked` | bool | false | rebalance 不修改 `quota_locked=true` 的 allocation 的 quota |

**互動規則**：
- `quota_locked=true` AND `is_service_allocation=true` 為合法但冗餘
  （皆豁免）；rebalance 視為「reserved」
- 池內成員定義：`status=active AND !is_service_allocation AND !quota_locked AND status!=quarantined`

---

## AuthAuditLog（既有，擴 event_type）

加 4 個列舉值：

| 新值 | 用途 |
|---|---|
| `quota_pool_rebalanced` | 成功 rebalance；details 含 RebalanceLog id |
| `rebalance_failed` | rebalance 失敗（含原因：守恆 fail、reserved 超 T 等） |
| `pool_exhausted_by_reserved` | reserved 占用 + floor·N > T 的特殊失敗情境 |
| `pool_idle` | 池內 0 個 allocation（所有人都 service/locked）— 提醒 admin |

---

## Settings（擴充）

| 欄位 | 型別 | 預設 | 用途 |
|---|---|---|---|
| `pool_total_tokens_per_month` | int | 0 | T；0 表 disabled |
| `pool_floor_per_allocation` | int | 1000 | 每池內 allocation 保底 quota |

`T=0` 時：rebalance 直接 no-op + audit「pool disabled」，不修改任何 quota。

---

## Query Patterns

### Q1: 取得池內成員 + 上月用量

```sql
SELECT a.id, COALESCE(SUM(c.total_tokens), 0) AS usage
FROM allocations a
LEFT JOIN call_records c ON c.allocation_id = a.id
    AND c.outcome = 'success'
    AND c.started_at >= :prev_month_start
    AND c.started_at < :this_month_start
WHERE a.status = 'active'
  AND a.is_service_allocation = false
  AND a.quota_locked = false
GROUP BY a.id
ORDER BY a.id   -- 確定性順序，方便測試
```

### Q2: 取得 reserved 占用（service / locked）

```sql
SELECT
  COALESCE(SUM(CASE WHEN is_service_allocation THEN quota_tokens_per_month ELSE 0 END), 0) AS service_reserved,
  COALESCE(SUM(CASE WHEN quota_locked AND NOT is_service_allocation THEN quota_tokens_per_month ELSE 0 END), 0) AS locked_reserved
FROM allocations
WHERE status = 'active'
  AND quota_tokens_per_month IS NOT NULL
```

> 注意：service / locked allocation 若 `quota_tokens_per_month IS NULL`
> 視為 unlimited — 但本階段「池」概念與「unlimited」不相容；spec 假設
> 進池前 admin 已賦予明確 quota。若遇到 NULL 即視為 reserved=0
> 並在 audit 寫警告。

### Q3: cron 同月去重檢查

INSERT 前，partial UNIQUE 約束自動處理 — 程式只需接 `IntegrityError`
即可分辨「已跑過」vs 「真正錯誤」。

---

## Migration 0005 概要

1. CREATE TABLE `rebalance_log` + indexes
2. ALTER `allocations` ADD `quota_locked` (bool default false)
3. 擴 `auth_audit_log.event_type` enum（沿用 batch_alter 模式）
