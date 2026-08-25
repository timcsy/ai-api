# Implementation Plan: 第一方網頁 app 的 OAuth（Authorization Code + PKCE）

**Branch**: `057-oauth-authorization` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

## Technical Context

- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）;FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2;前端 shadcn/ui + TanStack Query。**不新增套件**（PKCE 用 stdlib `hashlib`/`hmac`/`base64`/`secrets`）。
- **新 migration `0024`**：新表 `oauth_authorizations`（純加表、無 mutual FK）。
- 發出的金鑰沿用既有 `Credential` + `CredentialAllocation`（`create_member_credential`）;計費/撤回/範圍全部複用。

## 核心決策（spec Assumptions 已凍結）

- **一條 Authorization Code + PKCE 流程**,無 `client_secret`,同時服務「有後端」與「純 SPA」網頁 app。
- **結構上是 device flow 的導轉版**：consent(登入+勾 allocation)→ 發一次性 code → `/oauth/token` 換 `Credential`。核心發鑰邏輯與 device flow 同用 `create_member_credential`。
- **安全三支柱**：PKCE(S256)、`redirect_uri` 前綴白名單(fail-closed)、code 一次性+短 TTL+綁 redirect_uri/challenge。核准只發 code、金鑰延到交換時建（未用的 code 不會留下活金鑰）。

## 需改動的點

```
backend/
  src/ai_api/config.py                         # + oauth_redirect_allowlist (OAUTH_REDIRECT_ALLOWLIST)
  src/ai_api/models/oauth_authorization.py     # NEW 表 model（OAuthAuthorization + OAuthAuthStatus）
  src/ai_api/models/__init__.py                # 匯出
  alembic/versions/0024_oauth_authorizations.py# NEW migration（建表 + index）
  src/ai_api/services/oauth.py                 # NEW OAuthService：consent/approve/deny/exchange + PKCE S256 驗證 + redirect 白名單
  src/ai_api/api/oauth.py                      # NEW router：/me/oauth/*（session）+ /oauth/token（公開）
  src/ai_api/main.py                           # include oauth.router
deploy/
  deploy/nginx/default.conf.template           # + location /oauth/token → backend（/oauth/authorize 走 SPA、/me/oauth/* 由 /me 涵蓋）
  deploy/helm/ai-api/templates/deployment.yaml # + OAUTH_REDIRECT_ALLOWLIST env
  deploy/helm/ai-api/values.yaml               # + oauthRedirectAllowlist（預設空 = fail-closed）
frontend/
  frontend/src/routes/oauth-authorize.tsx      # NEW 同意頁（讀 URL 參數→consent→勾 allocation→approve→導回）
  frontend/src/App.tsx                         # + /oauth/authorize route
tests/
  tests/conftest.py                            # + OAUTH_REDIRECT_ALLOWLIST 測試環境
  tests/contract/test_oauth_flow.py            # 全流程 + 安全檢查（allowlist/PKCE/單次/redirect 綁定/deny/需登入）
  frontend/src/__tests__/oauth-authorize.test.tsx # 同意頁渲染 + approve 送出 + redirect_uri 被拒
```

## 資料模型

`oauth_authorizations`（單一 rows／每次授權嘗試,短命單次）：`id`、`client_name`、`redirect_uri`、`state`、`scope`、`code_challenge`、`code_challenge_method`、`member_id`(consent 由登入成員建,故已知)、`status`(pending/approved/consumed/denied/expired)、`allocation_ids`(JSON,核准時設)、`code`(unique,核准時設)、`credential_id`(交換時設)、`created_at`/`expires_at`(consent 視窗→核准後改為 code TTL)/`approved_at`/`consumed_at`。無 mutual FK（避開拓撲排序陷阱）。

## 路由/部署注意

- 前端 nginx：`/oauth/token` → backend;`/oauth/authorize` 是瀏覽器導覽 → 走 SPA fallback;`/me/oauth/*` 已被 `location /me` 涵蓋。**改 nginx template = 要重建前端 image。**
- `OAUTH_REDIRECT_ALLOWLIST` 每個部署自行設成第一方 app 的 callback origin;預設空 = 拒。

## 守則
- **auth 功能 → 上 production 前停下讓維護者 review**（見 [[feedback_workflow]]）。
- 零回歸;PKCE/allowlist/單次碼皆有測試守門。
