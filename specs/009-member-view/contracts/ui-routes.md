# UI Routes Contract — Phase 3b.1

## Route table

| Path | Component | Guard | Layout |
|---|---|---|---|
| `/login` | LoginPage | 公開 | bare |
| `/` | redirect → `/dashboard` | ProtectedRoute | bare |
| `/dashboard` | Dashboard | ProtectedRoute | AppShell |
| `/dashboard/allocations/:id` | AllocationDetail | ProtectedRoute | AppShell |
| `/catalog` | Catalog | ProtectedRoute | AppShell |
| `/catalog/:slug` | CatalogDetail | ProtectedRoute | AppShell |
| `*` | NotFoundPage | 公開 | bare |

## Backend dependencies per route

| Route | Backend calls | New endpoint? |
|---|---|---|
| `/dashboard` | `GET /me`, `GET /me/allocations` | 無 |
| `/dashboard/allocations/:id` | `GET /me/allocations`, `GET /me/allocations/{id}/calls?limit=20&before_id=<x>` | **是**（擴 cursor）|
| `/catalog` | `GET /catalog/models?<filters>`, `GET /catalog/filters` | 無 |
| `/catalog/:slug` | `GET /catalog/models/{slug}` | 無 |

## Backend endpoint contract change (FR-001)

### Before (Phase 2)

```http
GET /me/allocations/{allocation_id}/calls
Response 200: list[CallRecord]
```

### After (Phase 3b.1)

```http
GET /me/allocations/{allocation_id}/calls?limit=20&before_id=<id>
Response 200: {
  "items": [CallRecord, ...],
  "next_before_id": "<id>" | null
}
```

**Breaking change**: response shape from list → dict。前端尚未使用，所以
backend test 是唯一 caller。

**Query parameters**:
- `limit`: int, default 20, min 1, max 100
- `before_id`: optional str (cursor pointing to a CallRecord.id)

**Cursor semantics**:
- Records sorted by `started_at DESC, id DESC`
- `before_id=<x>` returns records with id strictly less than `<x>`
- `next_before_id` is the id of the last item in current page (use as cursor
  for next page), or `null` if no more.

**Error responses**: unchanged (404 not_found / 403 forbidden 同 Phase 2)

## URL ↔ Filter state contract

`/catalog` 的 URL query string 是 filter state 的 single source of truth。

| URL param | Filter | Backend mapping |
|---|---|---|
| `capability=A&capability=B` | capabilities AND [A, B] | 直接傳 `capability` repeat |
| `modality_input=text` | modality_input [text] | `modality_input` repeat |
| `cost_tier=low` | cost_tier single | 直接傳 |
| `include_deprecated=true` | include_deprecated bool | 直接傳 |

shadcn checkbox 變動時：
1. 改 URL（useSearchParams.setSearchParams）
2. URL 變 → TanStack Query key 變 → 自動重 fetch
3. 結果 grid 更新

**不要**用 React state mirror URL。

## Empty / loading / error states (UX contract)

| 場景 | UX |
|---|---|
| Loading | shadcn skeleton 或 spinner（≤ 200ms 顯示） |
| Empty (0 results) | 友善訊息 + 建議下一步 |
| 401 | 自動觸發 api:unauthorized event（3b.0 已處理） |
| 403 | 「無權限查看」+ 回首頁連結 (**不**跳 login) |
| 404 | 「找不到」內嵌（**不**用全域 NotFound） |
| 5xx | toast 顯示錯誤 + 重試按鈕 |
