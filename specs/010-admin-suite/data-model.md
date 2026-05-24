# Phase 1 Data Model: 階段 3b.2 — Admin Suite

## 概覽

唯一 schema 變動：`members.is_admin: bool`。

```
Member (existing, extended)
  + is_admin: bool (default false)
```

無新表、無新關聯、無 enum 擴充。

---

## Member 擴充

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `is_admin` | bool | `false` | True = session-based admin auth 通過 |

**Constraints**：
- 無 DB-level constraint；「至少一個 admin」由 application 層 `MemberService`
  保證
- migration 對既有 row：`server_default=false` → 所有現有 Member 升級後 is_admin=false

---

## AuthAuditLog 擴 enum

| 新 event_type | 觸發時機 |
|---|---|
| `member_promoted` | `set_is_admin(member_id, True)` 成功時 |
| `member_demoted` | `set_is_admin(member_id, False)` 成功時 |

actor: token-path → "admin:bootstrap"；session-path → 該 admin 的 member id

---

## Migration 0007 概要

```python
def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.add_column(
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Audit event enum extension（同 0003/0004/0005 batch_alter 模式）
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(*_OLD, name="auditeventtype", native_enum=False, length=64),
            type_=sa.Enum(*_NEW, name="auditeventtype", native_enum=False, length=64),
            existing_nullable=False,
        )
```

`_OLD` / `_NEW` 同 Phase 3c migration 0005 模式（list of enum values + 2 new）。

---

## Service signature 變動

### MemberService.update（既有）

不需動；新增 `is_admin` 走另一個 method（更明確 + 避免 audit event 混淆）。

### MemberService.set_is_admin（新）

```python
async def set_is_admin(
    self,
    member_id: str,
    is_admin: bool,
    actor: str = "admin",
) -> Member:
    """Promote/demote a member; guards against last-admin demotion."""
```

raises `LastAdminCannotDemoteError` 由 endpoint 層 catch → 409。

---

## Frontend type

```ts
export type Member = {
  id: string;
  email: string;
  display_name?: string | null;
  provider?: string;
  status?: string;
  is_admin?: boolean;
};
```

`is_admin?` optional 避免 backend 沒回欄位時 type error；用 strict equality
`member?.is_admin === true` 保證 false-default。
