# Data Model：scoped application credentials（M:N）

## 變更總覽

`Credential`：**屬於分配（1:N）→ 屬於成員、scope 經關聯表（M:N）**。新增關聯實體 `CredentialAllocation`。`Allocation` 語意不變。

## Credential（變更，migration `0017`）

| 欄位 | 變更 | 說明 |
|------|------|------|
| `id` | 不變（PK） | ULID String(26) |
| `allocation_id` | **移除** | 改由 `credential_allocations` 表達 scope |
| `member_id` | **新增（FK→members, NOT NULL）** | 擁有者；backfill 自舊 `allocation.member_id` |
| `name` | 不變 | 應用名（如「我的筆電 Codex」） |
| `token_fingerprint` | 不變（唯一） | token 雜湊；token→credential 仍 1 命中 |
| `token_prefix` | 不變 | 顯示用 |
| `created_at` / `last_used_at` / `revoked_at` | 不變 | 建立 / 節流最後使用 / 軟撤回 |

關係：`Credential.allocations`（list，經 `credential_allocations`）、`Credential.member`。

## CredentialAllocation（新，關聯實體）

一把憑證可用哪些分配。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `credential_id` | String(26) FK→credentials(ondelete CASCADE) | |
| `allocation_id` | String(26) FK→allocations(ondelete CASCADE) | |
| `resource_model` | String(128) | **denormalize 自 allocation**（不可變）；供 DB 級唯一 + 單查詢挑分配 |

鍵 / 索引：`PK(credential_id, allocation_id)`；`UNIQUE(credential_id, resource_model)`（**FR-003 歸戶無歧義**）；`INDEX(allocation_id)`（反查「哪些 key 含此分配」）。

## Allocation（不變）

唯讀引用；`Allocation.credentials` 反向關係改經 `credential_allocations`（仍回「scope 含此分配的 key」）。`resource_model`、`status`、`quota_*` 不變——計費/歸戶單位。

## 不變式 / 規則（對應 FR）

- **scope = 一組分配（≥1）**；建立至少 1 筆，移除不可到 0（撤回走撤回端點）（FR-001 / Edge）。
- **同 key 內 model 唯一**：`UNIQUE(credential_id, resource_model)`（FR-003）。
- **解析**：proxy = `token→credential(revoked_at IS NULL)` →（None→401）→ `(credential_id, requested_model)` 查關聯 →（None→403 model_mismatch）→ allocation；之後 status/quota/access/billing 全 per-allocation 不變（FR-002 / FR-004）。
- **attenuation**：scope 內每筆 allocation 必須 `member_id == credential.member_id`（= 擁有者已被授予）（FR-005）。
- **不連坐**：撤一把 key（`revoked_at`）只影響該 key；其關聯被一起停用，其他 key 照常（FR-011）。
- **show-once + hash-only**：不變（FR-011）。
- **稽核**：scope 增/刪、撤回留 audit（FR-008）。

## 既有 token 零回歸（migration 保證）

- 既有每把單分配憑證 → `member_id` 補齊 + 在 `credential_allocations` 補一列（其 allocation + resource_model），**token_fingerprint 不變**。
- 結果:等同「scope 含一筆分配的 app key」→ 既有 token 解析/歸戶/呼叫完全不變（SC-004）。

## Migration 0017 注意

- **in-place ALTER**（`credentials` 被 `device_authorizations.credential_id` 參照，不可 drop+rename 整表）。
- SQLite 用 `batch_alter_table`（加 `member_id`、丟 `allocation_id`）；Postgres 原生 ALTER。
- backfill 用 raw SQL（跨 DB）；新關聯與既有表**無循環 FK**。
- **Postgres 整合測試固化**（FK、唯一鍵、零回歸）。
