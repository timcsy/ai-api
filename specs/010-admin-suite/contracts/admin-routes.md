# Admin UI Routes Contract — Phase 3b.2

## Route table

| Path | Component | Guards | Backend deps |
|---|---|---|---|
| `/admin` | `<Navigate to="/admin/members">` | ProtectedRoute + AdminRoute | — |
| `/admin/members` | AdminMembersPage | ProtectedRoute + AdminRoute | GET /admin/members, POST /admin/members, PATCH, DELETE |
| `/admin/allocations` | AdminAllocationsPage | ProtectedRoute + AdminRoute | GET /admin/allocations, POST, PATCH, DELETE |
| `/admin/usage` | AdminUsagePage | ProtectedRoute + AdminRoute | GET /admin/usage, GET /admin/usage.csv, GET /admin/usage.json |
| `/admin/quota-pool` | AdminQuotaPoolPage | ProtectedRoute + AdminRoute | GET /admin/quota-pool/status, POST /admin/quota-pool/rebalance, GET /admin/quota-pool/rebalance-log |
| `/admin/rebalance-log` | AdminRebalanceLogListPage | ProtectedRoute + AdminRoute | GET /admin/quota-pool/rebalance-log |
| `/admin/rebalance-log/:id` | AdminRebalanceLogDetailPage | ProtectedRoute + AdminRoute | GET /admin/quota-pool/rebalance-log/{id} |
| `/admin/catalog` | CatalogPage (reused from 3b.1) | ProtectedRoute + AdminRoute | GET /catalog/models, /catalog/filters |
| `/admin/catalog/*` | CatalogDetailPage (reused) | ProtectedRoute + AdminRoute | GET /catalog/models/{slug} |

## AdminRoute behavior

```tsx
function AdminRoute() {
  const { status, member } = useAuth();
  if (status === "loading") return <FullPageSpinner />;
  if (member?.is_admin !== true) {
    return (
      <div className="...">
        <h1>無權限查看</h1>
        <p>此頁面僅供管理員存取</p>
        <Button asChild><Link to="/dashboard">回首頁</Link></Button>
      </div>
    );
  }
  return <Outlet />;
}
```

Note: 不 redirect — 保持 member 的登入 session 不中斷。

## Header nav addition

`<AppShell>` 在 Catalog 連結之後條件性加入 `Admin` 連結：

```tsx
{member?.is_admin && (
  <NavLink to="/admin" className={navLinkClass}>
    Admin
  </NavLink>
)}
```

## Data fetching conventions

| Query | Key | staleTime | invalidateOn |
|---|---|---|---|
| List members | `["admin", "members"]` | 30s | create / update / delete |
| List allocations | `["admin", "allocations", filters]` | 30s | create / patch / revoke |
| Usage data | `["admin", "usage", filters]` | 60s | filter change |
| Pool status | `["admin", "quota-pool", "status"]` | 30s | manual rebalance |
| Pool rebalance log | `["admin", "quota-pool", "log"]` | 30s | manual rebalance |
| Rebalance log detail | `["admin", "quota-pool", "log", id]` | 5min | never (immutable) |

## Empty / error states (UX contract)

| 場景 | UX |
|---|---|
| 401 | api:unauthorized event → AuthContext reset → redirect /login |
| 403 (not admin) | AdminRoute 內嵌「無權限」 |
| 403 (forbidden specific resource) | Toast error |
| 404 | Inline 「找不到」 + 回上頁連結 |
| 5xx | Toast error + 重試按鈕 (if applicable) |
| Mutation 409 (last admin / duplicate email etc) | Toast error，dialog 不關 |
