# Admin Auth Contract — Phase 3b.2 (c-β additive)

## require_admin dep

Replace `require_admin_token` with `require_admin`. Both paths accepted:

```
┌─────────────────────────────────────────────────┐
│  Incoming request to /admin/*                   │
└────────────────────┬────────────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       │                           │
       ▼                           ▼
┌─────────────┐         ┌─────────────────────┐
│ X-Admin-Token │         │ Session cookie       │
│ matches env?  │         │ → member.is_admin?   │
└──────┬──────┘         └──────┬──────────────┘
       │ yes                    │
       ▼                        ▼
    200 OK            yes → 200 OK
                      no  → 403 not_admin
       │                        │
       │   neither present      │
       └────────►  401 unauthorized
```

## Behavior table

| Auth scenario | Status | Body code |
|---|---|---|
| Valid X-Admin-Token | 200 | — |
| Session + is_admin=true | 200 | — |
| Session + is_admin=false | 403 | `not_admin` |
| Session + member.status≠active | 403 | `member_disabled` |
| No auth at all | 401 | `unauthorized` |
| Invalid X-Admin-Token + no session | 401 | `unauthorized` |
| Invalid X-Admin-Token + valid admin session | 200 | — (session wins) |

## Backwards compatibility

- All 274 existing tests pass `X-Admin-Token` header → still works.
- The dep returns `Member | None`:
  - `None` for token path (no member context available)
  - `Member` instance for session path (allows endpoints to attribute audit)

## Bootstrap sequence

```
1. Owner sets ADMIN_BOOTSTRAP_TOKEN env var
2. Owner creates Member alice via X-Admin-Token
   POST /admin/members
3. Owner promotes alice
   PATCH /admin/members/{alice_id} {"is_admin": true}
   → backend MemberService.set_is_admin
   → AuthAuditLog records 'member_promoted'
4. alice logs in via standard /auth/local/login or OIDC
5. alice's /me response now contains {"is_admin": true}
6. alice can access /admin/* with session cookie alone
   (no X-Admin-Token needed)
7. Owner can stop using X-Admin-Token for admin tasks
   (but keep it for emergency / CI)
```

## Last-admin guard

```
PATCH /admin/members/{X}/with-payload {"is_admin": false}

If X.is_admin is currently true AND count(active admins) == 1:
  → 409 last_admin_cannot_demote
  → audit event NOT written
  → DB row unchanged
```
