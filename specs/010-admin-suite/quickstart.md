# Quickstart: 階段 3b.2 — Admin Suite

## 0. 先決條件

- 3b.1 main 已合（PR #9 merged）
- 後端 dev server 跑著
- `ADMIN_BOOTSTRAP_TOKEN=local-dev-admin-only` 已設

## 1. 建表 + bootstrap admin

```bash
# Run migration 0007
uv run alembic upgrade head

# Start backend
uv run uvicorn ai_api.main:app --port 8000 &

# Bootstrap: create alice and promote
export ADMIN=local-dev-admin-only
curl -X POST http://localhost:8000/admin/members \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"alice@x.com","provider":"local_password","initial_password":"VerySafePass123","send_invitation":false}'

ALICE=$(curl -s "http://localhost:8000/admin/members?email=alice@x.com" \
  -H "X-Admin-Token: $ADMIN" | jq -r '.[0].id')

curl -X PATCH http://localhost:8000/admin/members/$ALICE \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d '{"is_admin": true}'
# → {"id":"...","email":"alice@x.com","is_admin":true,...}
```

## 2. 前端 dev server

```bash
cd frontend
npm install   # picks up react-hook-form + zod + 8 new Radix primitives
npm run dev
```

## 3. Bootstrap 驗證（US1）

```
1. 訪 http://localhost:5173
2. 登入 alice@x.com / VerySafePass123
3. /me 應該回 is_admin: true
4. AppShell header 應該看到「Admin」link（Dashboard / Catalog / Admin）
```

## 4. Admin Members 視圖（US3）

```
1. 點 header「Admin」→ 跳 /admin/members
2. 表格顯示 alice
3. 點「新建 Member」→ dialog 開
   - email: bob@x.com
   - provider: local_password
   - initial_password: VerySafePass123
4. submit → toast「Member 已建立」→ 表格多一筆 bob
5. 點 bob row 的 dropdown → 「升 admin」→ 確認
6. bob is_admin badge 出現
```

## 5. Admin Allocations 視圖（US4）

```
1. 訪 /admin/allocations
2. 點「新建 Allocation」
   - member: alice
   - model: gpt-4o-mini
   - quota: 10000
3. submit → token dialog 顯示一次性 token
4. 點「我已複製」→ token 從 UI state 清除
5. 表格顯示新 allocation
6. 點 quota cell 改成 20000 → save → 表格更新
7. 點「撤回」→ 確認 → status badge 變 revoked
```

## 6. Admin Usage 視圖（US5）

```
1. 訪 /admin/usage
2. 預設 group_by=member、過去 30 天
3. （需先有 call records；可手動跑幾次 proxy call）
4. 切 group_by=model → 表格重新加載
5. 點「下載 CSV」→ 瀏覽器下載 usage-2026-04-24-2026-05-24.csv
6. 開 CSV 確認內容對應 query filter
```

## 7. Admin Quota Pool 視圖（US6）

```
# 先設定 pool
export POOL_TOTAL_TOKENS_PER_MONTH=10000
export POOL_FLOOR_PER_ALLOCATION=500
# 重啟 backend

1. 訪 /admin/quota-pool
2. 狀態卡顯示 T=10000, distributable=...
3. 點「手動 rebalance」→ 確認 dialog
4. toast 顯示「rebalance done: scanned=N, changed=M」
5. 列表多一筆新 RebalanceLog
6. 點 row → drawer 顯示 per-allocation before/after
```

## 8. Last-admin guard（SC-007）

```
1. 確保 alice 是唯一 admin（其他 member is_admin=false）
2. 在 /admin/members 對 alice 點 dropdown → 「降 admin」
3. UI 應該：
   - 顯示警告 dialog「您是唯一 admin，無法降自己」
   - OR 嘗試後 toast「至少需保留一個 admin」
4. DB 確認 alice.is_admin 仍 true
```

## 9. 非 admin member 訪問（SC-003）

```
1. logout
2. 用 bob 登入（bob 此時 is_admin=true 因 §4 升過；先 demote 回來：
   curl -X PATCH /admin/members/$BOB_ID ... '{"is_admin": false}'）
3. bob /me 應顯示 is_admin=false
4. bob header 沒有 Admin link
5. bob 直接訪 /admin/members
   → 顯示內嵌「無權限查看」+ 回首頁 button
   → URL 仍是 /admin/members（不 redirect）
```

## 10. CI gates

```bash
# Backend
uv run pytest -q             # ≥ 199 + 新 ≥ 8 = ≥ 207
uv run ruff check .
uv run mypy src/ai_api

# Frontend
cd frontend
npm run lint
npm run typecheck
npm test -- --run            # ≥ 43 + 新 ≥ 25 = ≥ 68
npm run build                # bundle ≤ ~700KB gzipped
```

## 11. SC 檢核

| SC | 步驟 |
|---|---|
| SC-001 | §1 bootstrap → §3 alice 訪 /admin OK |
| SC-002 | §10 backend 全綠 + 274 處 admin_headers 測試零修改 |
| SC-003 | §9 bob 訪 admin 內嵌「無權限」 |
| SC-004 | §3-§7 五個視圖 manual 驗證 |
| SC-005 | §6 CSV 下載 |
| SC-006 | §7 手動 rebalance 後狀態 + log 更新 |
| SC-007 | §8 唯一 admin 降不下來 |
| SC-008 | §10 backend ≥ 207 |
| SC-009 | §10 frontend ≥ 68 |
| SC-010 | git log --oneline -- frontend/ src/ tests/ 順序 |
| SC-011 | §10 build 出來 gzipped 確認 |
