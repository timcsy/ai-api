# Phase 0 Research: 階段 3c — Adaptive Quota Pool

---

## 1. 演算法：純函式分層

**決策**：把演算法切成兩層：

```python
# Pure function — no DB, easy to unit-test
def compute_rebalance(
    *,
    T: int,
    floor: int,
    reserved_quotas: list[int],          # service + locked 占用的 quota
    pool: list[tuple[str, int]],          # [(allocation_id, usage_last_month)]
) -> list[tuple[str, int]]:
    """Return [(allocation_id, new_quota)] satisfying conservation."""

# Side-effect function — DB transaction wrapping the pure compute
async def apply_rebalance(db, *, trigger: str) -> RebalanceLog:
    """Wrap compute_rebalance in a transaction. Rollback on any failure."""
```

**理由**：
- 純函式 → unit test 涵蓋所有 boundary（cold start、0 用量、四捨五入零頭）
- 副作用層只負責 DB I/O + 守恆 assertion；不重複數學邏輯
- 對 PR review 友善：「演算法對不對」與「DB 用得對不對」分開看

**已評估**：
- 一個大 method 全做：難測；test 必須拖完整 Postgres
- 多個 method 分散：演算法散落多處，難追

---

## 2. 守恆零頭處理（rounding）

**決策**：對 `D - floor·N` 按 usage 比例分時，每人 `int(...)` 向下取整；
最後零頭 `D_remaining = D - Σ q_distributed` 加到「上月用量最高」的
allocation（如有並列，取 allocation_id 字典序最大）。

```python
shares = [int(distributable * (u / total_u)) for u in usages]
leftover = distributable - sum(shares)
# 加到 max usage（並列取 id 大者，保確定性）
target = max(range(len(usages)), key=lambda i: (usages[i], pool[i][0]))
shares[target] += leftover
q = [floor + s for s in shares]
assert sum(q) + sum(reserved_quotas) == T
```

**理由**：
- 馬太效應的延伸（多用者本就拿較多，給零頭最自然）
- 確定性（同樣輸入永遠同樣輸出，方便測試與審計）

**已評估**：
- 隨機分配零頭：不可重現，難審計
- 給最小 usage：違反馬太精神
- 平均分散到所有人：可能再產生小數，無限循環

---

## 3. Transaction 範圍

**決策**：整個 `apply_rebalance` 包在 `async with db.begin():`；任何例外
（演算法、DB constraint、守恆 assertion）→ 自動 rollback。

**步驟順序（單一交易內）**：

1. SELECT 全部 active allocations（FOR UPDATE 否？見 §4）
2. 計算 reserved = sum of service/locked quotas
3. 構造 pool list + 計算上月用量（subquery aggregation）
4. 呼叫 `compute_rebalance(...)` 純函式
5. 守恆 assert（compute 內部已 assert，這層雙保險）
6. UPDATE 每個池內 allocation 的 quota
7. INSERT RebalanceLog（cron 觸發時 UNIQUE constraint 可能丟錯 → 接住即 no-op）
8. COMMIT

**理由**：所有失敗路徑都自動 rollback，無需手動清理。

---

## 4. 是否 FOR UPDATE lock allocations？

**決策**：**不**用 FOR UPDATE。改用 optimistic 策略：

- SELECT 取得 allocation 與其當下 `quota_locked`、`is_service_allocation` 值
- UPDATE 時 WHERE 條件加 `quota_locked=false AND is_service_allocation=false`
- 若 admin 在這幾秒內手動把某 allocation 改成 locked，UPDATE rowcount 會少 1
- 我們只 assert「rebalance 後總和 = T」— 若 admin 改動讓總和對不上 → assert
  fail → rollback → 下次 rebalance 重來

**理由**：
- 避免長時間 lock 整批 allocation 阻塞線上 proxy 呼叫
- rebalance 對 race 容錯（rollback + retry）
- spec 沒承諾「rebalance 期間不允許 admin 改動」

**已評估**：
- FOR UPDATE：阻塞 proxy；對代理路徑的延遲不可預期
- Advisory lock：複雜度增加

---

## 5. CronJob 同月去重

**決策**：在 `rebalance_log` 加 partial UNIQUE：
```sql
CREATE UNIQUE INDEX uq_rebalance_log_cron_month
ON rebalance_log (period_yyyymm)
WHERE triggered_by = 'cron';
```

當 cron 觸發第二次（同月）時，INSERT 違反 UNIQUE → 接住 `IntegrityError` →
回傳「already done, skipping」訊息、無 audit 噪音。

**理由**：DB 約束強過程式檢查；多副本 race 也安全。

**已評估**：
- 程式內查「本月有沒有 cron rebalance」：race condition
- 用 advisory lock：複雜

**SQLite 注意**：SQLite 不支援 partial UNIQUE index；本機 dev 上用普通
UNIQUE `(period_yyyymm, triggered_by)` 替代（手動觸發會用 `admin:<id>` 之類
不同字串，自然不撞）。

---

## 6. 上月用量計算

**決策**：在 SQL 直接 aggregate（不 ORM lazy load）：

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
```

`prev_month_start` 用 helper：
```python
def previous_month_range_utc(now):
    this_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 1:
        prev_start = datetime(now.year - 1, 12, 1, tzinfo=UTC)
    else:
        prev_start = datetime(now.year, now.month - 1, 1, tzinfo=UTC)
    return prev_start, this_start
```

**理由**：直接 SQL group by，效能可預期；避免 N+1。

---

## 7. RebalanceLog.details 結構

**決策**：

```json
{
  "allocations": [
    {"id": "01...", "before": 1000, "after": 1500, "usage": 5000, "reason": "ratio"},
    {"id": "02...", "before": 1000, "after": 100, "usage": 0, "reason": "floor"},
    {"id": "03...", "before": 800, "after": 800, "usage": 999, "reason": "locked"}
  ],
  "reserved": {"service": 500, "locked": 800},
  "leftover_target": "01..."
}
```

存 `jsonb`（Postgres）/ `JSON`（SQLite via SQLAlchemy JSON column）。

**理由**：未來「為什麼我這月變少」可一鍵查清楚；reason 欄位區分
ratio / floor / locked / service / first_round 等情況。

---

## 8. 手動觸發的 `triggered_by` 命名

**決策**：
- cron：固定字串 `"cron"`
- API 手動觸發：`"admin:<token-id-or-name>"`
- 未來若由登入 admin Member 觸發：`"member:<member-id>"`

當前 admin 用 `X-Admin-Token`，token 沒有具體 ID — 用 `"admin:bootstrap"`
即可（與 audit 既有 `actor_id` 同層）。

---

## 9. NEEDS CLARIFICATION

無未決。
