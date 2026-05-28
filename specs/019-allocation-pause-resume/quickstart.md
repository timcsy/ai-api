# Quickstart: 憑證暫停 / 恢復

## 後端驗證（admin token）

```bash
TOKEN=$(grep '^ADMIN_BOOTSTRAP_TOKEN=' .env | cut -d= -f2-)
AID=<某把 active allocation 的 id>

# 暫停
curl -s -X POST localhost:47821/admin/allocations/$AID/pause -H "X-Admin-Token: $TOKEN" | python3 -m json.tool
# 預期：status = "paused"

# 暫停中：用該憑證的原 token 呼叫 proxy → 403 allocation_paused
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:47821/v1/chat/completions \
  -H "Authorization: Bearer aiapi_原token" -H 'Content-Type: application/json' \
  -d '{"model":"azure/gpt-5.4-mini","messages":[{"role":"user","content":"hi"}]}'
# 預期：403

# 恢復
curl -s -X POST localhost:47821/admin/allocations/$AID/resume -H "X-Admin-Token: $TOKEN" | python3 -m json.tool
# 預期：status = "active"

# 恢復後：同一把原 token 又能用
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:47821/v1/chat/completions \
  -H "Authorization: Bearer aiapi_原token" ... 
# 預期：200（上游正常時）

# 狀態機：對已 paused 再 pause → 409；對 active resume → 409
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:47821/admin/allocations/$AID/resume -H "X-Admin-Token: $TOKEN"
```

## 測試

```bash
uv run pytest tests/contract/test_allocation_pause_resume.py tests/integration/test_proxy_paused.py -v
cd frontend && npm test -- --run src/__tests__/admin-allocations-pause.test.tsx
# 全套
uv run pytest -q && cd frontend && npx tsc --noEmit && npm test -- --run
uv run ruff check .
# 確認無新 migration
DATABASE_URL="sqlite+aiosqlite:////tmp/p019.db" uv run alembic upgrade head   # 仍止於 0012
```

## UI 驗證

1. admin → 觀測 → 分配（或成員詳情）→ 對一把 active 憑證按「暫停」→ 狀態變「paused」、鈕變「恢復」
2. 用該憑證呼叫 API → 被擋（403 allocation_paused）
3. 按「恢復」→ 同一把 token 又能呼叫
4. 確認「暫停」與「撤回」文案/行為可區分（暫停可逆、保留 token；撤回終局）

## 驗收對應
- US1（暫停）→ pause 端點 + proxy 403 + token/配額不變測試
- US2（恢復）→ resume 端點 + 原 token 成功測試
- US3（狀態機）→ 非法轉移 409 測試
