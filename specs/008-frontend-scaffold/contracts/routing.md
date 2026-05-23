# Routing Contract — Phase 3b.0

本階段的「契約」是 path-based routing 與 SPA fallback 行為。

## Ingress 規則（生產環境）

| Path 前綴 | 目的地 service | 備註 |
|---|---|---|
| `/health` | `ai-api` (backend) | health check |
| `/auth/` | `ai-api` (backend) | login/logout/OIDC |
| `/me/` | `ai-api` (backend) | member self-service |
| `/admin/` | `ai-api` (backend) | admin APIs |
| `/catalog/` | `ai-api` (backend) | model catalog |
| `/v1/` | `ai-api` (backend) | proxy chat completions |
| 其他 `/*` | `ai-api-frontend` (nginx) | SPA |

Ingress controller：ingress-nginx；path type 用 `Prefix`。

## nginx SPA fallback（frontend pod 內）

| Path | 行為 |
|---|---|
| `/assets/<hash>.<ext>` | 直接服務 static asset；1 年 cache |
| `/index.html` | 服務 SPA entry |
| 其他 | `try_files $uri $uri/ /index.html` — 讓前端 router 接 |

## Vite dev proxy（本機開發）

SPA on `http://localhost:5173`，proxy 後端 prefix 到 `http://localhost:8000`：

```ts
"/auth": "http://localhost:8000",
"/me": "http://localhost:8000",
"/admin": "http://localhost:8000",
"/catalog": "http://localhost:8000",
"/v1": "http://localhost:8000",
"/health": "http://localhost:8000",
```

## 安全 headers（nginx）

| Header | Value | 理由 |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | 防 MIME sniff |
| `X-Frame-Options` | `DENY` | 防 clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 隱私 |

CSP 留 3b.1+ 細化（首版避免阻擋 dev 體驗）。

## Frontend Router Manifest（React Router v7）

| 路徑 | 元件 | 保護 |
|---|---|---|
| `/login` | `LoginPage` | 公開 |
| `/` | `HomePage`（placeholder）| `ProtectedRoute` |
| `*` | `NotFoundPage` | 公開 |

`/` 是 placeholder；3b.1+ 才掛實際業務頁面。
