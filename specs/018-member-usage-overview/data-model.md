# Phase 1 Data Model: 成員自助用量總覽

本功能**不新增資料表、不變更 schema、不新增 migration**。僅複用既有實體聚合。

## 既有實體（僅參照）

### CallRecord（`src/ai_api/models/call_record.py`）
用量與花費的事實來源。相關欄位：`allocation_id`、`outcome`、`started_at`、
`prompt_tokens`、`completion_tokens`、`total_tokens`、`cost_usd`（呼叫當時 point-in-time 成本）。
- 只計 `outcome == success` 的呼叫。
- `cost_usd` 為 NULL / 0 表示呼叫當時該 model 無價目 → 計入「未定價」判定。

### Allocation
把 `CallRecord` 歸屬到成員的橋樑：`member_id`、`quota_tokens_per_month`、
`is_service_allocation`、`origin`。member-scope 過濾即加 `Allocation.member_id == <me>`。

### Member
用量歸屬主體；查詢範圍 = 登入成員。

## 衍生聚合（非持久化）

### UsageSummary（端點回應用，無新 ORM）
| 欄位 | 來源 |
|------|------|
| total_tokens / prompt_tokens / completion_tokens | `SUM` over 該成員成功呼叫 |
| total_cost_usd | `SUM(cost_usd)`（point-in-time） |
| call_count | `COUNT` |
| has_unpriced | 是否存在「成功且 `total_tokens>0` 但 `cost_usd` NULL/0」的呼叫 |

由 `aggregate_usage(group_by="member", member_id=me)` 的單列 + 一支未定價 count 查詢組成。

### UsageBreakdownItem（沿用既有 `UsageItem` dataclass）
`group_key`、`display_name`、token 三項、`total_cost_usd`、`call_count`
（`is_service_allocation` 於 allocation 分組時帶出）。由
`aggregate_usage(group_by="model"|"allocation", member_id=me)` 產生。

## 服務層改動

### `aggregate_usage`（`services/usage.py`）— 加可選參數
- 新增 `member_id: str | None = None`。
- 非空時於 `base_filters` 加 `Allocation.member_id == member_id`（三分支皆已 join `Allocation`，一處生效）。
- 行為對既有呼叫（不傳 `member_id`）**完全不變**（admin 路徑零影響）。

### 未定價計數（FR-006）
新增輕量 helper（或於端點內）：count 成功 + `total_tokens>0` + `cost_usd` IS NULL/0 + member + 區間 → `has_unpriced`。

## 設定 / 常數
| 項 | 來源 | 用途 |
|----|------|------|
| 預設區間 | 端點預設 `from=本月 UTC 月初`、`to=now(UTC)` | FR-004 |
| 範圍上限 | 沿用 admin usage 的 `MAX_RANGE` 驗證 | 防過寬查詢 |
