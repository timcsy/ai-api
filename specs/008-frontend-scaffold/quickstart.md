# Quickstart: 階段 3b.0 — Frontend Scaffold

## 0. 先決條件

- Node 20 LTS（用 `nvm use` 或 `fnm`）
- 後端 dev server 在 `localhost:8000` 跑著
- `.env` 設 `CORS_ORIGINS=["http://localhost:5173"]`（可選；vite proxy 已避開
  CORS）

## 1. 本機跑前端（US1）

```bash
cd frontend
nvm use  # 讀 .nvmrc 切到 Node 20
npm install
npm run dev
# 啟動於 http://localhost:5173
```

## 2. 本機建一個 local member 並登入（手動）

```bash
# Terminal A: backend
uv run uvicorn ai_api.main:app --port 8000

# Terminal B: 建 admin token + 建 member
export ADMIN=local-dev-admin-only
curl -X POST http://localhost:8000/admin/members \
  -H "X-Admin-Token: $ADMIN" -H 'Content-Type: application/json' \
  -d '{"email":"alice@x.com","provider":"local_password","initial_password":"VerySafePass123","send_invitation":false}'

# Terminal C: 瀏覽器訪 http://localhost:5173
# → 應該被導向 /login
# → 填 alice@x.com + VerySafePass123
# → 登入後看到「Hello, alice@x.com」+ Logout 按鈕
```

## 3. CI gates（自動跑）

```bash
cd frontend
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run build      # vite build
npm test -- --run  # vitest unit tests（5+ 個）
```

預期：4 個指令全綠。

## 4. nginx image build（手動驗證）

```bash
# 從 repo root
docker build -f deploy/docker/Dockerfile.frontend -t ai-api-frontend:dev .
docker run --rm -p 8080:80 ai-api-frontend:dev
# 訪 http://localhost:8080 → 看到 SPA login 頁
```

## 5. Helm template 驗證

```bash
# Ingress disabled 是預設；既有 install 不壞
helm template deploy/helm/ai-api/ \
  --set image.repository=ghcr.io/timcsy/ai-api \
  --set image.tag=sha-deadbeef \
  --set frontend.image.repository=ghcr.io/timcsy/ai-api-frontend \
  --set frontend.image.tag=sha-deadbeef \
  | head -100

# 開啟 Ingress 驗證 path routing 規則
helm template deploy/helm/ai-api/ \
  --set ingress.enabled=true \
  --set ingress.host=aiapi.example.com \
  --set image.repository=ghcr.io/timcsy/ai-api \
  --set image.tag=sha-deadbeef \
  --set frontend.image.repository=ghcr.io/timcsy/ai-api-frontend \
  --set frontend.image.tag=sha-deadbeef \
  | grep -A 20 'kind: Ingress'
```

## 6. K8s 部署（叢集驗證，可選）

```bash
# 推 image（CI 處理；本地測試可手動）
helm install ai-api deploy/helm/ai-api/ \
  --set image.tag=sha-deadbeef \
  --set frontend.image.tag=sha-deadbeef \
  --set ingress.enabled=true \
  --set ingress.host=aiapi.example.com

# 訪 ingress host → 應看到 SPA；login 流程同 §2
```

## 7. SC 檢核

| SC | 對應步驟 |
|---|---|
| SC-001 | §1 `npm run dev` 啟動成功 |
| SC-002 | §2 local password 登入流程通過 |
| SC-003 | 同 §2 + 點 Google login → redirect 流程通過 |
| SC-004 | §3 typecheck + build 全綠 |
| SC-005 | CI Trivy gate（fs + image + SBOM）對 frontend image 通過 |
| SC-006 | §5 `helm template` 無誤；Ingress disabled 時無 Ingress object |
| SC-007 | `uv run pytest -q` 既有 194 backend 全綠 + `npm test` ≥ 5 個前端 unit 全綠 |
| SC-008 | `git log -- frontend/src/__tests__/ frontend/src/` 順序 test < impl |
