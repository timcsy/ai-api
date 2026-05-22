# Quickstart: 階段 3a — 用量觀測與費用計算

## 0. 先決條件

- Phase 1+2+2.5 quickstart 先決條件
- `.env` 加（可選）：
  ```
  CORS_ORIGINS='["http://localhost:5173"]'
  ```

## 1. 啟服務 + 載入價目

```bash
uv run alembic upgrade head      # 0004_usage_billing
uv run uvicorn ai_api.main:app --port 8000 &

# 載入價目
uv run python -m ai_api.cli.load_prices deploy/prices/azure-2026-05.yaml
# 預期：loaded 2 entries
```

## 2. 建分配 + 設配額 + 模擬呼叫（US3）

```bash
# 建分配
ALLOC=$(curl -s -X POST localhost:8000/admin/allocations \
  -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' \
  -d '{"subject":"alice@x.com","resource_model":"gpt-4o-mini"}')
ID=$(echo "$ALLOC" | jq -r .id)
TOKEN=$(echo "$ALLOC" | jq -r .token)

# 設配額 100 tokens / month
curl -X PATCH "localhost:8000/admin/allocations/$ID" \
  -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' \
  -d '{"quota_tokens_per_month":100}'

# 呼叫直到耗盡
curl -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
# 再幾次 → 第 N+1 次回 403 quota_exceeded
```

## 3. 查用量（US1, US2）

```bash
# Member 維度
curl -s "localhost:8000/admin/usage?group_by=member&from=2026-05-01T00:00:00Z&to=2026-06-01T00:00:00Z" \
  -H 'X-Admin-Token: local-dev-admin-only' | jq

# 單分配時間序列
curl -s "localhost:8000/admin/allocations/$ID/usage-timeseries?bucket=day&from=2026-05-01T00:00:00Z&to=2026-06-01T00:00:00Z" \
  -H 'X-Admin-Token: local-dev-admin-only' | jq

# CSV
curl -s "localhost:8000/admin/usage.csv?group_by=member&from=2026-05-01T00:00:00Z&to=2026-06-01T00:00:00Z" \
  -H 'X-Admin-Token: local-dev-admin-only' > usage.csv
```

## 4. Point-in-time 計費驗證（US5）

```bash
# 跑 1 次呼叫
... (call, note the cost_usd in usage)

# 載入「漲價」版本
uv run python -m ai_api.cli.load_prices deploy/prices/azure-2026-06-double.yaml

# 再跑 1 次（新 effective_from）
... (call → new cost_usd 為舊的 2 倍)

# 查 usage：兩筆 cost 不同 → point-in-time 正確
```

## 5. 服務型分配（US4）

```bash
curl -X PATCH "localhost:8000/admin/allocations/$ID" \
  -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' \
  -d '{"is_service_allocation":true,"quota_tokens_per_month":null}'

# 過濾只看服務型
curl -s "localhost:8000/admin/usage?group_by=allocation&service_only=true&from=...&to=..." \
  -H 'X-Admin-Token: local-dev-admin-only' | jq
```

## 6. CORS（US7）

```bash
# Set env then restart
export CORS_ORIGINS='["http://localhost:5173"]'

# Preflight
curl -i -X OPTIONS http://localhost:8000/admin/usage \
  -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: GET' \
  -H 'Access-Control-Request-Headers: X-Admin-Token'
# 預期：HTTP 200 + Access-Control-Allow-Origin: http://localhost:5173
#       + Access-Control-Allow-Credentials: true
```

## 7. SC 檢核

| SC | 步驟 |
|---|---|
| SC-001 | seed 10k CallRecord → time §3 by-member query |
| SC-002 | §2 配額測試 |
| SC-003 | §4 兩版價目對比 |
| SC-004 | seed 10k + §3 CSV export → time |
| SC-005 | §6 CORS preflight |
| SC-006 | 任何 §3 端點不帶 X-Admin-Token → 401 |
| SC-007 | `uv run pytest -q` → Phase 1+2+2.5 既有 97 + Phase 3a 新增全綠 |
| SC-008 | `git log -- tests/ src/` 顯示 test < impl commit |
