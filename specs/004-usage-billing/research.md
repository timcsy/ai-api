# Phase 0 Research: 階段 3a — 用量觀測與費用計算

---

## 1. 聚合查詢：ORM vs raw SQL

**決策**：用 SQLAlchemy Core (`select`、`func.sum`、`group_by`) — 不走 ORM
`session.execute(select(Model))`，而是 `select(CallRecord.member_id_via_join,
func.sum(...).label(...))`，回傳 tuples 自行打包。

**理由**：
- 聚合不需要 ORM 物件；用 ORM 反而慢且 lazy-load 風險高
- SQLAlchemy Core 對兩個 backend (Postgres + SQLite) 抽象一致
- experience「async lazy-load 禁止」教訓最自然的應用

**已評估**：
- 純文字 SQL：失去 type checking 與跨 backend 抽象
- Pandas / Polars：YAGNI；資料量小

---

## 2. JOIN 鏈：CallRecord → Allocation → Member

**決策**：所有 group_by 查詢統一從 `CallRecord` 出發，JOIN `Allocation`（取
member_id、is_service_allocation）、JOIN `Member`（取 email、display_name）；
group_by 鍵依參數切換。Member-only group_by 也走相同 JOIN，避免重複查詢路徑。

**理由**：單一路徑簡化測試與索引設計。

---

## 3. 月度配額計算

**決策**：定義 `current_month_start_utc(now)` helper
`datetime(now.year, now.month, 1, tzinfo=UTC)`；查詢
`SELECT COALESCE(SUM(total_tokens), 0) FROM call_records WHERE
allocation_id = ? AND started_at >= :month_start AND outcome = 'success'`。

**index 必要性**：既有 `idx_callrecord_allocation_time` (allocation_id,
started_at desc) 已存在，查詢即用此 index。**不需新 index**。

**理由**：簡單、可審計；不需新基建。

**已評估**：
- 物化 view / 預先 aggregate 表：YAGNI（10k 筆 SUM 在 ms 級）
- Redis counter：引入新 component；YAGNI

---

## 4. point-in-time pricing lookup

**決策**：給定 (provider, model, call_time) 找價目：

```sql
SELECT * FROM price_list
WHERE provider = ?
  AND model = ?
  AND effective_from <= ?
ORDER BY effective_from DESC
LIMIT 1
```

`record_call(success)` 寫入前查一次。**找不到 → cost_usd = NULL**（不擋呼叫；
聚合時視為 0）。

**理由**：
- 不在請求路徑上做 cache（規模小、簡單）
- 找不到不擋，避免「新模型沒設價就 503」

**已評估**：
- 用 view materialized「current price per model」：簡單但碰到 effective_from
  變更要 refresh，反而麻煩
- 把 cost_usd 留 NULL 之後背景補算：違反 point-in-time 精神（補算時的價目
  可能已變）

---

## 5. CSV streaming

**決策**：FastAPI `StreamingResponse` + Python `csv.writer` 寫入
`io.StringIO`；按 100 行 yield 一次。

**理由**：
- 90 天上限 + 預期 ≤ 10k 列；streaming 是過度設計，但 stdlib 寫法就帶
  「逐列 write」的天然能力，順手用即可
- `text/csv` MIME + UTF-8 BOM（讓 Excel 直接打開不亂碼）

**已評估**：
- Pandas to_csv：dep + 記憶體載入全部
- 自己拼字串：CSV quoting 容易做錯

---

## 6. CORS + cookie SameSite

**決策**：
- FastAPI `CORSMiddleware`，allow_origins 來自 `Settings.cors_origins`；
  allow_credentials=True 當清單非空
- session cookie SameSite：當 `cors_origins` 非空 → `SameSite=None`
  （瀏覽器規範：跨域帶 cookie 必為 None + Secure）+ `Secure=true`；
  否則維持 `SameSite=Lax`
- 文件記錄 dev 走 HTTP 時 `SameSite=None + Secure=false` 不被瀏覽器接受 —
  本機 dev 用同 origin（vite proxy）避開

**理由**：規範要求，無捷徑。

**已評估**：
- 允許所有 origin (`*`)：spec 已禁（FR-015 預設空）
- 走 BFF / reverse proxy 統一 origin：可行但增加部署複雜度

---

## 7. YAML schema

**決策**：

```yaml
# prices/azure-2026-05.yaml
effective_from: "2026-05-01T00:00:00Z"
source_note: "Azure OpenAI Service pricing — captured 2026-05-22"
prices:
  - provider: azure
    model: gpt-4o-mini
    input_per_1k_tokens_usd: 0.000150
    output_per_1k_tokens_usd: 0.000600
  - provider: azure
    model: gpt-4o
    input_per_1k_tokens_usd: 0.0025
    output_per_1k_tokens_usd: 0.010
```

**Loader 行為**：
- 解析 yaml → 對每一條 entry 嘗試 INSERT；違反 UNIQUE
  `(provider, model, effective_from)` → 整個載入回 `exit 1`（保證原子性）
- `created_by` 為 `cli:<user>`（從 `$USER` 取）

**理由**：人類可讀、git 可 diff、PR review 友善。

---

## 8. 配額拒絕的測試方式

**決策**：
- unit test 用 `quota_service.is_over_quota(...)` 驗 boundary（剛好相等、
  剛好小於）
- integration test 用 testcontainers Postgres，種入 N 筆 CallRecord +
  Allocation quota = N → 再呼叫 → 應拒

**理由**：兩層覆蓋；unit 給快速回饋、integration 給端到端信心。

---

## 9. NEEDS CLARIFICATION 解決狀態

無未決事項。spec.md 與 plan.md 中沒有 [NEEDS CLARIFICATION]。
