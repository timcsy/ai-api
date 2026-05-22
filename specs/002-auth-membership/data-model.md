# Phase 1 Data Model: 階段 2 — 身份驗證與成員管理

新增 8 張表，並升級既有 `allocations`。所有時間欄位 `timestamptz` (UTC)。
所有 ID 為 ULID 字串。

```
                Member ──1:N── Session
                  │
                  ├─1:N── Allocation（升級：subject → member_id）
                  ├─1:0..1── InvitationToken（單次有效）
                  └─0:N── PasswordAttempt（log，非 FK）

                EmailWhitelist (PK email)
                AutoRegisterRule (PK id)
                SourceRestriction (PK id)
                AuthAuditLog (PK id)
```

---

## Entity: Member（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) ULID | ✓ | PK |
| `email` | text(320) | ✓ | 標準化後（lower、IDN normalize）；UNIQUE |
| `provider` | enum(`google_oidc`, `local_password`, `external`) | ✓ | 一個 Member 一個 provider |
| `external_id` | text(256) | ✗ | Google sub / 任意外部識別；同 provider 下 UNIQUE |
| `display_name` | text(256) | ✓ | 預設 email |
| `status` | enum(`active`, `disabled`) | ✓ | disabled → 所有 session 立即失效 |
| `password_hash` | text | ✗ | 僅 `local_password` 有；Argon2id PHC string |
| `created_at` | timestamptz | ✓ | |
| `disabled_at` | timestamptz | ✗ | 變 disabled 時設定 |
| `created_by` | text(128) | ✓ | bootstrap-admin / admin Member id / `migration` |

**Indexes**：
- `UNIQUE idx_member_email` on `lower(email)`
- `UNIQUE idx_member_provider_external` on `(provider, external_id)` WHERE external_id IS NOT NULL
- `idx_member_status` on `status`

**Validation**：
- `provider=local_password` ⇒ `password_hash IS NOT NULL`
- `provider=external` ⇒ `password_hash IS NULL`
- email 必為合法 RFC 5322 並標準化過

---

## Entity: Session（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(64) | ✓ | PK；session token 的 SHA-256 hex |
| `member_id` | text(26) FK → members.id | ✓ | ON DELETE CASCADE |
| `created_at` | timestamptz | ✓ | |
| `last_seen_at` | timestamptz | ✓ | 每次認證請求更新 |
| `expires_at` | timestamptz | ✓ | 預設 created_at + 24h |
| `idle_timeout_at` | timestamptz | ✓ | 預設 last_seen_at + 2h；每次活動推進 |
| `source_ip` | inet | ✗ | 建立時的 IP |
| `user_agent` | text(512) | ✗ | |
| `status` | enum(`active`, `revoked`) | ✓ | |
| `revoked_at` | timestamptz | ✗ | |
| `revoked_reason` | text(128) | ✗ | `member_disabled` / `manual` / `logout` |

**Indexes**：
- `idx_session_member_time` on `(member_id, last_seen_at desc)`
- `idx_session_status` on `status`

**Lifecycle**：
```
[create]──→ active ──[logout/revoke/expire/member_disabled]──→ revoked
```

---

## Entity: EmailWhitelist（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `email` | text(320) | ✓ | PK；標準化後 |
| `added_at` | timestamptz | ✓ | |
| `added_by` | text(128) | ✓ | |
| `note` | text(500) | ✗ | |

---

## Entity: AutoRegisterRule（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) | ✓ | PK |
| `rule_type` | enum(`email_domain`) | ✓ | 預留枚舉，首階段僅 `email_domain` |
| `pattern` | text(256) | ✓ | 例：`example.com`（不含 @） |
| `enabled` | bool | ✓ | default true |
| `created_at` | timestamptz | ✓ | |
| `created_by` | text(128) | ✓ | |
| `note` | text(500) | ✗ | |

**Indexes**：`idx_rule_enabled` on `(enabled, rule_type)`

---

## Entity: SourceRestriction（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) | ✓ | PK |
| `cidr` | cidr (Postgres native) | ✓ | 例：`10.0.0.0/8` |
| `enabled` | bool | ✓ | |
| `created_at` | timestamptz | ✓ | |
| `created_by` | text(128) | ✓ | |
| `note` | text(500) | ✗ | |

**邏輯**：若無任何 `enabled=true` 列 → 允許所有 IP；否則必須 match 至少
一條才允許。

---

## Entity: InvitationToken（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `token_fingerprint` | text(64) | ✓ | PK；SHA-256 hex |
| `token_prefix` | text(12) | ✓ | 明文前 12 字 for admin 識別 |
| `member_id` | text(26) FK → members.id | ✓ | UNIQUE — 每個 Member 同時最多 1 個有效邀請 |
| `created_at` | timestamptz | ✓ | |
| `expires_at` | timestamptz | ✓ | created_at + 48h |
| `used_at` | timestamptz | ✗ | 使用後設定；之後不可再用 |
| `created_by` | text(128) | ✓ | |

**Indexes**：
- `UNIQUE idx_invitation_member_active` on `member_id` WHERE `used_at IS NULL`
- `idx_invitation_expires` on `expires_at`（清理用）

---

## Entity: PasswordAttempt（新；rate limit + audit）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) | ✓ | PK |
| `email` | text(320) | ✓ | 標準化後；嘗試的 email（即使不存在） |
| `attempted_at` | timestamptz | ✓ | |
| `source_ip` | inet | ✗ | |
| `outcome` | enum(`success`, `bad_password`, `unknown_email`, `locked`, `disabled`) | ✓ | |

**Indexes**：
- `idx_attempt_email_time` on `(email, attempted_at desc)`

**Retention**：保留 30 天，超過由背景 job 清理（背景 job 非本階段交付）。

---

## Entity: AuthAuditLog（新）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | text(26) | ✓ | PK |
| `event_type` | enum | ✓ | `login_success` / `login_failure` / `logout` / `member_created` / `member_disabled` / `whitelist_added` / `whitelist_removed` / `rule_added` / `rule_removed` / `restriction_added` / `restriction_removed` / `password_changed` / `invitation_issued` / `invitation_used` |
| `actor_type` | enum(`admin`, `member`, `system`, `anonymous`) | ✓ | |
| `actor_id` | text(128) | ✗ | member_id / admin token name / null |
| `target_type` | enum(`member`, `session`, `whitelist`, `rule`, `restriction`, `invitation`) | ✗ | |
| `target_id` | text(128) | ✗ | |
| `source_ip` | inet | ✗ | |
| `user_agent` | text(512) | ✗ | |
| `request_id` | text(64) | ✗ | 對應 logging request_id |
| `created_at` | timestamptz | ✓ | |
| `details` | jsonb | ✗ | 額外結構化資料（**已 redact**） |

**Indexes**：
- `idx_audit_actor_time` on `(actor_type, actor_id, created_at desc)`
- `idx_audit_target_time` on `(target_type, target_id, created_at desc)`
- `idx_audit_event_time` on `(event_type, created_at desc)`

---

## Entity: Allocation（升級）

新增欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `member_id` | text(26) FK → members.id ON DELETE RESTRICT | NOT NULL (migration 後) |
| `subject_snapshot` | text(256) | 建立／migration 當下的 subject 值，供稽核 |

DROP：`subject`（內容已轉到 `subject_snapshot` + Member）

**Migration 策略**：見 research.md §8。

---

## Migration map（Spec FR → Entity / Index）

| FR | 對應實現 |
|---|---|
| FR-001~003 | Member.provider + UNIQUE email |
| FR-004 | OAuth flow 由 `auth/google_oidc.py` 用 authlib；session state/nonce 暫存於 `oidc_states` 表 *(見備註)* |
| FR-006~011 | Member.password_hash + InvitationToken + PasswordAttempt |
| FR-012 | EmailWhitelist / AutoRegisterRule / SourceRestriction 三表 CRUD |
| FR-014 | Member.status=disabled 觸發 Session 更新（service 層） |
| FR-015~017 | Session 表 + cookie 規範 |
| FR-018, FR-019 | `/me/*` 端點 + member_id filter |
| FR-020, FR-021 | 0002 migration data step |
| FR-022, FR-023 | AuthAuditLog + redact filter |

> **備註**：plan 中提到的 `oidc_states` 也是一張新表（PK=state、欄位有
> nonce、redirect_to、created_at、expires_at）；列在這裡避免被遺漏，
> 但因生命週期極短（≤ 10 分鐘），結構簡單，未獨立節說明。
