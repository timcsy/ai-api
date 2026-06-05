# Data Model：device-flow（裝置授權）

## 新表：`device_authorizations`（migration `0016`）

一次 device-flow 授權嘗試。短時效、單次使用。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | String(26) PK | ULID |
| `device_code` | String(64) **unique, index** | 高熵不透明；CLI 輪詢用 |
| `user_code` | String(16) **unique, index** | 人類可讀短碼（`XXXX-XXXX`）；成員在瀏覽器確認用 |
| `status` | Enum(VARCHAR) | `pending` / `approved` / `denied` / `expired`（`Enum(..., native_enum=False)`，加值免 migration） |
| `device_label` | String(64) nullable | CLI 帶上的裝置提示（如 `Codex on host-x`）；mint 時當憑證名 |
| `member_id` | String(26) FK→members nullable | 核可時寫入（核可者＝擁有者） |
| `allocation_id` | String(26) FK→allocations nullable | 核可時成員選定的分配 |
| `credential_id` | String(26) FK→credentials nullable | 核可時 mint 的憑證 |
| `encrypted_token` | Text nullable | Fernet 加密的明文 token；**交付一次後清 NULL**（hash-only 的有界例外） |
| `created_at` | DateTime(tz) | |
| `expires_at` | DateTime(tz) | `created_at + 600s` |
| `approved_at` | DateTime(tz) nullable | |
| `last_polled_at` | DateTime(tz) nullable | 節流（`slow_down`）判定 |
| `poll_interval` | Integer | 預設 5（秒） |

索引：`idx_device_auth_device_code`（unique）、`idx_device_auth_user_code`（unique）、`idx_device_auth_status_expires`（清理用）。

## 狀態機

```
                ┌──── approve（擁有者選分配）──► approved ──token 交付一次──► （明文清空、終結）
pending ────────┤
                ├──── deny ─────────────────► denied（終結）
                └──── 逾時 / 過 expires_at ─► expired（終結；惰性或背景清理）
```

- `pending`：可被 `GET /me/device/{user_code}` 讀、可 approve/deny；CLI 輪詢回 `authorization_pending`（或 `slow_down`）。
- `approved`：`encrypted_token` 有值；CLI 下次輪詢回 `{token,...}` 並清 `encrypted_token`（之後再輪詢回 `expired_token`／已取走）。
- `denied`：CLI 輪詢回 `access_denied`。
- `expired`：CLI 輪詢回 `expired_token`。

## 不變式 / 規則（對應 FR）

- **單次交付**：明文僅 `encrypted_token` 持有，`POST /device/token` 成功後立即清 NULL（FR-008/010）。
- **短時效 + 單次**：過 `expires_at` 一律 `expired`；approve/deny/交付後不可再轉態（FR-011）。
- **節流**：`now - last_polled_at < poll_interval` → `slow_down`（不推進）（FR-011）。
- **擁有者邊界**：approve 要求 `current_member` 且 `allocation.member_id == current_member.id`；否則 403、不 mint（FR-012）。
- **mint 沿用階段 18**：核可呼叫 `AllocationService.add_credential(allocation, device_label)`；憑證進「裝置與憑證」清單、可撤回/rotate（FR-013）。
- **稽核**：approve/deny 寫 `device_authorization_approved` / `device_authorization_denied`（含 member、allocation、credential id）（FR-014）。

## 既有實體沿用

- **Credential**（階段 18）：device-flow 核可時新建一筆，綁分配、具裝置名。零 schema 變更。
- **Allocation / Member**：唯讀引用。

## Migration 0016 注意

- 純新增表（無既有資料搬遷）；但仍 **Postgres 整合測試驗**（FK、enum VARCHAR、tz 欄、unique 索引在 Postgres 行為）。
- `device_authorizations` 與其他表無循環 FK（避免階段 13 的 mutual-FK 陷阱）。
