# Data Model：成員自助用量視覺化

**本功能不涉及資料模型**——以**成員為範圍**聚合既有用量（`CallRecord` × `Allocation`），無新表、無
migration、無新欄位。以下記錄聚合範圍與隔離不變式，供任務與測試對齊。

## 聚合範圍（非持久化）

| 圖 | 資料來源 | 範圍 |
|----|---------|------|
| 每日趨勢 | `GET /me/usage/timeseries`（新）— `usage_timeseries(member_id=<session>)`，bucket=day | 登入成員**所有自己的憑證**之和，按日分桶 |
| 各 model 占比 | `GET /me/usage?group_by=model`（既有） | 登入成員各 model 之和 |

## 隔離不變式（硬約束，對應 FR-002 / 原則 1、2）

- 兩張圖的 `member_id` **一律來自通過驗證的 session（`current_member`）**。
- 端點**沒有**任何 member/allocation 查詢參數可指定他人；以參數嘗試指定他人不存在（不提供此能力）。
- 回傳資料集**永不包含**他人或跨成員聚合。
- 不變式以測試固化：成員 A 的時序**不得**包含成員 B 的任何呼叫（integration, Postgres）。

## 既有結構（不變更）

- `usage_timeseries`：新增 `member_id: str | None = None` 過濾參數；`None`＝既有平台級行為（不變），
  具體 `allocation_id`＝既有 per-allocation 行為（不變）。
- `aggregate_usage(group_by="model", member_id=...)`：既有，donut 沿用（經 `/me/usage`）。

## 狀態

無狀態、無持久化變更；唯一前端 UI 狀態為時段選擇（`<TimeRangeSelect>`）。
