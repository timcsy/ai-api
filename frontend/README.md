# ai-api Frontend (Phase 3b.0 scaffold)

React 19 + Vite 6 + TypeScript + TanStack Query + shadcn/ui。

本階段只交付骨架（login / placeholder home / 404）；業務頁面（usage、allocations、
catalog UI 等）留 3b.1+。

## 本機開發

```bash
nvm use            # 切到 Node 20 (.nvmrc)
npm install
npm run dev        # http://localhost:5173
```

Vite 自動 proxy 後端 prefix（`/health`, `/auth`, `/me`, `/admin`, `/catalog`,
`/v1`）到 `localhost:8000` — 本機開發不需開 CORS。

## 與後端整合

```bash
# Terminal A: 後端
uv run uvicorn ai_api.main:app --port 8000

# Terminal B: 建一個 local member
export ADMIN=local-dev-admin-only
curl -X POST http://localhost:8000/admin/members \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"alice@x.com","provider":"local_password","initial_password":"VerySafePass123","send_invitation":false}'

# Terminal C: 訪 http://localhost:5173 → 登入 → 看 placeholder
```

## CI / 品質 gate

```bash
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm test -- --run  # vitest（21 tests）
npm run build      # vite build → dist/
npm run test:cov   # coverage report
```

## 結構

```
src/
├── lib/api-client.ts          # fetch wrapper (credentials: include, 401 event)
├── contexts/auth.tsx          # AuthProvider + useAuth
├── components/
│   ├── protected-route.tsx
│   └── ui/                    # shadcn (button, input, label, card, alert)
├── routes/
│   ├── login.tsx              # local + Google OIDC
│   ├── home.tsx               # placeholder protected
│   └── not-found.tsx
└── __tests__/                 # vitest unit/integration
```

## 部署

獨立 nginx pod；image 由 `deploy/docker/Dockerfile.frontend` build。Helm 走
`frontend.enabled=true`；Ingress 路徑路由將 backend prefix 導向 backend service，
其他導向 frontend service。詳見 `docs/frontend.md`。
