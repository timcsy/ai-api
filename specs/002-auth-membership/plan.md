# Implementation Plan: 階段 2 — 身份驗證與成員管理 (Auth & Membership)

**Branch**: `002-auth-membership` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-auth-membership/spec.md`

## Summary

延續 Phase 1 的 FastAPI + SQLAlchemy 2 + Postgres 技術線，新增：

- **`AuthProvider` 抽象**：`authenticate(credentials) → AuthResult`，首發兩
  個實作 `google_oidc` 與 `local_password`。
- **Google OIDC**：用 [`authlib`](https://github.com/lepture/authlib)
  Starlette 整合，Authorization Code + PKCE，state/nonce 由 server session
  保管。
- **Local password**：`argon2-cffi` 雜湊；invitation token = 隨機 32B
  URL-safe base64，SHA-256 指紋存 DB；rate limit 以 DB 表計數（per-email
  時間窗）。
- **Session**：server-side `Session` 表 + HTTP-only / Secure / SameSite=Lax
  cookie；每次請求驗證 session（同 Phase 1「每次查 DB」策略，呼應原則 3
  即時撤回）。
- **Member 升格**：Phase 1 `Allocation.subject` 字串以 Alembic data migration
  對應到 `external` 型 Member；保留 `subject_snapshot` 欄位作為審計快照。
- **管理員管控**：白名單／自動註冊規則／來源限制 三張 CRUD 表，變更
  立即生效（查 DB，不快取）。

## Technical Context

**Language/Version**: Python 3.11+（同 Phase 1）
**Primary Dependencies**（新增於 Phase 1 之上）：
- `authlib>=1.3.0`（Google OIDC client，Starlette 整合）
- `argon2-cffi>=23.1.0`（Argon2id 密碼雜湊）
- `itsdangerous>=2.2.0`（state/nonce/邀請 token 簽章與序列化）
- `email-validator>=2.2.0`（email 標準化與驗證）
- 既有：FastAPI、SQLAlchemy 2 async、Alembic、Pydantic v2、httpx
**Storage**: PostgreSQL（含新表：members、sessions、email_whitelist、
  auto_register_rules、source_restrictions、invitation_tokens、
  password_attempts、auth_audit_log）
**Testing**: pytest、pytest-asyncio、httpx、schemathesis、
  testcontainers-postgres、`respx`（mock Google OIDC discovery / token endpoint）
**Target Platform**: 同 Phase 1（Linux container，K8s 部署）
**Project Type**: web-service（同 Phase 1，繼續單一專案結構）
**Performance Goals**:
- Google OIDC 完整 round-trip ≤ 5 秒（含 Google 端延遲）
- 登入 rate limit 第 6 次回 429 → 觀察 ≤ 200ms
- Member 停用 → active session 失效 SLO ≤ 5 秒（與原則 3 一致）
**Constraints**:
- 密碼 / OAuth secret / session token 一律走 redaction filter（沿用 Phase 1
  `observability/logging.py`，擴充 secrets 清單）
- 一個 email 對應一個 Member（DB UNIQUE on lower(email)）
- 既有 Phase 1 token 與行為**不可破壞**（migration zero-downtime）
**Scale/Scope**: 階段 2 預期 ≤ 200 Member、≤ 500 active session、≤ 50
  /login 請求/分鐘；性能驗證為輔，正確性與安全性為主

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First (NON-NEGOTIABLE) | spec FR-009; SC-009 延續 Phase 1 SC-008 git-history 紀律；本計畫 Phase 1 先產契約測試 | ✅ |
| II. Contract-First | OpenAPI 新增 `/auth/*`、`/admin/{whitelist,rules,restrictions,members}`、`/me/*` 端點；本計畫 Phase 1 產出 `contracts/openapi.yaml` 後再實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | Google OIDC：以 `respx` mock discovery/token endpoint；至少一個「真實 Google sandbox」smoke test 由 quickstart 列為手動步驟。Postgres：testcontainers | ✅ |
| IV. 可觀測性 | 認證審計事件以結構化 JSON 寫 DB + log；既有 `RedactionFilter` 擴充涵蓋密碼、ID token、邀請 token | ✅ |
| V. YAGNI | 不做 UI、不做密碼重設、不做 MFA、不做 SAML、不引入 cache 層；rate limit 用 DB 計數而非 Redis | ✅ |

**符合 experience.md 的教訓**：
- async SQLAlchemy 必 `selectinload`（Member ↔ Allocation、Member ↔ Session 雙向）
- datetime 一律 tz-aware（session/invitation/audit timestamps）
- 拒絕路徑先 bind context（失敗登入 audit 必須帶 `attempted_email` + IP）
- 不對外用 mutable image tag

**初次評估通過**：無違反，不需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-membership/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md            # /speckit.tasks 產出
```

### Source Code (repository root) — 新增於 Phase 1 之上

```text
src/ai_api/
├── api/
│   ├── allocations.py            # 既有
│   ├── records.py                # 既有
│   ├── health.py                 # 既有
│   ├── deps.py                   # 既有；加入 require_member, require_admin_session
│   ├── auth.py                   # 新：/auth/login(local), /auth/logout, /auth/oidc/start, /auth/oidc/callback, /auth/invitation/{token}
│   ├── me.py                     # 新：/me, /me/allocations, /me/allocations/{id}/calls, /me/password
│   ├── admin_members.py          # 新：/admin/members CRUD + /admin/members/{id}/sessions, /admin/sessions
│   ├── admin_access.py           # 新：/admin/whitelist, /admin/rules, /admin/source-restrictions
│   └── schemas.py                # 既有；新增 schemas
├── auth/
│   ├── __init__.py
│   ├── base.py                   # AuthProvider 抽象 + AuthResult/AuthError
│   ├── google_oidc.py            # Google OIDC 實作（authlib）
│   ├── local.py                  # Local password 實作（argon2）
│   ├── policy.py                 # 白名單 / 規則 / 來源限制 evaluation
│   ├── ratelimit.py              # PasswordAttempt 寫入與查詢
│   ├── invitations.py            # invitation token 發行 + 驗證
│   ├── sessions.py               # session 建立 / 驗證 / 撤銷
│   └── audit.py                  # auth_audit_log 寫入
├── models/
│   ├── allocation.py             # 既有；加 member_id FK + subject_snapshot
│   ├── credential.py             # 既有
│   ├── call_record.py            # 既有
│   ├── member.py                 # 新
│   ├── session.py                # 新
│   ├── access_control.py         # 新：EmailWhitelist, AutoRegisterRule, SourceRestriction
│   ├── invitation.py             # 新：InvitationToken
│   ├── password_attempt.py       # 新
│   └── auth_audit.py             # 新
├── services/
│   ├── allocations.py            # 既有；改用 member_id
│   ├── credentials.py            # 既有
│   ├── records.py                # 既有
│   ├── members.py                # 新
│   ├── sessions.py               # 新
│   ├── access_control.py         # 新
│   ├── invitations.py            # 新
│   └── ratelimit.py              # 新（PasswordAttempt 上的薄查詢）
├── observability/
│   ├── logging.py                # 既有；redaction 擴充加密碼/OIDC secret/session token
│   └── request_id.py             # 既有
├── config.py                     # 既有；新增 GOOGLE_OAUTH_CLIENT_ID/SECRET, GOOGLE_DISCOVERY_URL, COOKIE_DOMAIN, COOKIE_SECURE, BASE_URL
└── main.py                       # 既有；註冊新 routers + 認證 middleware

alembic/versions/
├── 0001_init.py                  # 既有
└── 0002_auth_membership.py       # 新（含資料 migration）

tests/
├── contract/
│   ├── test_auth_oidc.py
│   ├── test_auth_local.py
│   ├── test_admin_members.py
│   ├── test_admin_access.py
│   ├── test_me_endpoints.py
│   └── test_no_secret_leak_global.py    # 既有；擴充涵蓋密碼/cookie
├── integration/
│   ├── test_us1_google_sso.py
│   ├── test_us2_local_password.py
│   ├── test_us3_admin_controls.py
│   ├── test_us4_member_self_service.py
│   ├── test_us5_subject_migration.py    # 對既有 Phase 1 DB 跑 0002 migration
│   ├── test_session_disable_slo.py
│   └── test_redaction_for_passwords.py
└── unit/
    ├── test_argon2_hashing.py
    ├── test_invitation_token.py
    ├── test_policy_evaluation.py
    └── test_session_cookie.py
```

**Structure Decision**: 沿用 Phase 1 的 Option 1 單一專案，**新增 `auth/`
子模組**（與 `api/`、`models/`、`services/` 平行）作為認證領域的整合點：
provider 實作、policy 評估、session 與 invitation token 邏輯都集中於此，
keep `api/` 薄、`services/` 為純 DB 互動。

## Complexity Tracking

無待說明的偏離。Constitution Check 全部通過。

## Post-Design Re-check

在 Phase 1 完成 `data-model.md` / `contracts/openapi.yaml` / `quickstart.md`
之後重新檢視：

| 原則 | 重評 |
|---|---|
| Test-First | 契約檔已先於實作存在；OpenAPI 含 13 個新端點 → ✅ |
| Contract-First | `contracts/openapi.yaml` 完整定義所有對外端點與 ErrorResponse → ✅ |
| 整合測試覆蓋外部依賴 | Google OIDC 以 `respx` mock 並有真實 sandbox 手動步驟；Postgres testcontainers 跨版本 migration 測試 → ✅ |
| 可觀測性 | data-model.md 中 `AuthAuditLog` 表覆蓋成功登入、失敗登入、各管控變更；request_id 串接 → ✅ |
| YAGNI | 不引入 Redis、不引入 SMTP、不做 UI → ✅ |

通過。可進入 `/speckit.tasks` 拆解任務。
