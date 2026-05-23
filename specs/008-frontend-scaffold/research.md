# Phase 0 Research: 階段 3b.0 — Frontend Scaffold

---

## 1. Backend route prefix 集合（FR-018 的 ⚠️）

**驗證來源**：`src/ai_api/main.py:56-66`

```
/health（無 prefix）
/auth/*
/me/*
/admin/*    (allocations, records, members, access, usage, quota-pool)
/catalog/*
/v1/*       (proxy)
```

**Ingress 路由規則**：

| Path | 目的地 |
|---|---|
| `/health` | backend |
| `/auth/` | backend |
| `/me/` | backend |
| `/admin/` | backend |
| `/catalog/` | backend |
| `/v1/` | backend |
| `/` (其他) | frontend (nginx) |

> **`/api/*` 不在後端 prefix 內**；spec 原本提到「/api/*」是慣例性概念，
> 實際 backend 路由就是上述 6 個 prefix；spec 階段的 ⚠️ 已解析。

---

## 2. `/auth/logout` 已存在

**驗證來源**：`src/ai_api/api/auth.py:1` docstring 明列
「`/auth/oidc/*, /auth/local/login, /auth/logout, /auth/invitation/*`」。

**結論**：本階段不需動後端；前端直接 POST `/auth/logout`。

---

## 3. shadcn/ui 安裝模式

**決策**：用 CLI `npx shadcn@latest init` + `npx shadcn@latest add <component>`；
生成的 .tsx 直接 commit。不裝 npm 套件，避免「整包升級壞掉」。

**首版加的元件**（最小集合）：
- `button` — login submit、logout
- `input` — email/password input
- `label` — form label
- `card` — login form container
- `alert` — error message 顯示

**理由**：shadcn 的設計哲學就是「copy-paste」而非依賴；版本可控。

---

## 4. API client 設計

**決策**：超薄 fetch wrapper（不引入 axios）：

```ts
// src/lib/api-client.ts
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",        // 帶 session cookie
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = body?.error || {};
    if (res.status === 401) {
      // 觸發 auth context 清狀態（透過 event 或 callback）
      window.dispatchEvent(new Event("api:unauthorized"));
    }
    throw new ApiError(res.status, err.code || "unknown", err.message || res.statusText);
  }
  return res.json();
}
```

**理由**：
- fetch 原生足夠；axios 是負債
- 401 事件解耦 — auth context 自己 listen，不必每個 API 呼叫都注入 context
- TanStack Query 用 `api()` 當 fetcher 即可

---

## 5. AuthContext 設計

**決策**：

```tsx
type Status = "loading" | "authenticated" | "unauthenticated";
interface AuthCtx {
  status: Status;
  member: Member | null;
  login(email: string, password: string): Promise<void>;
  loginGoogle(): void;                       // redirect, 不回 Promise
  logout(): Promise<void>;
  refresh(): Promise<void>;                  // 重新呼叫 /me
}
```

啟動時：
1. status = "loading"
2. fetch `/me` → 200 → status="authenticated"，set member
3. 任何錯誤 → status="unauthenticated"

`window.addEventListener("api:unauthorized")` → status="unauthenticated"，
member=null，跳 `/login?next=<current>`。

**理由**：把 401 處理收斂到一處；任何 API 呼叫只要 throw ApiError 就會自動觸發。

---

## 6. ProtectedRoute 設計

```tsx
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullPageSpinner />;
  if (status === "unauthenticated") {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <>{children}</>;
}
```

**`next` 安全規則**：login 頁讀 `next` 時驗證
- 必須以 `/` 開頭
- 不能以 `//` 開頭（防 protocol-relative URL）
- 不能含 `\` 或 control char

不通過則 fallback 到 `/`。

---

## 7. Vite proxy（dev 環境）

**決策**：`vite.config.ts` 設 proxy：

```ts
server: {
  port: 5173,
  proxy: {
    "/auth": "http://localhost:8000",
    "/me": "http://localhost:8000",
    "/admin": "http://localhost:8000",
    "/catalog": "http://localhost:8000",
    "/v1": "http://localhost:8000",
    "/health": "http://localhost:8000",
  },
},
```

**理由**：本機開發時 SPA 在 5173、backend 在 8000；vite proxy 讓 SPA 直接
fetch `/auth/...` 而非 `http://localhost:8000/auth/...`，**避免本機 dev 必須
打開 CORS**。生產走 Ingress 路由分流，跨 host 才走 CORS。

---

## 8. nginx 設定

**決策**：`deploy/nginx/default.conf`：

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 靜態檔長期 cache
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 一切其他 path 都回 index.html，讓前端 router 接手
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**理由**：標準 SPA fallback；`/assets/` 由 Vite build 出時有 hash 名稱，
適合長期 cache；其他 path 走 SPA router。

---

## 9. Dockerfile.frontend (multi-stage)

**決策**：

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Serve stage
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**已評估**：
- 用 distroless：nginx 沒官方 distroless image；alpine 已夠輕量
- 用 caddy：太多後端不需的功能；nginx 標準
- node serve：增加 attack surface

---

## 10. CI workflow 結構

**決策**：新 `.github/workflows/frontend.yml`：

```yaml
on:
  push:
    branches: [main]
    paths: [frontend/**, .github/workflows/frontend.yml]
  pull_request:
    paths: [frontend/**, .github/workflows/frontend.yml]
jobs:
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>
      - uses: actions/setup-node@<sha>
        with: { node-version-file: frontend/.nvmrc, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm run typecheck
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
      - run: npm test -- --run
        working-directory: frontend
```

**理由**：path filter 讓 backend 改動不觸發；setup-node 內建 cache。

**image.yml 擴展**：用 matrix build 兩個 image（backend + frontend），或加
獨立 job。優先用 matrix 保持 workflow 簡潔。

---

## 11. Helm Ingress 預設 disabled

**決策**：`values.yaml`：

```yaml
ingress:
  enabled: false
  className: nginx
  host: aiapi.example.com
  tls:
    enabled: false
    secretName: ""
```

`templates/ingress.yaml` 用 `{{- if .Values.ingress.enabled }}` 包住。
**Production 必須手動 set `--set ingress.enabled=true --set ingress.host=...`**
才會建立 Ingress。

**理由**：FR-019 — 既有 install 不壞。Ingress controller 並非每個叢集都有。

---

## 12. 測試策略

| 層次 | 工具 | 範圍 |
|---|---|---|
| Unit | Vitest + jsdom | api-client、auth-context、protected-route、login form |
| Component | Vitest + RTL | 上述 + 404 fallback |
| Integration | manual dev server | 登入流程端到端（手動） |
| E2E | Playwright | **defer 3b.7** |

5 個 unit test 對應 SC-007。

---

## 13. NEEDS CLARIFICATION

無未決。spec 中 ⚠️ 已於 §1 解析。
