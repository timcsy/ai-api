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
