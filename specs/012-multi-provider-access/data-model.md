# Phase 1 — Data Model

## ER 概覽

```text
Provider (enum, app-level)        ──┐
                                    │
ProviderCredential ─────────────────┤
  id PK                             │
  provider                          │
  label                             │   used by routing
  enc_key                           │
  fingerprint                       │
  base_url? extra_config?           │
  status                            │
  last_used_at?                     │
  created_at created_by             ▼
                                  routes
                                    │
ModelCatalog (EXISTING + 4 cols)    ▼
  slug PK                       routes to Provider
  + provider                        │
  + default_access                  │
  + allowed_tags JSON               │
  + denied_tags JSON                ▼
                              filtered to Member by
                                Member.tags
                                    ▲
Member (EXISTING)                   │
  id PK                          (M:N)
  ...                               │
MemberTag                           │
  member_id FK ──────────────────── ┘
  tag (string)
  added_by added_at
  PK(member_id, tag)
```

## 1. ProviderCredential（新）

**目的**：admin 為某家 LLM provider 加入的 API 憑證；可有多筆同 provider（round-robin）。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `str` ULID, PK | |
| `provider` | `str(32)` indexed | enum-like：`azure_openai` / `openai` / `anthropic` / `gemini`；驗證時對照 `Settings.allowed_providers` |
| `label` | `str(64)` | 人類可讀標記（例：「team-a-prod」）；同 provider 內唯一（unique constraint） |
| `enc_key` | `bytes` | Fernet 加密後的 plaintext API key |
| `fingerprint` | `str(16)` | SHA-256(plaintext) 的前 16 hex 字元；顯示用 |
| `base_url` | `str(256) NULL` | 覆寫預設端點（Azure 必填 endpoint；其他家可選） |
| `extra_config` | `JSON NULL` | 例：Azure `{api_version}`、Gemini `{project, location}` |
| `status` | `enum('active','disabled')` | |
| `last_used_at` | `datetime(tz) NULL` indexed | round-robin 用 |
| `created_at` | `datetime(tz)` not null | |
| `created_by` | `str` not null | Member.id or `bootstrap-admin` |
| `disabled_at` | `datetime(tz) NULL` | |

**約束**：
- `UNIQUE(provider, label)`
- `INDEX(provider, status, last_used_at)` — 路由查詢主路徑
- `CHECK fingerprint LIKE '[0-9a-f]{16}'`（appliction-side enforced）

**State transitions**：
- `active` → `disabled`（admin 操作；不可逆，要重啟用得新建）
- `active` 內 enc_key + fingerprint 可被 rotate（in-place 替換）

**驗證規則**：
- `provider` 必在 `Settings.allowed_providers` 內，否則 422
- 建立 / rotate 時 plaintext key 不可空、長度 ≥ 8

## 2. MemberTag（新）

**目的**：成員與 tag 字串的多對多。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `member_id` | `str` FK → Member.id, PK | ON DELETE CASCADE |
| `tag` | `str(64)` PK | snake_case + lowercase enforced |
| `added_by` | `str` not null | 哪個 admin 加的 |
| `added_at` | `datetime(tz)` not null | |

**約束**：
- `PRIMARY KEY (member_id, tag)`
- `INDEX(tag)` — 反查「哪些 member 有 X tag」用
- `INDEX(member_id)` — 反查「member 有哪些 tag」用（catalog 過濾主路徑）
- application-level: `tag` 必符合 `^[a-z][a-z0-9_-]{0,63}$`

**首版不獨立 Tag 表**：tag 名稱以 `MemberTag.tag` 的 distinct 集合代表。需要 tag CRUD 介面時，「刪除 tag」= 刪除所有 member 對該 tag 的關聯。理由：YAGNI；組織內部規模不需要 tag metadata（description / color 等）；未來需要時新增 `Tag` 表只是 schema 增量。

## 3. ModelCatalog（既有，加 4 欄）

| 新欄位 | 型別 | 說明 |
|---|---|---|
| `provider` | `str(32)` not null indexed | 對應 `ProviderCredential.provider`；YAML loader 強制 |
| `default_access` | `enum('open','restricted')` not null | 無系統預設，YAML 必填 |
| `allowed_tags` | `JSON` not null default `[]` | list of tag strings |
| `denied_tags` | `JSON` not null default `[]` | list of tag strings |

**Migration 0009 同時做**：
- 建 `provider_credentials` 與 `member_tags`
- 對 `model_catalog` 加 4 欄；既有 9 row backfill：`provider='azure_openai'`、`default_access='open'`、tags 都 `[]`

**驗證規則**：
- YAML loader 拒絕缺 `provider` / `default_access` 的 model
- `provider` 必在 `Settings.allowed_providers` 內

## 4. AuditEventType（既有 enum，加值）

新增：
- `provider_credential_created`
- `provider_credential_rotated`
- `provider_credential_disabled`
- `provider_credential_used_first_time`
- `member_tag_added`
- `member_tag_removed`
- `member_tag_bulk_added`
- `model_access_policy_updated`

**Migration 0010**：沿用 0007 / 0008 的 `batch_alter_table` + `sa.Enum(*OLD)` → `sa.Enum(*NEW)` pattern。

## 5. 既有實體不變

- `Member`：不加欄位（tag 走關聯表）
- `Allocation`：不加欄位（model 不綁 provider，由 catalog 即時查）
- `Credential`（allocation token）：不動

## 跨實體規則

- **Credential gate**：`Model M` 對成員可見的前提是 `EXISTS (SELECT 1 FROM provider_credentials WHERE provider=M.provider AND status='active')`
- **Access policy**：見 research.md R5 邏輯
- **Tag 變更立即生效**：無快取層（FR-018）

## 索引總覽

| 表 | 索引 | 用途 |
|---|---|---|
| `provider_credentials` | `(provider, status, last_used_at)` | 路由查 next available |
| `provider_credentials` | `UNIQUE(provider, label)` | admin 建立衝突偵測 |
| `member_tags` | `(member_id)` | 成員看自己 tag |
| `member_tags` | `(tag)` | 反查 tag 命中的 member |
| `model_catalog` | `(provider)` | credential gate 反查 |

## Migration 計畫

- **0009** `phase5_multiprovider_schema`：
  - 建 `provider_credentials` 表 + 索引 + unique
  - 建 `member_tags` 表 + 索引
  - 對 `model_catalog` 加 4 欄；backfill 既有 9 row
- **0010** `phase5_audit_events`：擴 `AuditEventType` enum（8 個新值）
