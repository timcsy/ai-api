# Tasks: 階段 3b.0 — Frontend Scaffold

**Input**: Design documents from `/specs/008-frontend-scaffold/`
**Prerequisites**: plan.md, spec.md, research.md, contracts/routing.md, quickstart.md

**Tests**: TDD enforced — Vitest unit + RTL；E2E 留 3b.7。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

### Scaffold + tooling

- [ ] T001 建立 `frontend/.nvmrc` 內容 `20`
- [ ] T002 `cd frontend && npm init -y` 建立 `package.json`；填寫 name=`ai-api-frontend`、private=true、type=module
- [ ] T003 `cd frontend && npm install` 主要依賴：`react@^19`、`react-dom@^19`、`react-router-dom@^7`、`@tanstack/react-query@^5`
- [ ] T004 `cd frontend && npm install -D` 開發依賴：`typescript@^5`、`vite@^6`、`@vitejs/plugin-react@^4`、`@types/react`、`@types/react-dom`、`@types/node`、`tailwindcss@^3`、`postcss`、`autoprefixer`、`tailwindcss-animate`、`eslint@^9`、`@typescript-eslint/parser`、`@typescript-eslint/eslint-plugin`、`eslint-plugin-react-hooks`、`eslint-plugin-react-refresh`、`vitest@^2`、`@vitest/coverage-v8`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`、`jsdom`、`prettier`
- [ ] T005 [P] 建立 `frontend/tsconfig.json` strict mode + bundler module；建立 `frontend/tsconfig.node.json`（給 vite.config）
- [ ] T006 [P] 建立 `frontend/vite.config.ts` 含 React plugin + dev proxy（依 research.md §7 6 個 prefix）
- [ ] T007 [P] 建立 `frontend/tailwind.config.ts` + `frontend/postcss.config.js` + `frontend/src/index.css`（tailwind base + components + utilities + shadcn CSS 變數）
- [ ] T008 [P] 建立 `frontend/eslint.config.js`（flat config）+ `frontend/.prettierrc.json`
- [ ] T009 [P] 在 `frontend/package.json` 加 scripts：`dev`、`build`、`preview`、`lint`、`typecheck` (`tsc --noEmit`)、`test`、`test:cov`
- [ ] T010 [P] 建立 `frontend/index.html` 空殼指向 `src/main.tsx`
- [ ] T011 [P] 建立 `frontend/.gitignore`（node_modules、dist、coverage、.vscode、.env*）
- [ ] T012 確認 `cd frontend && npm install && npm run typecheck && npm run build` 跑得起來（空殼也要綠）

### shadcn/ui

- [ ] T013 `cd frontend && npx shadcn@latest init`：選 default + Slate；產生 `components.json`、`src/lib/utils.ts`、`src/components/ui/` 初始化
- [ ] T014 `cd frontend && npx shadcn@latest add button input label card alert`：加 5 個基礎元件（commit 生成的 .tsx）

### Vitest config

- [ ] T015 [P] 建立 `frontend/vitest.config.ts` 與 vite.config 整合；jsdom 環境；setup file
- [ ] T016 [P] 建立 `frontend/src/__tests__/setup.ts`：`import "@testing-library/jest-dom"`；export reset hooks

**Checkpoint**：`npm run dev` 跑得起來（empty App）；`npm test` 無 fail（無測試）。

---

## Phase 2: Foundational

### API client + Auth context

- [ ] T017 建立 `frontend/src/lib/api-client.ts`：
  - `ApiError` class
  - `api<T>(path, init)` 帶 `credentials: 'include'`
  - 401 → `window.dispatchEvent(new Event("api:unauthorized"))`
  - 標準 error parse（`{error: {code, message}}`）

- [ ] T018 建立 `frontend/src/contexts/auth.tsx`：
  - `AuthProvider`：startup 呼叫 `GET /me` 水合；listen `api:unauthorized`
  - `useAuth()` exposing `{status, member, login, loginGoogle, logout, refresh}`
  - `login(email, pw)` → `POST /auth/local/login` → `refresh()`
  - `loginGoogle()` → `window.location.href = "/auth/oidc/start"` 之類（看實際 endpoint）
  - `logout()` → `POST /auth/logout` → set unauthenticated

### ProtectedRoute

- [ ] T019 建立 `frontend/src/components/protected-route.tsx`：
  - loading → spinner
  - unauthenticated → `<Navigate to={"/login?next=" + encoded path}>`
  - authenticated → `{children}`

### Router

- [ ] T020 建立 `frontend/src/App.tsx`：React Router v7 + AuthProvider + QueryClientProvider；3 個 routes（`/login`、`/`、`*`）

- [ ] T021 建立 `frontend/src/main.tsx`：mount App；StrictMode

**Checkpoint**：T017-T021 完成後 `npm run build` 仍要綠；尚無頁面。

---

## Phase 3: US1 — 本機可登入 (P1)

**Goal**：login / home / 404 三頁可運作；端到端 manual 跑得通。
**Independent Test**：手動 — `npm run dev` + 後端跑著 → login → 看 placeholder → logout。

### Tests First

- [ ] T022 [US1] 建立 `frontend/src/__tests__/api-client.test.ts`：
  - 200 → return body
  - 401 → throw ApiError 且觸發 `api:unauthorized` event
  - 5xx → throw ApiError 含 code 與 message
- [ ] T023 [US1] 建立 `frontend/src/__tests__/auth-context.test.tsx`：
  - initial `/me` 200 → status=authenticated
  - initial `/me` 401 → status=unauthenticated
  - login 成功 → refresh → status=authenticated
  - logout → status=unauthenticated
  - `api:unauthenticated` 事件 → status 自動 reset
- [ ] T024 [US1] 建立 `frontend/src/__tests__/protected-route.test.tsx`：
  - loading → 顯示 spinner
  - unauthenticated → 觸發 `<Navigate to=/login?next=...>`
  - authenticated → render children
- [ ] T025 [US1] 建立 `frontend/src/__tests__/login.test.tsx`：
  - submit 觸發 `login()`
  - 顯示 backend 回傳的錯誤訊息
  - `next` URL 安全驗證：拒絕 `//evil`、`http://evil`、`\evil`
- [ ] T026 [US1] 建立 `frontend/src/__tests__/not-found.test.tsx`：404 fallback 顯示「找不到頁面」+ 回首頁連結

### Impl

- [ ] T027 [US1] 建立 `frontend/src/routes/login.tsx`：
  - shadcn Card 包 form（email + password input + submit button）
  - Google login button → `loginGoogle()`
  - 錯誤訊息走 shadcn Alert
  - `next` query 參數安全驗證後 redirect
- [ ] T028 [US1] 建立 `frontend/src/routes/home.tsx`：
  - 「Hello, {member.email}」+ Logout button
  - 包在 `<ProtectedRoute>`
- [ ] T029 [US1] 建立 `frontend/src/routes/not-found.tsx`：minimal 404

**Checkpoint**：T022-T026 全綠 → T027-T029 實作 → 全綠。手動 `npm run dev`
跑端到端登入流程。

---

## Phase 4: US2 — K8s 部署可登入 (P1)

**Goal**：nginx image + Helm Ingress 路徑路由；deploy 後瀏覽器可登入。
**Independent Test**：`helm install` 後訪 ingress host → login → 兩種 provider 都通。

### nginx + Dockerfile

- [ ] T030 [US2] 建立 `deploy/nginx/default.conf` 依 research.md §8（SPA fallback + 安全 headers + assets 1y cache）
- [ ] T031 [US2] 建立 `deploy/docker/Dockerfile.frontend` multi-stage（research.md §9）

### Helm

- [ ] T032 [US2] 建立 `deploy/helm/ai-api/templates/frontend-deployment.yaml`：
  - 用 `.Values.frontend.image.{repository, tag}`
  - 安全 context: nonroot + readOnlyRootFilesystem + tmp emptyDir（沿用既有 backend pattern）
- [ ] T033 [US2] 建立 `deploy/helm/ai-api/templates/frontend-service.yaml`：ClusterIP port 80
- [ ] T034 [US2] 建立 `deploy/helm/ai-api/templates/ingress.yaml`：包 `{{ if .Values.ingress.enabled }}`；7 條 path-based rule（依 contracts/routing.md）
- [ ] T035 [US2] 更新 `deploy/helm/ai-api/values.yaml`：加 `frontend:` 與 `ingress:` 區段（後者預設 disabled）

### CI

- [ ] T036 [US2] 建立 `.github/workflows/frontend.yml` 依 research.md §10；所有 `uses:` pin commit SHA + 註解標 semver
- [ ] T037 [US2] 修改 `.github/workflows/image.yml`：加 frontend image build job（matrix 或獨立 job；Trivy fs + image + SBOM 三 gate 都跑）

**Checkpoint**：
- `helm template` 通過（兩種模式：ingress disabled / enabled）
- frontend image 通過 Trivy
- 可手動 `kubectl port-forward` 訪 SPA 並登入

---

## Phase 5: US3 — Smoke test (P2)

**Goal**：CI 跑 ≥ 5 個 Vitest 確保骨架完整。

說明：T022-T026 已涵蓋 5 個 unit test；本階段是 polish — 確保 CI 跑通 +
coverage 報告。

- [ ] T038 [US3] 確認 `frontend.yml` 跑 `npm test -- --run` 且 `≥ 5 passed`；失敗即 CI fail
- [ ] T039 [US3] 加 coverage：`npm run test:cov`（vitest --coverage）；CI 上傳 artifact，門檻不嚴格（覆蓋率報告供觀察）

---

## Phase 6: Polish

- [ ] T040 [P] `frontend/README.md`：本機跑、build、test、與後端整合說明
- [ ] T041 [P] `docs/frontend.md`：架構 + Ingress 規則 + nginx fallback 邏輯（人類閱讀）
- [ ] T042 [P] 跑既有 backend `uv run pytest -q` 確認 194 tests 不回歸
- [ ] T043 [P] 跑前端 `cd frontend && npm run lint && npm run typecheck && npm test && npm run build` 四綠
- [ ] T044 [P] 更新 `knowledge/vision.md`：階段 3b 拆成 3b.0~3b.7；標 3b.0 完成
- [ ] T045 PR 描述附 quickstart §1+§2+§3 執行紀錄

---

## Dependencies

```
Phase 1 (Setup: scaffold + shadcn + vitest config)
   │
   ▼
Phase 2 (Foundational: api-client + auth-context + ProtectedRoute + router)
   │
   ├─→ Phase 3 (US1 — login/home/404 unit tests + impl)
   │
   └─→ Phase 4 (US2 — nginx + Dockerfile + Helm + CI；不依賴 US1 內容，可並行)
        │
        ▼
   Phase 5 (US3 — smoke / coverage：依賴 US1 測試已存在 + US2 CI workflow)
        │
        ▼
   Phase 6 Polish
```

**Story dependencies**：
- US1 依賴 Phase 2 完整（auth context + ProtectedRoute）
- US2 可與 US1 並行（image + Helm 不需要 page 實作；但 image 內容會包 build 出來的 dist，所以實際合 PR 時 US1 要先完成）
- US3 依賴 US1 測試 + US2 CI workflow 已存在

---

## Parallel Execution Opportunities

- **Phase 1**：T001-T011 多檔互不依賴可並行；T012 為 gate
- **Phase 1 shadcn**：T013 必先；T014 依賴 T013
- **Phase 2**：T017-T021 順序：T017 → T018 → T019 → T020 → T021（互相依賴）
- **Phase 3 (US1)**：5 個 test (T022-T026) 可並行寫；3 個 impl (T027-T029) 可並行
- **Phase 4 (US2)**：T030-T037 大致並行（不同檔）；T032-T035 同 helm 目錄可循序 commit
- **Phase 6 Polish**：T040-T044 全部並行

---

## Implementation Strategy

### MVP

**Phase 1+2+3 = MVP**（local password 登入端到端可跑）。
**+ Phase 4+5 = 上線就緒**。

### TDD Discipline

每個 user story：unit test commit → impl commit。git log -- frontend/ 必須
顯示 test < impl 順序。

### Risk Hot Spots

1. **Tailwind v3 + shadcn CLI 相容性**：v4 剛 GA，shadcn 還在追；T013 init
   時若 CLI 自動選 v4，要回退到 v3（components.json 內含版本資訊）
2. **Vite proxy 對 cookie 處理**：dev 環境 proxy 必須轉發 cookie；
   `changeOrigin: false` + `cookieDomainRewrite` 可能需要調
3. **shadcn 生成 .tsx 含 absolute import alias (`@/components/...`)**：
   `vite.config.ts` + `tsconfig.json` 必須設 path alias，否則 build fail
4. **Helm Ingress path-type**：必須 `Prefix` 而非 `Exact`，否則 `/auth/oidc/callback`
   這種子路徑不會 match
5. **TanStack Query 與 401 互動**：query 失敗 401 應該 trigger event 然後
   query 不要 retry（預設 retry 3 次會打爆）→ QueryClient 設 `retry: false`
   for 401，或 wrapper 內判斷
6. **Node 版本不一致**：本機可能跑 node 22，CI 跑 node 20；package-lock 走
   ci 模式 + .nvmrc 對齊

---

## Format Validation

✅ 全部 45 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-5 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
