# Phase 0 Research: 階段 3b.2 — Admin Suite

---

## 1. `require_admin` 雙軌 dep 實作（c-β additive）

**驗證來源**：`src/ai_api/api/deps.py:19`、`src/ai_api/api/admin_members.py:20`
等 30 個 admin endpoint 都用 `Depends(require_admin_token)`。

**決策**：新增 `require_admin` 函式取代 `require_admin_token`：

```python
async def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Member | None:
    """Pass if either X-Admin-Token is valid OR session-with-admin is present."""
    settings = get_settings()
    # 1. token path（既有行為）
    if x_admin_token and x_admin_token == settings.admin_bootstrap_token:
        return None  # token path → no Member context

    # 2. session-with-admin path
    if session_cookie:
        sm = get_sessionmaker()
        async with sm() as s:
            member = await validate_session(s, session_cookie)
            await s.commit()
        if member and member.is_admin and member.status == MemberStatus.active:
            return member
        if member is not None:
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "not_admin", "message": "admin role required"}},
            )

    # 3. neither path → 401
    raise HTTPException(
        status_code=401,
        detail={"error": {"code": "unauthorized", "message": "admin auth required"}},
    )
```

**既有 `require_admin_token` 處理**：改為 `require_admin` 的別名（pointing
to 同一個 function）— 既有 30 個 `Depends(require_admin_token)` callers
0 改動。

**理由**：
- 既有 274 admin_headers 測試帶 X-Admin-Token → 走 path 1 → 通過
- 新 admin UI 用 session cookie → 走 path 2 → 通過
- 一般 member 無 token、has session 但 is_admin=false → path 2 403
- 未登入 + 無 token → 401

**Alternatives 評估**：
- 維持兩個 deps（require_admin_token / require_admin_session）並讓每個
  endpoint 選一個：複雜 + 容易選錯
- 完全替換 X-Admin-Token：破壞 274 處測試（已決定不做，c-β）

---

## 2. Bootstrap 流程

**決策**：流程如下，**無新 endpoint**：

```bash
# 1. 後端啟動，admin_bootstrap_token 已設於 env
# 2. owner 建一個 Member（既有）
curl -X POST http://localhost:8000/admin/members \
  -H "X-Admin-Token: $TOKEN" \
  -d '{"email":"alice@x.com","provider":"local_password","initial_password":"..."}'

# 3. 取得 alice 的 member_id
ALICE_ID=$(curl ... | jq -r '.[0].id')

# 4. 用既有 PATCH endpoint set is_admin
curl -X PATCH http://localhost:8000/admin/members/$ALICE_ID \
  -H "X-Admin-Token: $TOKEN" \
  -d '{"is_admin": true}'

# 5. alice 用一般 login 進入；session 帶 is_admin
```

**理由**：
- 不引入新 endpoint；既有 PATCH /admin/members/{id} 加一個 field 即可
- audit log 記 `member_promoted` (event_type 新增)

---

## 3. Last-admin guard

**決策**：在 service 層而非 endpoint 層實作：

```python
class MemberService:
    async def set_is_admin(self, member_id: str, is_admin: bool) -> Member:
        member = await self._get(member_id)
        if not is_admin and member.is_admin:
            # Demotion — check this isn't the last admin
            count = await self._db.scalar(
                select(func.count()).select_from(Member).where(
                    Member.is_admin.is_(True),
                    Member.status == MemberStatus.active,
                )
            )
            if count <= 1:
                raise LastAdminCannotDemoteError(...)
        member.is_admin = is_admin
        await self._db.flush()
        return member
```

Endpoint 層 catch 此 error → 409。

**已評估**：
- 在 endpoint 層查：服務邊界錯
- DB CHECK constraint：跨 row 約束 Postgres 不直接支援；trigger 太複雜

---

## 4. 前端 admin 路由結構

**決策**：

```tsx
// App.tsx
<Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
  {/* member routes (3b.1) */}
  <Route path="/dashboard" element={<DashboardPage />} />
  ...
  <Route path="/catalog" element={<CatalogPage />} />
  <Route path="/catalog/*" element={<CatalogDetailPage />} />

  {/* admin routes (3b.2) — wrapped in AdminRoute */}
  <Route element={<AdminRoute />}>
    <Route path="/admin" element={<Navigate to="/admin/members" replace />} />
    <Route path="/admin/members" element={<AdminMembersPage />} />
    <Route path="/admin/allocations" element={<AdminAllocationsPage />} />
    <Route path="/admin/usage" element={<AdminUsagePage />} />
    <Route path="/admin/quota-pool" element={<AdminQuotaPoolPage />} />
    <Route path="/admin/rebalance-log" element={<AdminRebalanceLogListPage />} />
    <Route path="/admin/rebalance-log/:id" element={<AdminRebalanceLogDetailPage />} />
    <Route path="/admin/catalog" element={<CatalogPage />} />
    <Route path="/admin/catalog/*" element={<CatalogDetailPage />} />
  </Route>
</Route>
```

`AdminRoute` 用 `<Outlet />` 包子節點；is_admin=false 顯示「無權限」內嵌頁。

---

## 5. 表單模式：react-hook-form + zod + shadcn form

**決策**：所有 admin 表單統一用 react-hook-form + zod 驗證：

```tsx
const memberSchema = z.object({
  email: z.string().email("email 格式錯"),
  provider: z.enum(["local_password", "external"]),
  initial_password: z.string().min(12, "密碼至少 12 字元").optional(),
});

function CreateMemberDialog() {
  const form = useForm<z.infer<typeof memberSchema>>({
    resolver: zodResolver(memberSchema),
    defaultValues: { provider: "local_password" },
  });
  const onSubmit = form.handleSubmit(async (values) => {
    await api("/admin/members", { method: "POST", body: JSON.stringify(values) });
    toast({ title: "Member 已建立" });
    queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
  });
  return <Form {...form}>...</Form>;
}
```

**理由**：
- zod 一處宣告 schema → form 驗證 + TypeScript type 自動推導
- shadcn `form.tsx` 提供 `<FormField>` / `<FormItem>` / `<FormMessage>` 標準
  化錯誤呈現
- 後端 error 在 catch 中 toast；表單字段錯誤從 zod 來

---

## 6. CSV/JSON 下載

**決策**：`lib/download.ts`：

```ts
export function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

// 用法
const csv = await api<Response>("/admin/usage.csv?...", { raw: true });
triggerDownload(`usage-${from}-${to}.csv`, await csv.blob());
```

**注意**：CSV/JSON endpoint 回 `text/csv` / `application/json`，需要拿 Blob
而非 JSON parse。需擴 `api()` 加 `{raw: true}` 模式或新增 `apiBlob()` 函式。

**決策**：新增 `apiBlob(path)` 簡單函式，不污染既有 `api<T>` 介面。

---

## 7. Admin Allocations filter state

**決策**：與 3b.1 catalog 模式一致 — `useAdminAllocationsFilters` hook 用
`useSearchParams`：

```ts
type Filters = {
  status: "active" | "revoked" | "all";  // default "active"
  member_id: string | null;
  service_only: boolean;
};
```

URL：`/admin/allocations?status=active&member_id=xxx&service_only=true`

---

## 8. Admin Usage filter state

**決策**：date range 用 `from` / `to` ISO date 字串放 URL；
`group_by` ∈ {member, allocation, model}；`service_only` boolean。

```ts
type UsageFilters = {
  from: string;  // ISO date YYYY-MM-DD
  to: string;
  group_by: "member" | "allocation" | "model";
  service_only: boolean;
};
```

Default from = today - 30 days；to = today。

---

## 9. shadcn 元件 commit 策略

延續 3b.0/3b.1 模式 — hand-write from defaults。本階段 8 個元件：

| 元件 | Radix dep | 用途 |
|---|---|---|
| table | 無 | members / allocations / usage / rebalance-log 列表 |
| dialog | `@radix-ui/react-dialog` | 新建 / patch dialog |
| alert-dialog | `@radix-ui/react-alert-dialog` | 確認刪除 / 撤回 |
| dropdown-menu | `@radix-ui/react-dropdown-menu` | row actions |
| form | 無（包 react-hook-form Provider） | 標準化欄位 + 錯誤呈現 |
| select | `@radix-ui/react-select` | provider / group_by 下拉 |
| textarea | 無 | note 欄位 |
| popover | `@radix-ui/react-popover` | date picker base |

---

## 10. Member service `set_is_admin` audit

**決策**：兩個新 audit event：
- `member_promoted` — 升 admin 時記錄（target=member, actor=token holder or member）
- `member_demoted` — 降時記錄

由 service 層在 set_is_admin() 內呼叫 `audit.record()`。

---

## 11. /me response 加 is_admin

**決策**：既有 `_member_public` 加一個欄位：

```python
def _member_public(m: Member) -> dict[str, Any]:
    return {
        "id": m.id,
        "email": m.email,
        "provider": m.provider,
        "display_name": m.display_name,
        "status": m.status,
        "is_admin": m.is_admin,  # 新增
    }
```

既有 /me 測試不會破（增加欄位是 backwards compat）。

---

## 12. 前端 useAuth Member 型別

**決策**：

```ts
export type Member = {
  id: string;
  email: string;
  display_name?: string | null;
  provider?: string;
  status?: string;
  is_admin?: boolean;  // 新增；optional 容錯舊 backend 沒回此欄
};
```

`<AppShell>` 與 `<AdminRoute>` 用 `member?.is_admin === true` 嚴格比較。

---

## 13. NEEDS CLARIFICATION

無未決。
