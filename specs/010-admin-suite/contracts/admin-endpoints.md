# Admin Endpoints Contract — Phase 3b.2 (extension only)

## PATCH /admin/members/{member_id}

**Before** (Phase 2): accepts `display_name`, `status`

**After** (Phase 3b.2): accepts additionally `is_admin: bool`

### Request body schema

```ts
type UpdateMemberRequest = {
  display_name?: string;
  status?: "active" | "disabled";
  is_admin?: boolean;  // NEW
};
```

### Behavior

- Three independent updates; any subset can be sent.
- If `is_admin` is set:
  - The endpoint calls `MemberService.set_is_admin()` internally
  - Audit event `member_promoted` / `member_demoted` written
  - If demotion would leave 0 active admins → 409 `last_admin_cannot_demote`

### Response (200)

```json
{
  "id": "...",
  "email": "...",
  "display_name": "...",
  "provider": "...",
  "status": "active",
  "is_admin": true,
  "created_at": "...",
  "disabled_at": null
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | not_found | member_id 不存在 |
| 409 | last_admin_cannot_demote | 嘗試把唯一 active admin 降為非 admin |
| 401/403 | unauthorized / not_admin | require_admin 失敗（見 admin-auth.md）|

## GET /me — response shape extension

**Added field**: `is_admin: boolean`

```json
{
  "id": "...",
  "email": "alice@x.com",
  "provider": "local_password",
  "display_name": "Alice",
  "status": "active",
  "is_admin": true
}
```

Backwards compat: 客戶端讀 `is_admin ?? false` 處理舊 response。
本階段 frontend 對 `is_admin` 用 `?? false` 預設 falsy。

## No other endpoint shape changes

其他 admin endpoints（/admin/members POST/DELETE、/admin/allocations *、
/admin/usage *、/admin/quota-pool *、/admin/catalog 預覽（無新 endpoint）、
/admin/quota-pool/rebalance-log *）shape **不變**。

只是 dep 從 `require_admin_token` → `require_admin`（行為向下相容）。
