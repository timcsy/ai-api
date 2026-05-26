# Phase 1 — Data Model

## 1. ModelCatalog（既有，加 2 欄）

| 新欄位 | 型別 | 說明 |
|---|---|---|
| `self_service_enabled` | `bool` not null default `false` | 是否開放成員自助領取 |
| `self_service_default_quota` | `int NULL` | 自助領取的預設月配額；`enabled=true` 時**必填**（app 層驗證）|

**約束**：`self_service_enabled=true` 且 `self_service_default_quota IS NULL` → app 層 422（DB 不設 CHECK，留彈性）。
**讀取相容**：既有 catalog list / detail / access 判定不讀這兩欄，行為不變。

## 2. Allocation（既有，加 1 欄）

| 新欄位 | 型別 | 說明 |
|---|---|---|
| `origin` | `enum('admin','self_service')` not null default `admin` | 發起來源 |

**Backfill**：既有 row 全部 `origin='admin'`（server_default）。
**相容**：`AllocationService.create` 加參數 `origin=AllocationOrigin.admin`（預設不變）；既有呼叫零變動。proxy / quota pool / 計量 **不讀 origin**，行為不變（SC-005）。

## 3. SelfServiceReclaimLock（新）

某（成員, model）在自助 allocation 被撤回後、admin 解鎖前不可重領。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `member_id` | `str(26)` FK→members, PK 之一 | |
| `model_slug` | `str(128)` PK 之一 | 被鎖的 model |
| `locked_at` | `datetime(tz)` not null | 撤回觸發時間 |
| `locked_by` | `str(128)` not null | 撤回的 admin（或 system）|

**PK**：`(member_id, model_slug)` 複合鍵 → 天然「一個 pair 一把鎖」、upsert 冪等。
**生命週期**：撤回 `origin=self_service` allocation → upsert；admin 解鎖 → DELETE。
**索引**：PK 即足夠（查詢都以 pair 或 member 為鍵；加 `INDEX(member_id)` 供 dashboard 查該成員的鎖）。

## 4. AuditEventType（既有 enum，加 3 值）

| 新值 | 觸發 |
|---|---|
| `self_service_claimed` | 成員領取成功（details: member_id, model, allocation_id, quota）|
| `self_service_reclaim_locked` | 撤回自助 allocation 連帶建鎖（details: member_id, model）|
| `self_service_unlocked` | admin 解鎖（details: member_id, model）|

model 開放/配額設定變更**複用** `model_access_policy_updated`（details 標 `{self_service: {...}}`）。

## 5. Migration 0012（down_revision = `0011_tag_rules`）

- `model_catalog`：加 `self_service_enabled`（server_default `false`）+ `self_service_default_quota`（nullable）
- `allocations`：加 `origin`（enum，server_default `admin`）
- 建 `self_service_reclaim_locks` 表 + `INDEX(member_id)`
- 擴 `auth_audit_log` 的 enum（native_enum=False → 實際是 VARCHAR + app 層 enum，無需 DB enum ALTER；確認 column 長度容得下新值）

## 6. 領取資格（非持久化）

```python
class ClaimEligibility(TypedDict):
    eligible: bool
    reason: str | None   # model_not_self_service / model_forbidden / already_claimed / reclaim_locked / member_inactive

# SelfServiceService.check(member, model) → ClaimEligibility
#   1. member.status active？        → 否 member_inactive
#   2. model.self_service_enabled？   → 否 model_not_self_service
#   3. evaluate_visibility(...).visible？ → 否 model_forbidden
#   4. 存在 active origin=self_service allocation(member, model)？ → 是 already_claimed
#   5. 存在 reclaim lock(member, model)？ → 是 reclaim_locked
#   否則 eligible=true
```

順序：先擋「結構性不可」（inactive / 未開放 / 不允許），再擋「狀態性不可」（已持有 / 鎖定）。
