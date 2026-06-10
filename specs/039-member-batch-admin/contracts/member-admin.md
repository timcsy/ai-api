# Contracts: 管理員成員管理批次化 + 安全刪除

所有端點掛在既有 admin router（`/admin` 前綴），**僅管理員 session 可用**；非管理員/未驗證 → 401/403（沿用既有 admin 守衛）。錯誤封包沿用既有 `{"error": {"code", "message"}}`（FastAPI HTTPException `detail` 包裝；前端 `body.error ?? body.detail?.error`）。

---

## 1. `DELETE /admin/members/{member_id}` —（行為變更）安全刪除單一成員

把既有「有分配就擋下」改為「安全刪除」。

**Request**：path `member_id`；無 body。

**Behavior**：在單一交易內，撤回並刪除該成員所有分配、刪憑證與連結、將其呼叫紀錄 `allocation_id` 設為 NULL、刪成員（見 data-model A）。

**Responses**：
- `204 No Content`：刪除成功（含「有分配」與「無分配」兩種情形）。
- `403 cannot_delete_self`：`member_id` 等於當前管理員自己。
- `409 last_admin`：該成員是最後一位 active 管理員，拒絕刪除。
- `404 not_found`：成員不存在。

**Side effects**：寫一筆 `member_deleted` 稽核；該成員 `CallRecord` 保留（`allocation_id IS NULL`）。

**回歸**：對「無分配」成員的刪除行為與結果（204）維持不變；不再回先前的「revoke and delete allocations before deleting member」擋阻。

---

## 2. `POST /admin/members/bulk-delete` —（新增）批次安全刪除

**Request**：
```json
{ "member_ids": ["<id>", "<id>", "..."] }
```
- `member_ids`：非空字串陣列。空陣列 → `400 bad_request`。

**Behavior**：對每個 id **獨立**套用端點 1 的安全刪除（逐筆獨立成敗，不整批回滾）。守衛（self / last-admin）在逐筆層判定。

**Response** `200 OK`：
```json
{
  "deleted": 2,
  "failed": 1,
  "results": [
    { "member_id": "...", "status": "deleted", "reason": null },
    { "member_id": "...", "status": "failed", "reason": "last_admin" }
  ]
}
```
- `status` ∈ `deleted` / `failed`；`reason` ∈ `cannot_delete_self` / `last_admin` / `not_found` / `internal`（成功為 null）。

**Side effects**：每筆成功寫一筆 `member_deleted` 稽核。

---

## 3. `POST /admin/members/bulk-create` —（新增）批次預建 local_password 成員

**Request**：
```json
{ "emails": "a@x.com\nb@x.com\n..." }
```
或等價的字串陣列 `{ "emails": ["a@x.com", "b@x.com"] }`（實作擇一，契約測試對齊）。空/全空白 → `400 bad_request`。

**Behavior**：解析多行 → trim → 去空行 → 同批去重 → 逐筆以 `provider=local_password`、`send_invitation=true` 套既有 create。

**Response** `200 OK`：
```json
{
  "created": 1,
  "exists": 1,
  "invalid": 1,
  "duplicate": 0,
  "results": [
    { "email": "new@x.com", "status": "created", "invitation_url": "https://<base>/auth/invitation/<token>" },
    { "email": "old@x.com", "status": "exists", "invitation_url": null },
    { "email": "bad-email", "status": "invalid", "invitation_url": null }
  ]
}
```
- `status` ∈ `created` / `exists` / `invalid` / `duplicate`；`invitation_url` 僅 `created` 提供。

**Side effects**：每筆 `created` 寫一筆 `member_created` 稽核。

---

## 契約測試要點（合併前必過）

- 端點 1：有分配成員 → 204 + 該成員 CallRecord 仍在且 `allocation_id IS NULL`；刪自己 → 403；最後一位 admin → 409；無分配成員 → 204（回歸）。
- 端點 2：混合（成功 + 刪自己 + 不存在）→ 200 + 逐筆 results 正確分類；空陣列 → 400。
- 端點 3：混合（新 + 已存在 + 格式錯 + 同批重複）→ 200 + 逐筆分類 + created 帶 invitation_url；空清單 → 400。
- 授權：三端點無 admin session → 401/403（非 404）。
