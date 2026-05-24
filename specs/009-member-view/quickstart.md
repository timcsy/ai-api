# Quickstart: 階段 3b.1 — Member View

## 0. 先決條件

- 3b.0 scaffold 已合進 main（PR #8 merged 為 `881b6d3`）
- 後端 dev server 跑著（uv run uvicorn）
- Phase 4 catalog YAML 已載入：
  ```bash
  uv run python -m ai_api.cli.load_models deploy/catalog/azure-2026-05.yaml
  ```

## 1. 本機建 member + allocation + seed call records

```bash
export ADMIN=local-dev-admin-only

# 1. Create member
curl -s -X POST http://localhost:8000/admin/members \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"alice@x.com","provider":"local_password","initial_password":"VerySafePass123","send_invitation":false}'

# 2. Get member id
MEMBER=$(curl -s "http://localhost:8000/admin/members?email=alice@x.com" \
  -H "X-Admin-Token: $ADMIN" | jq -r '.[0].id')

# 3. Create allocation
curl -s -X POST http://localhost:8000/admin/allocations \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d "{\"member_id\":\"$MEMBER\",\"resource_model\":\"gpt-4o-mini\"}"

# 4. (optional) Make a few proxy calls to populate /me/allocations/{id}/calls
TOKEN=...  # 從上一步 response 取
for i in 1 2 3; do
  curl -s -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}' \
    > /dev/null
done
```

## 2. 跑前端 (US1+US2)

```bash
cd frontend
npm install   # picks up new Radix deps
npm run dev   # http://localhost:5173

# 瀏覽器訪 http://localhost:5173
# → 跳 /login → 登入 alice@x.com / VerySafePass123
# → 跳 /dashboard
#   應看到 alice 的 email + 1 個 allocation 卡片
# → 點 allocation 卡片
#   應看到 quota progress + 呼叫表格
```

## 3. Catalog filter（US3）

```bash
# 訪 http://localhost:5173/catalog
# 應看到 9 個模型卡片（dall-e-3, gpt-4o, gpt-4o-mini, ...）

# 勾左側 sidebar:
#   capability: vision (CHECK)
#   capability: function-calling (CHECK)
#   cost_tier: low (RADIO)
# → 右側只剩 gpt-4o-mini 一張卡片
# → URL 變成 /catalog?capability=vision&capability=function-calling&cost_tier=low

# 複製 URL 開新分頁 → 同樣只顯示 gpt-4o-mini，sidebar 對應項目預勾
```

## 4. Catalog detail + copy curl（US4）

```bash
# 點 gpt-4o-mini 卡片 → /catalog/azure%2Fgpt-4o-mini
# 應看到 description、capabilities、example_request tabs

# 點「複製 curl」按鈕
# → toast 顯示「已複製到剪貼簿」
# → 貼到 terminal、換上 $TOKEN 與 $BASE，即可跑
```

## 5. Header nav + logout（US5）

```bash
# 任一頁 → 點 header 「Catalog」→ 跳 /catalog
# 點 header logout → cookie 清空 → 跳 /login
# 用 alice 重新登入 → 看到自己資料（cache 已清，無上一位殘留）
```

## 6. CI gates

```bash
# Backend
uv run pytest -q              # 196 (195 + 1 cursor pagination contract test)
uv run ruff check .
uv run mypy src/ai_api

# Frontend
cd frontend
npm run lint
npm run typecheck
npm test -- --run             # 21 prior + ≥ 10 new = ≥ 31
npm run build                 # bundle size 預期 +30~50KB (Radix elements)
```

## 7. SC 檢核

| SC | 步驟 |
|---|---|
| SC-001 | §2 登入後 dashboard 5 秒內出現 |
| SC-002 | §3 勾 filter 300ms 內更新 |
| SC-003 | §3 複製 URL 開新分頁同步勾選 |
| SC-004 | §3 vision+fn-call+low → 唯一命中 gpt-4o-mini |
| SC-005 | §4 點「複製 curl」測試環境用 mock clipboard 驗 |
| SC-006 | §2 cursor pagination 30 筆 → 20+10+按鈕消失 |
| SC-007 | §5 logout 重登別位 member 看不到舊資料 |
| SC-008 | §6 全綠 |
| SC-009 | `git log -- frontend/ src/` test < impl 順序 |
