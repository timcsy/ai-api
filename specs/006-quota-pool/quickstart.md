# Quickstart: 階段 3c — Adaptive Quota Pool

## 0. 先決條件

- Phase 3a 已上線（CallRecord.total_tokens 已累積；Allocation 有
  `quota_tokens_per_month` 與 `is_service_allocation`）
- 在 `.env` 設定：

```
POOL_TOTAL_TOKENS_PER_MONTH=1000
POOL_FLOOR_PER_ALLOCATION=100
```

## 1. 啟服務 + migration

```bash
uv run alembic upgrade head      # 0005_quota_pool
uv run uvicorn ai_api.main:app --port 8000 &
```

## 2. 看池狀態（US6）

```bash
curl -s localhost:8000/admin/quota-pool/status \
  -H 'X-Admin-Token: local-dev-admin-only' | jq
```

預期：
```json
{
  "total_T": 1000,
  "reserved": {"service": 0, "locked": 0},
  "distributable": 1000,
  "pool_member_count": 0,   // 還沒人在池內
  "floor": 100,
  "settings": {"enabled": true},
  "last_rebalance_at": null
}
```

## 3. 建 3 個 allocation + 模擬上月用量（US1）

```bash
# 建 3 個非服務型 allocation
for u in alice bob carol; do
  curl -s -X POST localhost:8000/admin/allocations \
    -H 'X-Admin-Token: local-dev-admin-only' \
    -H 'Content-Type: application/json' \
    -d "{\"subject\":\"$u@x.com\",\"resource_model\":\"gpt-4o-mini\"}"
done

# 手動 seed CallRecord 模擬上月用量比 5:3:2
# （實作層由真實呼叫累積；測試用 seed 腳本）
```

## 4. 手動觸發 rebalance（US5）

```bash
curl -s -X POST localhost:8000/admin/quota-pool/rebalance \
  -H 'X-Admin-Token: local-dev-admin-only' | jq
```

預期回 RebalanceLog 摘要 + 三人 quota 變為 450/310/240：

```bash
curl -s "localhost:8000/admin/allocations?status=active" \
  -H 'X-Admin-Token: local-dev-admin-only' | jq '.[] | {subject_snapshot, quota_tokens_per_month}'
```

驗證守恆：`Σ quota == 1000`。

## 5. 服務型與 locked 豁免（US3）

```bash
# 把 alice 標為服務型 + quota 固定 500
ALICE_ID=$(curl -s -H 'X-Admin-Token: local-dev-admin-only' \
  "localhost:8000/admin/allocations?subject=alice@x.com" | jq -r '.[0].id')
curl -s -X PATCH "localhost:8000/admin/allocations/$ALICE_ID" \
  -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' \
  -d '{"is_service_allocation":true,"quota_tokens_per_month":500}'

# 把 bob 標 locked + quota 200
BOB_ID=...
curl -s -X PATCH "localhost:8000/admin/allocations/$BOB_ID" \
  -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' \
  -d '{"quota_locked":true,"quota_tokens_per_month":200}'

# rebalance：池內只剩 carol
curl -s -X POST localhost:8000/admin/quota-pool/rebalance \
  -H 'X-Admin-Token: local-dev-admin-only' | jq

# 驗證：alice=500, bob=200, carol=300 (T=1000)
```

## 6. CronJob 同月去重（US2/US5 重疊）

```bash
# 模擬 cron 觸發兩次（透過 CLI）
uv run python -m ai_api.cli.run_rebalance
uv run python -m ai_api.cli.run_rebalance
# 第二次應該回 "already done for this month"
```

## 7. Rollback 驗證（US2）— 故意失敗

```bash
# 故意把 T 設為比 service+locked 更小，rebalance 應失敗
export POOL_TOTAL_TOKENS_PER_MONTH=100   # 比 alice(500)+bob(200) 還少
# 重啟服務
# 觸發 rebalance → 預期 409 pool_exhausted_by_reserved
curl -s -X POST localhost:8000/admin/quota-pool/rebalance \
  -H 'X-Admin-Token: local-dev-admin-only' | jq
# 驗證 quota 都沒動（取 §5 的最終結果比對）
```

## 8. SC 檢核

| SC | 對應步驟 |
|---|---|
| SC-001 | §4 守恆驗證（450+310+240=1000） |
| SC-002 | §5 service/locked 豁免 |
| SC-003 | §7 rollback 驗證 |
| SC-004 | §7 後檢查 `rebalance_log` 沒有失敗紀錄；只有 audit 有 `rebalance_failed` |
| SC-005 | §6 cron 去重 |
| SC-006 | §4 後立刻跑 `/v1/chat/completions` 看 quota 用新值 |
| SC-007 | `uv run pytest -q` 既有 140 全綠 |
| SC-008 | `git log -- tests/ src/` 順序 |
