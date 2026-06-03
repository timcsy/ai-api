# Frontend Architecture (Phase 3b.0+)

## Overview

| Component | Tech |
|---|---|
| SPA framework | React 19 + Vite 6 + TypeScript (strict) |
| Routing | React Router v7 |
| Data fetching | TanStack Query v5 |
| UI primitives | shadcn/ui (Radix + Tailwind v3) |
| Tests | Vitest + RTL + jsdom |
| Build artifact | static bundle in `frontend/dist/` |
| Production serving | nginx:1.27-alpine pod |
| Routing fabric | K8s Ingress (path-based) |

## Path-based routing

The Ingress directs traffic to backend or frontend based on URL prefix:

| Path | Service |
|---|---|
| `/health` | backend |
| `/auth/` | backend |
| `/me/` | backend |
| `/admin/` | backend |
| `/catalog/` | backend |
| `/v1/` | backend |
| `/` (anything else) | frontend (nginx pod) |

The frontend nginx config uses `try_files $uri $uri/ /index.html;` so the
React Router can pick up the URL on hard-refresh / direct link.

## Auth flow

1. SPA boots → `AuthProvider` calls `GET /me` (with `credentials: include`)
2. 200 → `status = "authenticated"`, member set
3. 401 → `status = "unauthenticated"`, dispatch `api:unauthorized`
4. Any subsequent API 401 → dispatches the same event → context resets without
   each call-site needing to handle it
5. Login is either:
   - `POST /auth/local/login` (email + password)
   - `GET /auth/oidc/start` → Google OIDC redirect cycle

The session cookie (`ai_api_session`) is HttpOnly + SameSite=None+Secure
(when CORS_ORIGINS is non-empty) — see Phase 3a backend behaviour.

## SameSite / cross-origin notes

Two deployment modes:

| Mode | SameSite | Secure |
|---|---|---|
| backend on same host as frontend (Ingress path routing) | Lax | optional |
| backend on different host (api.example.com / app.example.com) | **None** | **required** |

The backend toggles this dynamically based on `cors_origins` setting. SPA
itself does nothing special — `fetch(..., { credentials: "include" })` works
in both modes.

## Local dev: Vite proxy

`vite.config.ts` proxies the 6 backend prefixes to `localhost:8000`. SPA fetches
`/me` directly (relative URL), Vite forwards. **No CORS needed for local dev.**

## Deployment

Two images, two Deployments, one Ingress:

```bash
helm install ai-api deploy/helm/ai-api \
  --set image.repository=ghcr.io/timcsy/ai-api \
  --set image.tag=sha-deadbeef \
  --set frontend.enabled=true \
  --set frontend.image.tag=sha-deadbeef \
  --set ingress.enabled=true \
  --set ingress.host=aiapi.example.com
```

`frontend.enabled` and `ingress.enabled` default to `false` so existing
backend-only installs do not break.

## Testing strategy

| Layer | Tool | Scope (Phase 3b.0) |
|---|---|---|
| Unit | Vitest | api-client, auth-context, ProtectedRoute, login form, sanitizeNext |
| Component | Vitest + RTL | 5 test files, 21 tests |
| Integration | manual `npm run dev` | login flow end-to-end |
| E2E | Playwright | **deferred to Phase 3b.7** |

## Future phases

- 3b.1 member view (allocations, /me detail)
- 3b.2 admin: members + allocation CRUD
- 3b.3 admin: usage dashboard + CSV/JSON export
- 3b.4 admin: quota-pool monitor + manual trigger
- 3b.5 admin: catalog browse
- 3b.6 admin: RebalanceLog viewer
- 3b.7 Playwright E2E + final polish

## RWD 規範（階段 16）

桌機優先設計，但手機（最小 360px）也須順手。詳見 `specs/025-mobile-rwd/`。

**斷點策略（沿用 Tailwind 預設）**：
- 多欄資訊／表單／工具列：base 單欄或可換行，桌機版面掛 `sm:`（640px）——`grid-cols-1 sm:grid-cols-N`、`flex-wrap`。
- 導覽收合與寬表格卡片化：以 `md:`（768px）為界。
- 360–414px 手機全部 < sm，所以改動皆為「在更小斷點新增手機行為」，桌機斷點 class 不動 → 桌機零回歸。

**寬表格 → 手機卡片（單一機制，避免 drift）**：
- `index.css` 的 `.responsive-table`：`< md` 時 `thead` 隱藏、每列變卡片、每格 `data-label` 顯示欄名。
- 用法：`<Table className="responsive-table">` + 每個 body `<TableCell data-label="欄名">`。
- CSS 用 **child combinator**（`> tbody > tr > td`）只作用頂層表格，巢狀表（如 tag 下鑽）不受影響。
- 契約測試：`__tests__/responsive-tables.test.tsx` 斷言每 body 格帶 `data-label`。

**手機導覽**：`app-shell.tsx` 以 `useIsMobile()`（`hooks/use-mobile.ts`，matchMedia）切換——`< md` 顯示漢堡 + `Sheet` 抽屜（含全部目的地），`≥ md` 維持 inline 橫排。`ui/sheet.tsx` 基於既有 `@radix-ui/react-dialog`（零新依賴）。

**CJK 字字斷行防範（核心教訓）**：中文無空格，flex 子項被壓到比內容窄時會逐字換行成直條。凡橫排含中文：`whitespace-nowrap` + 容器 `min-w-0`，或讓父層 `flex-wrap`。長字串（email/slug/URL/指紋）用 `truncate`（配 `min-w-0`）或 `break-all`。

**測試分工**：有 DOM 行為（導覽收合、表格 data-label）走 vitest 先 Red 後 Green；純視覺（溢出/折行）jsdom 無版面引擎，以 `specs/025-mobile-rwd/quickstart.md` 的 360px 手動清單驗收。
