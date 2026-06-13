# Phase 1 Data Model: 成本制配額

**核心結論：一個 additive migration（0020）、零新表。** 沿用既有 `call_records.cost_usd`（0019）作為累計來源；分配只加一個選填上限欄；新拒絕 outcome 走 VARCHAR enum 無 migration。

## 1. Allocation（既有，加一欄）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `quota_cost_usd_per_month` | `Numeric(10,6)` **nullable** | 每月花費上限（USD）。NULL ⇒ 無花費上限（維持現況）。**migration 0020 純加欄。** |

既有 `quota_tokens_per_month`（token 上限）、`quota_locked`、`is_service_allocation` 等**不變**。兩種上限可並存。

**驗證規則**：`>= 0`（0＝立即擋；負值拒絕）。admin create/update 收選填值；空＝NULL（不設）。

**與自適應池**：`quota_cost_usd_per_month` **不在** `quota_pool` 的讀寫範圍（池只動 `quota_tokens_per_month`）→ 不被再分配（SC-005）。

## 2. CallRecord（既有，沿用 + 新 outcome 值）

- 累計來源：`sum(cost_usd) where allocation_id=? and outcome=success and started_at>=月初(UTC)`。`cost_usd` NULL（未定價）→ `coalesce 0`，不計入。
- `CallOutcome` 列舉新增 **`rejected_cost_quota_exceeded`**（`Enum(native_enum=False, length=32)` 存 VARCHAR → **無 migration**）。被花費上限擋的呼叫以此 outcome 落一筆（綁 allocation、status 403），與 `rejected_quota_exceeded`（token）可區分。

## 3. 衍生計算（不落表）

| 名稱 | 定義 | 用途 |
|---|---|---|
| `current_month_cost(allocation_id)` | `Σ cost_usd`（成功、本月、coalesce 0）→ `Decimal` | preflight 檢查 + 用量顯示 |
| `is_over_cost_quota(allocation, spent)` | `cap is not None and spent >= cap` | preflight / watcher 共用判斷 |
| `session_running_cost(sess, price)` | realtime 連線進行中累計 = `session_quantity(sess, price.unit) × price.per_unit` | 連線中把關（committed + 此值 ≥ cap） |

## 4. 序列化新增欄（API 輸出）

| 端點 | 新欄 |
|---|---|
| admin 分配（list/detail）+ create/update 輸入 | `quota_cost_usd_per_month`（選填） |
| `/me/usage`、`/me/allocations`、admin 用量每分配 | `cost_used_this_month`（Decimal 字串）+ `quota_cost_usd_per_month` |

## 5. 狀態/流程

- **同步端點**：preflight 階段 `current_month_cost ≥ cap` → reject `cost_quota_exceeded`（403）+ 記一筆 `rejected_cost_quota_exceeded`。
- **realtime**：建立時 preflight 含 cost 檢查；連線中 watcher 每 N 秒 `committed + running ≥ cap` → close（已累計時長落帳，沿用「任何 close 路徑都落帳」）。

---

**Migration 結論**：**`0020` 純加 `allocations.quota_cost_usd_per_month`（nullable）**。token 欄、`call_records` 皆不動（`cost_usd`/`unit`/`quantity` 0019 已就緒）；新 outcome 為 VARCHAR enum 值，非 schema 變更。
