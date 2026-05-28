# Phase 1 Data Model: 階段 10 使用體驗打磨收尾

**不新增資料表、不變更 schema、不新增 migration。** 僅一處後端序列化新增欄位。

## 既有實體（僅參照）

### Allocation（`/me/allocations` 序列化）
`_alloc_public` 既有回傳：`id`、`resource_model`(slug)、`status`、`quota_tokens_per_month`、`token_prefix`、`price`（`{input_per_1k, output_per_1k}` 或 null）等。
- **新增欄位 `display_name`**：來自 `model_catalog` 中該 slug 的顯示名稱；slug 不在目錄（orphan）時為 `null`。additive、向後相容。

### ModelCatalog（`model_catalog`）
既有；提供 `slug → display_name` 對應與現價（已透過 price_map）。本功能唯讀使用。

## 前端衍生（無持久化）
- 分配卡片：`display_name`（fallback slug）+ 現價（`price.input/output_per_1k` 經 `per1kToPer1m` → 每 1M；null→「未定價」）+ 既有配額進度。
- 可自助領取卡片：既有 `slug` + `display_name` + 導向 `/catalog/{slug}`。
- 呼叫端點：單一 helper `apiBaseUrl() = ${window.location.origin}/v1`。

## 不變式
- `/me/allocations` 既有欄位語意與型別不變，只 additive 加 `display_name`。
- display_name / 現價皆唯讀展示，不改動分配或目錄資料。
