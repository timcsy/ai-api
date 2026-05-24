# Phase 0 Research: 階段 3b.1 — Member View

---

## 1. Backend `/me/allocations/{id}/calls` 擴充

**驗證來源**：`src/ai_api/services/records.py:56-71`

```python
async def list_for_allocation(
    self,
    allocation_id: str,
    limit: int = 100,
    before: str | None = None,
) -> list[CallRecord]:
    stmt = (
        select(CallRecord)
        .where(CallRecord.allocation_id == allocation_id)
        .order_by(CallRecord.started_at.desc(), CallRecord.id.desc())
        .limit(limit)
    )
    if before:
        stmt = stmt.where(CallRecord.id < before)
```

Service **已支援 limit + before**！本階段只需修 `src/ai_api/api/me.py` 透傳
query params + response 包裝 `next_before_id`。

**決策**：
- `limit`: default 20、min 1、max 100；用 FastAPI `Query(20, ge=1, le=100)`
- `before_id`: optional str
- response shape: `{"items": [...], "next_before_id": str | null}`（**改變**
  原 endpoint shape from list 為 dict）— 前端會用 useInfiniteQuery 接

**Breaking change**：原 endpoint 回 `list[dict]`，改成 `dict`。檢視：
- frontend 尚未使用此 endpoint（3b.0 沒做）
- 其他 backend test 用此 endpoint？grep 確認

**Migration**：直接破壞性改。檢查 `tests/contract/` 找用此端點的測試。

---

## 2. URL ↔ Filter State 同步

**決策**：custom hook `useCatalogFilters()` 內部用 `useSearchParams`：

```ts
type CatalogFilters = {
  capability: string[];
  modality_input: string[];
  modality_output: string[];
  recommended_for: string[];
  cost_tier: string | null;
  include_deprecated: boolean;
};

export function useCatalogFilters() {
  const [params, setParams] = useSearchParams();
  const filters: CatalogFilters = {
    capability: params.getAll("capability"),
    modality_input: params.getAll("modality_input"),
    modality_output: params.getAll("modality_output"),
    recommended_for: params.getAll("recommended_for"),
    cost_tier: params.get("cost_tier"),
    include_deprecated: params.get("include_deprecated") === "true",
  };
  const toggle = (key, value) => { ... setParams(next); };
  const setSingle = (key, value) => { ... };
  return { filters, toggle, setSingle, clear };
}
```

**理由**：URL 是 single source of truth；不維護 React state；TanStack Query
key 直接 derive 自 filters。重新整理、複製 URL、瀏覽器 back/forward 全部
work。

**已評估**：
- React state + sync to URL effect：常見 bug 來源（雙向同步）
- 全部 query string 自己拼：失去 useSearchParams 的 history integration

---

## 3. TanStack Query 整合策略

**決策**：

| Query | hook | key | options |
|---|---|---|---|
| `/me` | useQuery | `["me"]` | 沿用 3b.0 AuthContext |
| `/me/allocations` | useQuery | `["me", "allocations", { include_revoked }]` | staleTime 60s |
| `/me/allocations/{id}/calls` | useInfiniteQuery | `["me", "allocations", id, "calls"]` | getNextPageParam → `next_before_id` |
| `/catalog/models` (filtered) | useQuery | `["catalog", "models", filters]` | staleTime 5min |
| `/catalog/filters` | useQuery | `["catalog", "filters", { include_deprecated }]` | staleTime 5min |
| `/catalog/models/{slug}` | useQuery | `["catalog", "model", slug]` | staleTime 5min |

**logout 時**：`queryClient.clear()`（FR-027）— 不只是 invalidate，是 clear
所有 cache。

---

## 4. `useInfiniteQuery` for cursor pagination

**決策**：

```ts
useInfiniteQuery({
  queryKey: ["me", "allocations", id, "calls"],
  queryFn: ({ pageParam }) =>
    api<CallsPage>(`/me/allocations/${id}/calls?limit=20${pageParam ? `&before_id=${pageParam}` : ""}`),
  initialPageParam: null as string | null,
  getNextPageParam: (lastPage) => lastPage.next_before_id,
});
```

UI 顯示 `data.pages.flatMap(p => p.items)`；「載入更多」按鈕呼叫 `fetchNextPage()`；
按鈕在 `hasNextPage === false` 時隱藏。

**已評估**：
- offset pagination：不適合 mutable 資料（新 call 插入會導致重複/漏）
- 一次拉全部：spec FR-014 已決定 cursor

---

## 5. Clipboard API + fallback

**決策**：

```ts
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}
```

UI 層：呼叫後若回 false，**不**自動 fallback 到 textarea hack（複雜且
unreliable）— 改為顯示「請手動複製」+ 整段文字在 `<pre>` 可被 select。

**理由**：
- 大多數 modern browser 在 HTTPS / localhost 都 work
- HTTP 環境是 dev edge case（生產走 HTTPS）
- textarea + execCommand("copy") 已 deprecated

---

## 6. shadcn 新元件需求

**決策**：7 個新元件（hand-write from defaults，3b.0 模式）：

| 元件 | 用途 | Radix dep |
|---|---|---|
| `badge` | status / family / cost_tier 標籤 | 無 |
| `progress` | quota progress bar | `@radix-ui/react-progress` |
| `tabs` | catalog detail curl/JSON 切換 | `@radix-ui/react-tabs` |
| `separator` | header 區隔 | `@radix-ui/react-separator` |
| `scroll-area` | filter sidebar 高度限制 | `@radix-ui/react-scroll-area` |
| `checkbox` | facet 多選 | `@radix-ui/react-checkbox` |
| `switch` | include_revoked / include_deprecated | `@radix-ui/react-switch` |
| `toast` + `toaster` + `use-toast` | 複製 curl 成功提示、錯誤 | `@radix-ui/react-toast` |

新增的 npm deps（7 個 Radix primitives）統一安裝；commit 元件 .tsx。

---

## 7. AppShell layout

**決策**：

```tsx
export function AppShell() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />  {/* React Router */}
      </main>
    </div>
  );
}
```

Header 含 nav links + member email + logout。所有 ProtectedRoute 子節點包在
`<AppShell>` 內：

```tsx
<Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
  <Route path="/dashboard" element={<Dashboard />} />
  <Route path="/dashboard/allocations/:id" element={<AllocationDetail />} />
  <Route path="/catalog" element={<Catalog />} />
  <Route path="/catalog/:slug" element={<CatalogDetail />} />
</Route>
```

**理由**：避免每個 protected route 自己 render header。`Outlet` 是 React
Router v7 標準模式。

---

## 8. Dashboard「上月 token 摘要」資料來源

**驗證**：grep `/me/allocations` 後端 response shape：

```python
# tests/contract/test_me_endpoints.py 推測 — 待確認
```

**決策**：
- 先讀現有 endpoint 回傳是否含 token 摘要
- **若沒有** → dashboard 只顯示 allocation 名單 + 連結到 detail（detail 才
  顯示 token）；不擴後端
- **若有** → 直接展示

**Fallback**：spec assumption 已允許「需查詢細節」的退化呈現。

---

## 9. URL slug routing for `/catalog/:slug`

**決策**：catalog slug 含 `/`（如 `azure/gpt-4o-mini`）— 用 React Router v7
splat：

```tsx
<Route path="/catalog/:slug" element={<CatalogDetail />} />
// useParams<{ slug: string }>().slug → 自動 decode URL-encoded
```

對 backend 也要傳 URL-encoded slug。

**已評估**：
- 拆 `/catalog/:provider/:name`：與 backend slug 慣例不一致
- query param `?slug=`：違 REST

---

## 10. logout `queryClient.clear()` 集成

**決策**：`AuthProvider` 接受 optional `queryClient` 參數；logout 時呼叫
`clear()`：

```tsx
export function AuthProvider({ children, queryClient }: Props) {
  // ...
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST" }); }
    finally {
      queryClient?.clear();
      setMember(null);
      setStatus("unauthenticated");
    }
  };
}
```

App.tsx 把 `queryClient` 傳給 AuthProvider。

**已評估**：
- 在 logout 內部 `useQueryClient()`：hooks 規則限制
- 全域單例 import：testable 較差

---

## 11. 設計 `next_before_id` 計算邏輯

**決策**：後端 endpoint 行為：

```python
records = await service.list_for_allocation(id, limit=limit + 1, before=before_id)
has_more = len(records) > limit
items = records[:limit]
next_before_id = items[-1].id if has_more else None
return {"items": [serialize(r) for r in items], "next_before_id": next_before_id}
```

**理由**：拉 limit+1 筆判斷是否還有更多；只回 limit 筆給 client；
`next_before_id` 是最後一筆的 id（cursor）。

---

## 12. NEEDS CLARIFICATION

無未決。
