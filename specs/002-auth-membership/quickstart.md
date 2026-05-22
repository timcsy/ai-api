# Quickstart: 階段 2 — 身份驗證與成員管理

驗證流程涵蓋 spec 五個 user story。所有指令 cwd 為 repo root。

## 0. 先決條件

- Phase 1 quickstart 的所有先決條件
- Google Cloud Console OAuth 2.0 Client ID（type: Web application）
- 在 `.env` 新增：

```bash
BASE_URL=http://localhost:8000
COOKIE_SECURE=false            # local dev only; prod=true
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_DISCOVERY_URL=https://accounts.google.com/.well-known/openid-configuration
```

並到 Google Console 把 Authorized redirect URI 設為
`http://localhost:8000/auth/oidc/callback`。

## 1. Migration + 啟服務

```bash
uv sync
uv run alembic upgrade head      # 跑 0002_auth_membership.py
uv run uvicorn ai_api.main:app --reload --port 8000
```

驗證健康：`curl localhost:8000/healthz` → `{"status":"ok"}`

## 2. US3：管理員管控

```bash
# 加白名單
curl -X POST localhost:8000/admin/whitelist \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","note":"alpha tester"}'

# 加自動註冊規則
curl -X POST localhost:8000/admin/rules \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"rule_type":"email_domain","pattern":"example.com"}'

# 加來源限制（local dev: allow loopback + LAN）
curl -X POST localhost:8000/admin/source-restrictions \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"cidr":"127.0.0.0/8"}'
curl -X POST localhost:8000/admin/source-restrictions \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"cidr":"192.168.0.0/16"}'
```

## 3. US1：Google SSO

在瀏覽器開：`http://localhost:8000/auth/oidc/start?next=/me`

→ 重新導向至 Google → 同意 → 回到 `/auth/oidc/callback` → 進入 `/me`。

驗證：
```bash
# /me 回傳 Member
curl --cookie cookies.txt localhost:8000/me
# /me/allocations 為空（這是新註冊 Member）
curl --cookie cookies.txt localhost:8000/me/allocations
```

## 4. US2：Local Password + 邀請

```bash
# 管理員建立 Local Member（送邀請連結）
CREATE=$(curl -s -X POST localhost:8000/admin/members \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@partner.com","provider":"local_password","send_invitation":true}')
echo "$CREATE"
INVITE_URL=$(echo "$CREATE" | python3 -c "import sys,json;print(json.load(sys.stdin)['invitation_url'])")
echo "Send to user: $INVITE_URL"

# 使用者在邀請頁設密碼（模擬）
TOKEN=$(echo "$INVITE_URL" | sed 's|.*/auth/invitation/||')
curl -c bob.cookies -X POST "localhost:8000/auth/invitation/$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"superSecure2026!"}'

# Bob 用 cookie 訪問 /me
curl -b bob.cookies localhost:8000/me

# 之後可登出後改用密碼登入
curl -b bob.cookies -X POST localhost:8000/auth/logout
curl -c bob.cookies -X POST localhost:8000/auth/local/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@partner.com","password":"superSecure2026!"}'
```

驗證 rate limit：
```bash
for i in $(seq 1 6); do
  curl -s -o /dev/null -w "attempt $i: HTTP %{http_code}\n" \
    -X POST localhost:8000/auth/local/login \
    -H "Content-Type: application/json" \
    -d '{"email":"bob@partner.com","password":"wrong"}'
done
# 第 6 次預期 429
```

## 5. US4：成員自助

```bash
# 管理員幫 Bob 建立分配
curl -X POST localhost:8000/admin/allocations \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"member_id":"<bob_member_id>","resource_model":"gpt-5.4-mini"}'

# Bob 列自己的分配
curl -b bob.cookies localhost:8000/me/allocations
```

## 6. US5：subject 遷移驗證

> 在執行 `alembic upgrade head` **之前**先確認 DB 內有 Phase 1 留下的
> 字串 subject；migration 後該字串應被建立為 `external` 型 Member 並
> 反映在 `Allocation.member_id` 中。

```bash
# Phase 1 token 仍可呼叫
curl -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <phase1_token>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.4-mini","messages":[{"role":"user","content":"ping"}]}'
```

## 7. Session 撤銷 SLO（呼應原則 3）

```bash
# 管理員停用 Bob
curl -X PATCH localhost:8000/admin/members/<bob_member_id> \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{"status":"disabled"}'

# Bob 在 5 秒內呼叫 /me 應拿到 401
sleep 3
curl -b bob.cookies -o /tmp/r.json -w "HTTP %{http_code}\n" localhost:8000/me
```

## 8. SC 檢核表

| SC | 如何驗證 |
|---|---|
| SC-001 | 步驟 3 全程 < 30s |
| SC-002 | 步驟 4 從 admin create 到 login success < 5min |
| SC-003 | grep `$GOOGLE_OAUTH_CLIENT_SECRET`、`superSecure2026!`、cookie 值於回應/log = 0 |
| SC-004 | 對 50 對「email 不存在 vs 密碼錯誤」回應做 reviewer 檢視 |
| SC-005 | 步驟 4 rate limit 區塊 |
| SC-006 | 步驟 7 |
| SC-007 | 步驟 6 |
| SC-008 | 至少 `local` 與 `google_oidc` 兩個 provider 各自通過 contract tests |
| SC-009 | `git log --follow tests/ src/` 顯示測試 commit 早於對應實作 commit |
