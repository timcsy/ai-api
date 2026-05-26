# Phase 1 — Data Model

## 1. TagRule（新）

admin 定義的有序自動標籤規則。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `str` ULID, PK | |
| `order_index` | `int` not null, indexed | 評估順序（升冪 first-match-wins）|
| `matcher_type` | `enum` | `email_localpart_regex` / `email_suffix` / `email_domain` / `always` |
| `pattern` | `str(256)` | regex / suffix / domain 字串；`always` 時忽略（可空字串）|
| `tag` | `str(64)` | 命中時要貼的 tag（符合 `^[a-z][a-z0-9_-]{0,63}$`）|
| `enabled` | `bool` not null default true | |
| `created_at` | `datetime(tz)` not null | |
| `created_by` | `str(64)` not null | |

**約束 / 驗證**：
- `tag` 必符合既有 tag regex
- `matcher_type=email_localpart_regex` 時 `pattern` 必通過護欄（compile + anchor + 複雜度）
- `order_index` 不必連續，只需可排序；reorder 一次全寫
- `INDEX(enabled, order_index)` — 評估查詢主路徑

**狀態轉換**：`enabled` true ↔ false（停用不刪）。

## 2. MemberTag（既有，加 2 欄）

| 新欄位 | 型別 | 說明 |
|---|---|---|
| `source` | `enum('manual','auto')` not null default `manual` | tag 來源 |
| `rule_id` | `str(32) NULL` | source=auto 時記命中的 TagRule id（FK 軟參照，不設 hard FK 避免刪規則卡住）|

**Backfill**：既有 row 全部 `source='manual'`、`rule_id=NULL`。

**讀取相容**：access policy / 診斷 / visible-models / tag 詳情 **不讀 source**，行為不變（SC-005）。

## 3. AuditEventType（既有 enum，無新值）

沿用既有 `member_tag_added`；details 帶 `{source: "auto", rule_id: ...}` 區分。不新增 enum 值（避免又一次 migration enum 擴充）。

## Migration

- **0011** `tag_rules`：
  - 建 `tag_rules` 表 + index `(enabled, order_index)`
  - `member_tags` 加 `source`（enum，server_default `manual`）+ `rule_id`（nullable）
  - 既有 row 由 server_default 自動 backfill `manual`

## 評估輸出（非持久化）

```python
class RuleMatch(TypedDict):
    matched: bool
    rule_id: str | None
    tag: str | None
    matcher_type: str | None
```

`TagRuleService.evaluate(email)` 回此形狀；`apply_to_new_member` 用它決定貼哪個 tag。
