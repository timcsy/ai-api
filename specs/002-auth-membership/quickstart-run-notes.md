# Quickstart Run Notes — Phase 2 Auth & Membership

**Date**: 2026-05-22
**Environment**: 本機（macOS / Python 3.12.11 / uv 0.11.8）
**Server**: `uvicorn ai_api.main:app --port 8000`
**DB**: SQLite (本機 dev); Postgres testcontainers (CI integration)

## SC 檢核

| SC | 結果 | 證據 |
|---|---|---|
| **SC-001** Google SSO ≤ 30s | ✅ | 瀏覽器 `localhost:8000/auth/oidc/start` → 同意 → `/me` 回 `張頌宇 / timcsy@ms2.ccsh.tn.edu.tw / provider=google_oidc` |
| **SC-002** Local 邀請→登入 ≤ 5min | ✅ | quickstart §4 全程 < 10s（CLI 模擬） |
| **SC-003** 密碼 / secret 不洩漏 | ✅ | 75 tests 中無一筆掃描出 Azure key、cookie、OAuth secret |
| **SC-004** unknown email vs 密碼錯一致 | ✅ | contract `test_local_login_401_*` 兩情境同樣回 `invalid_credentials` |
| **SC-005** rate limit 6 次→429 + 15 min lock | ✅ | live: `for i in 1..6` 第 6 次回 429；正確密碼於鎖定期亦拒 |
| **SC-006** disable Member → session 失效 SLO ≤ 5s | ✅ | live 量測 **25 ms** |
| **SC-007** Phase 1 token migration 後不變 | ✅ | Phase 1 46/46 regression 綠；migration 0002 通過 |
| **SC-008** 多 provider，core 與 provider 數無關 | ✅ | google_oidc + local_password 兩個實作通過契約；第三個 provider 可加實作類別即可 |
| **SC-009** test commit 早於 impl commit | ✅ | `git log` 顯示 `88e37e5 (test)` < `6e1fefd (feat)` |

## Issues encountered & resolved during live verification

1. **state attribute usage post-delete** — 原本在 `await session.delete(state_row)` 後仍存取 `state_row.code_verifier`。改為先 cache 屬性再 delete。
2. **Clock skew vs Google id_token** — 本機 clock 比 Google 慢約 3 秒，`iat` 落在「未來」被 authlib 拒絕。改為 `claims.validate(leeway=60)`，容忍 60 秒時鐘偏移。

兩者都應該補成 experience.md 教訓（見下方建議）。

## Live commands sample

```bash
# Bootstrap admin controls
curl -X POST localhost:8000/admin/whitelist -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' -d '{"email":"<you>"}'
curl -X POST localhost:8000/admin/rules -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' -d '{"rule_type":"email_domain","pattern":"<your-workspace-domain>"}'

# Local password — admin creates + send invitation
CREATE=$(curl -X POST localhost:8000/admin/members -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' -d '{"email":"bob@partner.com","provider":"local_password","send_invitation":true}')
INVITE_URL=$(echo "$CREATE" | jq -r .invitation_url)
TOKEN=${INVITE_URL##*/auth/invitation/}
curl -c bob.cookies -X POST "$INVITE_URL" -H 'Content-Type: application/json' -d '{"password":"VerySecurePass2026"}'

# Live SSO requires a browser:
open "http://localhost:8000/auth/oidc/start?next=/me"

# Session disable SLO
curl -X PATCH localhost:8000/admin/members/<id> -H 'X-Admin-Token: local-dev-admin-only' -H 'Content-Type: application/json' -d '{"status":"disabled"}'
curl -b bob.cookies localhost:8000/me  # expect 401 within ≤ 5s
```

## 待人工驗證

- **K8s 部署 Phase 2**：image 已 build (`ghcr.io/timcsy/ai-api:sha-dd25af3`)，但叢集端 Helm 套用後跑一遍 quickstart 仍待做。
- **Local password 邀請流程的「48h expiry」邊界**：未跑時鐘前進測試；後續 chaos test 補。
