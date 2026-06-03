# Phase 1：資料模型

**本功能不新增任何資料表、不新增 migration。** 全部以既有表在查詢時 JOIN 聚合。

## 既有表（沿用，不改）

### `member_tags`（既有）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `member_id` | `String(26)` PK | FK → members.id |
| `tag` | `String(64)` PK | 自由字串 tag（composite PK 與 member_id） |
| `added_by` | `String(64)` | |
| `added_at` | `TIMESTAMP TZ` | |
| `source` | enum | manual / rule |
| `rule_id` | `String(32)?` | |

- composite PK `(member_id, tag)` → 一成員多 tag = 多列；tag 名稱集合 = `SELECT DISTINCT tag`
- index `idx_member_tags_tag` ON `tag` → 支援 tag 過濾與 GROUP BY

### `call_records`、`allocations`（既有，不改）

- 聚合來源；`call_records.allocation_id → allocations.id → allocations.member_id`

## 查詢層概念（非持久化）

### Tag 用量聚合（tag 維度）

```text
SELECT member_tags.tag AS group_key,
       SUM(call_records.total_tokens), SUM(prompt), SUM(completion),
       SUM(cost_usd), COUNT(*), SUM(reasoning_tokens), SUM(cached_tokens)
FROM call_records
JOIN allocations ON allocations.id = call_records.allocation_id
JOIN member_tags ON member_tags.member_id = allocations.member_id
WHERE call_records.outcome = 'success'
  AND call_records.started_at >= :from AND call_records.started_at < :to
  [AND allocations.is_service_allocation = true]   -- service_only 可選
GROUP BY member_tags.tag
ORDER BY SUM(total_tokens) DESC
```

- 回傳形狀 = 既有 `UsageItem`（`group_key=tag`、`display_name=tag`、token/cost/count）
- 重疊由 JOIN 自然產生：成員掛 N tag → 其 call 與 N 個 member_tags 列各配一次 → 計入 N 個 tag

### Tag 成員下鑽（給定 tag → 成員明細）

```text
-- 重用既有 member 分支，加 tag 成員過濾
... member 維度聚合 ...
WHERE allocations.member_id IN (SELECT member_id FROM member_tags WHERE tag = :tag)
```

- 回傳 = 該 tag 底下每位成員的 `UsageItem`（與既有 member 維度同形）

## 型別變更（code-level，無 schema）

- `services/usage.py`：`GroupBy = Literal["member", "allocation", "model", "tag"]`（加 `"tag"`）
- 新增聚合分支（tag）+ 下鑽函式（tag → members）
- `UsageItem` dataclass **不變**（tag 維度沿用既有欄位：`group_key`=tag、`display_name`=tag）

## 驗證規則

| 規則 | 對應 FR | 實作位置 |
|------|---------|----------|
| tag 聚合 = 成員各自相加 | FR-002 / SC-002 | tag 分支的 GROUP BY 正確性（整合測試逐筆驗） |
| 多 tag 重疊正確計入 | FR-005 | JOIN member_tags 自然產生（測試驗成員 C 在兩 tag 都計入） |
| service_only 支援、member_id 不接受 | R5 | tag 分支只套 service_only，不套 member-scope |
| admin-only | FR-012/013 | 端點掛既有 admin router；無 /me 對應 |
| 不新增表/migration | SC-006 | 純查詢層；無 alembic 變更 |
