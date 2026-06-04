# Data Model：憑證模型重構（每分配多 per-device 憑證）

## 變更總覽

`Credential`：**1:1 → 1:N**（一筆 `Allocation` 可有多筆 `Credential`）。`Allocation` 語意不變。

## Credential（變更）

| 欄位 | 變更 | 說明 |
|------|------|------|
| `id` | **新增（PK）** | ULID String(26)；取代原本以 `allocation_id` 當主鍵 |
| `allocation_id` | **改一般 FK + 索引（非唯一）** | 一分配可多筆；`ondelete=CASCADE` 維持 |
| `name` | **新增** | 裝置名 / label（如「我的筆電」）；新增時必填 |
| `last_used_at` | **新增（nullable）** | 最後成功使用時間（節流更新，僅顯示用） |
| `revoked_at` | **新增（nullable）** | 軟撤回；非空＝已撤回，排除於 token 解析 |
| `token_fingerprint` | 不變（**仍唯一**） | token 雜湊；唯一 → token→credential 1 對 1 命中 |
| `token_prefix` | 不變 | 顯示用前綴 |
| `created_at` | 不變 | |

關係：`Allocation.credential`（scalar）→ `Allocation.credentials`（list）。

## 不變式 / 規則（對應 FR）

- **唯一性在分配層**：額度、用量、歸戶、可追蹤性綁 `allocation_id`；憑證不持有額度（FR-003/009）。
- **token 解析**：`lookup_by_token` = `token_fingerprint == fp AND revoked_at IS NULL` → credential → allocation（FR-004）。
- **撤回單把不連坐**：設 `revoked_at`；同分配其他 `revoked_at IS NULL` 者照常解析（FR-002）。
- **show-once + hash-only**：新增時回明文一次，平台只存 fingerprint（FR-006）。
- **擁有者邊界**：member 端點只能對 `allocation.member_id == current_member` 的憑證操作（FR-005）。

## 狀態轉移（單把憑證）

```
（新增）active（revoked_at = NULL）  ──撤回──▶  revoked（revoked_at = now，永久，不解析）
```
分配層的狀態（active/paused/quarantined/revoked）與此獨立；撤回單把 ≠ 撤銷分配（FR-010）。

## Migration 0015（資料保留）

- 重建 `credentials`（batch 模式）：`id` PK、`allocation_id` FK+索引、加三欄、`token_fingerprint` 唯一。
- 既有每列 → 補 `id`(新 ULID) + `name="預設"` + `revoked_at=NULL`；`token_fingerprint`/`token_prefix`/`created_at` **原樣搬**。
- 結果：既有 token 不失效（fingerprint 不變），每分配恰有一把名為「預設」的憑證。
