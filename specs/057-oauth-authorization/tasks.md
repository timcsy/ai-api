# Tasks: 第一方網頁 app 的 OAuth（Authorization Code + PKCE）

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Status**: back-filled — 程式碼先建並測試,任務為事後記錄;`[x]` = 已完成並驗證。

## Phase 1 — 資料層
- [x] T001 新表 model `oauth_authorizations`（`models/oauth_authorization.py`：`OAuthAuthorization` + `OAuthAuthStatus`）
- [x] T002 匯出 model（`models/__init__.py`）
- [x] T003 migration `0024_oauth_authorizations`（建表 + `code`/`member`/`status,expires` index）;fresh SQLite `alembic upgrade head` 驗過
- [x] T004 config `oauth_redirect_allowlist`（`config.py`,env `OAUTH_REDIRECT_ALLOWLIST`）

## Phase 2 — 服務層（安全核心）
- [x] T005 `OAuthService.create_consent`：驗 `redirect_uri` 白名單(fail-closed) + PKCE method=S256 + challenge 格式;建 pending row（`member_id`=登入成員）
- [x] T006 `OAuthService.get_pending`：擁有者 + pending + 未過期
- [x] T007 `OAuthService.approve`：驗 allocation 為本人所有 → 發一次性 `code`、status=approved、expires=now+120s（**不建金鑰**）
- [x] T008 `OAuthService.deny`
- [x] T009 `OAuthService.exchange`：查 code → status=approved + 未過期 + `redirect_uri` 相符 + **PKCE S256 驗證**（`hmac.compare_digest`）→ `create_member_credential` 發金鑰 → status=consumed（單次）
- [x] T010 `validate_redirect_uri` / `verify_pkce_s256` 純函式（stdlib）

## Phase 3 — API 層
- [x] T011 `POST /me/oauth/consent`（session + CSRF）→ 回 `{id, client_name, redirect_uri, allocations}`
- [x] T012 `GET /me/oauth/{id}`、`POST /me/oauth/{id}/approve`、`POST /me/oauth/{id}/deny`（session + CSRF）
- [x] T013 `POST /oauth/token`（公開）→ `{access_token, token_type, credential_id, scope}`;`grant_type != authorization_code` → 400
- [x] T014 註冊 router（`main.py`）

## Phase 4 — 前端
- [x] T015 同意頁 `routes/oauth-authorize.tsx`：讀 URL 參數 → consent → 勾 allocation → approve → `window.location` 導回 `redirect_uri?code&state`;deny 導回 `error=access_denied`;`redirect_uri` 被拒顯示錯誤
- [x] T016 註冊 `/oauth/authorize` route（`App.tsx`）
- [x] T017 可見性：OAuth 金鑰以 `client_name` 顯示於既有成員金鑰清單(沿用,無新頁)

## Phase 5 — 部署設定
- [x] T018 nginx `location /oauth/token → backend`（`/oauth/authorize` 走 SPA、`/me/oauth/*` 由 `/me` 涵蓋）
- [x] T019 helm：`OAUTH_REDIRECT_ALLOWLIST` env（`deployment.yaml`）+ `oauthRedirectAllowlist` value（預設空）

## Phase 6 — 測試
- [x] T020 後端 contract `test_oauth_flow.py`（7 條）：全流程 + 單次碼 + allowlist 拒 + PKCE 不符 + redirect 綁定 + deny + 需登入 + unsupported grant → **全綠**
- [x] T021 前端 `oauth-authorize.test.tsx`（2 條）：同意頁渲染 + approve 送出正確 allocation_ids + 導回帶 code/state;redirect_uri 被拒顯示錯誤 → **全綠**
- [x] T022 `conftest.py` 加 `OAUTH_REDIRECT_ALLOWLIST` 測試環境

## Phase 6b — 管理員可編輯白名單（維護者追加,FR-010）
- [x] T024 `oauth_config` 單例 model（CHECK id=1）+ migration `0025`
- [x] T025 `get_oauth_config` lazy-seed from env;`validate_redirect_uri(uri, prefixes)` 改吃 DB 清單;`create_consent` 讀 DB config
- [x] T026 admin API `GET/PUT /admin/oauth/config`（`api/admin_oauth.py`,require_admin_token）
- [x] T027 後台頁 `/admin/oauth`「應用授權」（textarea 一行一前綴 + 儲存）+ nav + route
- [x] T028 測試：admin 編輯即時生效 + DB 覆蓋 env + 需 admin（`test_oauth_flow.py` +2）;前端 `admin-oauth.test.tsx`

## Phase 7 — 上線（auth review gate）
- [ ] T023 **維護者 review**（auth 功能上 production 前必停）→ 設每個部署的 `oauthRedirectAllowlist` → 部署 ccsh（暖快取後 helm）→ 真機驗一條完整流程
