# Phase 1 Data Model: 階段 1 — 分流核心

## 概覽

四個實體，全部持久化於 PostgreSQL（本機可用 SQLite）。所有時間戳一律
UTC、ISO 8601 字串對外、`timestamptz` 對內。所有 ID 以 ULID 產生
（時間有序、適合審計）。

```
Allocation ──1:1── Credential
    │
    └─1:N── CallRecord
```

---

## Entity: Allocation

代表「擁有者把某個 AI 資源分配給某個對象」這個事件。

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | ULID (text) | ✓ | 對外公開的分配識別 |
| `subject` | text | ✓ | 被分配對象識別（階段 1 為任意字串，例 email/暱稱）|
| `resource_model` | text | ✓ | 綁定的 Azure OpenAI 模型 deployment 名稱 |
| `status` | enum(`active`, `revoked`) | ✓ | 當前狀態 |
| `created_at` | timestamptz | ✓ | 建立時間（UTC） |
| `revoked_at` | timestamptz | ✗ | 撤回時間，未撤回為 NULL |
| `created_by` | text | ✓ | 建立者識別（階段 1 固定為 `bootstrap-admin`）|
| `note` | text | ✗ | 擁有者自由註記（≤ 500 字） |

**驗證規則**：
- `subject` 非空、長度 ≤ 256
- `resource_model` 非空、長度 ≤ 128、符合 `[A-Za-z0-9_\-.]+`
- `status` 由系統管理，建立時必為 `active`
- `revoked_at` 必為 NULL 當且僅當 `status = active`

**狀態轉移**：
```
[create]──→ active ──[revoke]──→ revoked
                              ╲─[revoke (再次)]──→ revoked（冪等）
```

**索引**：
- PK on `id`
- `idx_allocation_subject` on (`subject`, `created_at desc`)
- `idx_allocation_status` on (`status`)（撤回後查詢分配清單常用）

---

## Entity: Credential

對外發行的 token。同一筆分配恰好一張憑證；憑證不可再生（撤回 + 重發等於
新建一筆分配）。

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `allocation_id` | ULID (text) | ✓ | FK → Allocation.id；同時為 PK |
| `token_fingerprint` | text | ✓ | token 明文的 SHA-256 hex；用以驗證 |
| `token_prefix` | text(8) | ✓ | token 前綴（明文）；僅供管理員介面識別用 |
| `created_at` | timestamptz | ✓ | 與 allocation 同時建立 |

**生成規則**：
- token 明文 = `aiapi_` 前綴 + 32 bytes URL-safe base64 隨機字串
- 明文**僅在建立時回傳一次**，之後系統不可再取得
- 驗證以「SHA-256(token) == fingerprint」比對

**索引**：
- PK on `allocation_id`
- `idx_credential_fingerprint` (UNIQUE) on `token_fingerprint`

**驗證規則**：
- `token_fingerprint` 必為 64 字 hex
- `token_prefix` 取 token 明文前 8 字（含 `aiapi_` 前綴中的前 8 字）

---

## Entity: CallRecord

每次經過閘道的呼叫記錄一筆。

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | ULID (text) | ✓ | 紀錄 ID |
| `request_id` | text | ✓ | 與日誌交叉對應；通常為 UUID v4 |
| `allocation_id` | ULID (text) | ✗ | NULL 表「匿名拒絕」（無有效憑證） |
| `subject` | text | ✗ | 冗餘存放，便於日後 allocation 改名／刪除時的稽核（snapshot） |
| `model` | text | ✗ | 實際嘗試呼叫的模型；NULL 表早於模型解析就被拒 |
| `started_at` | timestamptz | ✓ | 收到請求時間 |
| `finished_at` | timestamptz | ✓ | 寫入紀錄時間 |
| `status_code` | smallint | ✓ | HTTP 狀態碼 |
| `outcome` | enum(`success`, `rejected_unauthenticated`, `rejected_revoked`, `rejected_model_mismatch`, `upstream_error`, `gateway_error`) | ✓ | 結構化結果分類 |
| `prompt_tokens` | int | ✗ | 上游回報 |
| `completion_tokens` | int | ✗ | 上游回報 |
| `total_tokens` | int | ✗ | 上游回報 |
| `error_message` | text | ✗ | 結構化錯誤摘要（**經 redaction**） |

**驗證規則**：
- `outcome == rejected_unauthenticated` ⇒ `allocation_id` 必為 NULL
- `outcome == success` ⇒ `allocation_id` 必非 NULL 且 `status_code == 200`
- `error_message` 在寫入前必經 redaction filter（FR-009 防線）

**索引**：
- PK on `id`
- `idx_callrecord_allocation_time` on (`allocation_id`, `started_at desc`)
- `idx_callrecord_outcome_time` on (`outcome`, `started_at desc`)（供管理員 dashboard 統計）

---

## Entity: Subject（邏輯實體，無獨立表）

階段 1 不獨立建表。`subject` 為字串識別，由建立分配的擁有者填入；同一字串
可有多筆分配。階段 2（SSO）後升級為真實使用者表，屆時用一次性 migration
將 `subject` 字串映射至使用者 ID。

---

## 不持久化、僅在記憶體／日誌中存在

- **底層 Azure OpenAI key**：僅存在於環境變數 / K8s Secret；redaction filter
  在 log/response 邊界以 `***` 取代
- **進程內快取**：階段 1 不引入；每次呼叫查 DB（見 research.md §4）

---

## 與 Spec FR 的對應

| Spec 條目 | 模型反映 |
|---|---|
| FR-001 | Allocation.subject + resource_model |
| FR-002 | Credential.token_fingerprint（唯一）+ token 生成規則 |
| FR-003 | Allocation 狀態轉移冪等 |
| FR-004 | 全部於 RDBMS 持久化 |
| FR-006 | 驗證路徑必須讀 Allocation.status |
| FR-008 | CallRecord.outcome=`rejected_model_mismatch` |
| FR-009 | CallRecord.error_message 經 redaction |
| FR-011 | CallRecord 各欄位 |
| FR-012 | `idx_callrecord_allocation_time` 索引 |
| FR-013 | CallRecord.allocation_id NULLable + outcome=`rejected_unauthenticated` |
