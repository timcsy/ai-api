# Feature Specification: 階段 3b.0 — Frontend Scaffold

**Feature Branch**: `008-frontend-scaffold`
**Created**: 2026-05-23
**Status**: Draft
**Input**: User description: "階段 3b.0 stack 決定與基礎建設 — React + Vite + TypeScript + TanStack Query + shadcn/ui；獨立 nginx pod + Ingress 路徑路由；含 Google OIDC + local password 登入頁；無業務頁面"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 維運者可以本機跑前端 dev server (Priority: P1)

維運者 clone repo 後，在 `frontend/` 跑 `npm install && npm run dev`，
SPA 跑在 `localhost:5173`，可登入既有後端（`localhost:8000`）。
登入後看到 placeholder「Hello, $email」並能 logout。

**Why this priority**：沒這個能力，後續所有業務頁面（3b.1~3b.6）都無從開工。

**Independent Test**：手動 — `npm run dev` + 後端跑著 → 訪 `/login` →
填表 → 登入後看到 placeholder → 點 logout → 回 `/login`。

**Acceptance Scenarios**:

1. **Given** 後端在 `localhost:8000` 跑著且 `CORS_ORIGINS=["http://localhost:5173"]`，
   **When** SPA 在 `localhost:5173` 用 local password 登入，**Then** 成功設定
   session cookie 並導向 protected route。
2. **Given** 已登入，**When** 點 logout，**Then** session cookie 清除、
   導回 `/login`。
3. **Given** 未登入直接訪 `/`，**When** route guard 攔截，**Then** 導向 `/login`。
4. **Given** 登入時填錯密碼，**When** 後端回 401，**Then** UI 顯示「invalid
   credentials」並停留在 login 頁。

---

### User Story 2 - 部署後 admin/member 在瀏覽器都能登入 (Priority: P1)

K8s 部署後，使用者在 `https://aiapi.example.com/` 看到 SPA、
`/api/*`、`/auth/*`、`/admin/*`、`/me/*`、`/catalog/*`、`/v1/*` 路由到後端。
Google OIDC + local password 兩種登入流程都可用。

**Why this priority**：3b 階段最終目的就是「瀏覽器可用」。

**Independent Test**：`helm install` 後 `kubectl port-forward` 到 ingress；
瀏覽器訪 ingress 主機名 → 看到 login 頁 → 兩種登入皆可。

**Acceptance Scenarios**:

1. **Given** Helm chart 已 install，**When** 訪 ingress root，**Then** nginx
   pod 回傳 SPA 的 `index.html`。
2. **Given** SPA 呼叫 `/auth/local/login`，**When** Ingress 收到，**Then**
   依路徑規則路由到 backend service。
3. **Given** Google OIDC 點「使用 Google 登入」，**When** redirect 流程，
   **Then** 回到 SPA 並登入成功。
4. **Given** 用 disabled member 登入，**When** 看 `/me`，**Then** 401 觸發
   auth context 清理 + 導回 login。

---

### User Story 3 - Smoke test 驗證骨架完整 (Priority: P2)

至少一條自動化 smoke test：開瀏覽器 → 登入 → 看 placeholder → logout，
全程不報錯。

**Why this priority**：catch CI 上「build 出來但跑不起來」的情況。

**Independent Test**：CI 跑前端 smoke test job → 全綠。

**Acceptance Scenarios**:

1. **Given** Vitest/RTL（unit）已配，**When** 跑 `npm test`，**Then**
   至少 auth context 與 API client 的 unit test 全綠。
2. **Given** 後端 + 前端 dev server 同時跑（用 docker compose 或腳本），
   **When** 跑 Playwright smoke（**選擇性，可 defer 到 3b.7**），**Then**
   登入→logout 場景通過。

### Edge Cases

- **CORS_ORIGINS 沒設或設錯**：登入時 OPTIONS preflight 失敗 → SPA 顯示
  「無法連線後端」明確錯誤。
- **session 過期**：API 回 401 → auth context 清理 local 狀態 + 跳 login。
- **登入後立刻重新整理頁面**：cookie 應持續、auth context 從 `/me` 重新水合。
- **使用者直接修改 URL 訪 admin 路由（未授權）**：路由 guard 攔；同時 API
  仍會 401/403 兜底。

## Requirements *(mandatory)*

### Functional Requirements

#### 專案結構
- **FR-001**: 新建 `frontend/` 目錄為前端 source；獨立於 Python `src/`。
- **FR-002**: 前端使用 **React 19 + Vite 6 + TypeScript（strict mode）**。
- **FR-003**: 資料層使用 **TanStack Query v5**；UI 元件採 **shadcn/ui**
  （Radix + Tailwind v3）；router 採 **React Router v7**。
- **FR-004**: 套件管理使用 **npm**（lockfile commit）；Node 版本 **20 LTS**
  以 `.nvmrc` 與 CI matrix 對齊。

#### Auth + API client
- **FR-005**: 提供 `apiClient` fetch wrapper：所有請求帶 `credentials: 'include'`；
  401 回應觸發 auth context 清理 + 跳 login。
- **FR-006**: 提供 `AuthContext`/`useAuth`：暴露 `member`、`status`
  (`loading | authenticated | unauthenticated`)、`login(email, pw)`、`loginGoogle()`、
  `logout()`；初始化時呼叫 `/me` 水合狀態。
- **FR-007**: 路由 guard component (`ProtectedRoute`)：`status !== authenticated`
  即導向 `/login`，帶 `?next=<原 URL>`。

#### 頁面（最小骨架）
- **FR-008**: `/login`：兩個入口 — local password 表單 + 「使用 Google 登入」
  按鈕（後者 redirect 到 `/auth/google/login`）。
- **FR-009**: `/`：登入後 placeholder「Hello, {email}」+ logout 按鈕。
- **FR-010**: `/login?next=...`：登入後導回原 URL（防 open redirect — 只接受
  以 `/` 開頭、且不含 `//` 的相對路徑）。
- **FR-011**: 404 fallback：未匹配路由顯示 minimal 404 頁。
- **FR-012**: **不**包含任何業務頁面（allocations、usage、quota-pool、catalog UI），
  留 3b.1+。

#### Build + 部署
- **FR-013**: `npm run build` 產出 static bundle 至 `frontend/dist/`。
- **FR-014**: 新增 `deploy/docker/Dockerfile.frontend`：multi-stage —
  `node:20-alpine` build → `nginx:1.27-alpine` 服務 `dist/`。
- **FR-015**: nginx 設定支援 SPA 路由 fallback（任何 unknown path → `index.html`），
  排除 `/assets/*` 之類已存在的 static asset path。
- **FR-016**: nginx image 走既有 image-build pipeline：另一個 workflow job
  或同 workflow 加 matrix；ref 與 image tag 仍 pin commit SHA（Phase 2.6 紀律）。

#### Helm
- **FR-017**: Helm chart 新增 `frontend-deployment.yaml` + `frontend-service.yaml`。
- **FR-018**: Ingress（新增 `ingress.yaml` 或更新既有）依 path-based 路由：
  - `/api/*`、`/auth/*`、`/admin/*`、`/catalog/*`、`/me/*`、`/v1/*`、`/health/*` → backend
  - `/*`（其他）→ frontend
  ⚠️ 視既有路由實作而定；spec 階段確認準確 prefix 集合。
- **FR-019**: Helm values 加 `frontend.image.{repository, tag}` 與
  `ingress.{enabled, host, tls}`；預設 ingress 關閉以維持向下相容（既有
  install 不會壞）。

#### CI
- **FR-020**: 新增 `.github/workflows/frontend.yml` 或擴 `ci.yml`：
  `npm ci` → `npm run lint` (eslint) → `npm run typecheck` (tsc --noEmit)
  → `npm run build` → `npm test` (Vitest)。
- **FR-021**: 前端 lockfile 變動觸發 build；後端只變更不觸發前端 job。

#### CORS / session
- **FR-022**: 既有 `cors_origins` 設定需要在 deploy 時非空（dev: `["http://localhost:5173"]`；
  prod: `["https://aiapi.example.com"]`）；spec 內標明依 Phase 3a 既有實作，
  本階段不改後端，僅維護人需要設環境變數。

#### 不在本階段範圍
- **FR-023** (NON-GOAL): 任何業務頁面（allocations 列表、usage dashboard、
  catalog browse、quota-pool monitor 等）— 留 3b.1+
- **FR-024** (NON-GOAL): Playwright E2E 完整覆蓋 — 留 3b.7
- **FR-025** (NON-GOAL): 多語言（首版只繁中）
- **FR-026** (NON-GOAL): 響應式手機版（首版只 desktop ≥ 1024px）
- **FR-027** (NON-GOAL): 視覺化圖表庫整合（Recharts/Chart.js 等留 3b.4）

### Key Entities

無新資料庫實體；本階段為前端 + 部署設定。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 本機 `cd frontend && npm install && npm run dev` 啟動成功，
  跑在 `localhost:5173`；瀏覽器無 console error。
- **SC-002**: 對既有後端（`localhost:8000`，`CORS_ORIGINS=["http://localhost:5173"]`），
  local password 登入流程端到端通過。
- **SC-003**: Google OIDC 登入流程端到端通過（已在 Phase 2 驗證後端 → 本階段
  只需 redirect 觸發）。
- **SC-004**: `npm run typecheck && npm run build` 在 Node 20 LTS 上零警告通過。
- **SC-005**: nginx image 經 Trivy fs scan + image scan + SBOM 三個 gate 全通過
  （延續 Phase 2.6 紀律）。
- **SC-006**: Helm `helm template` 通過；新 Ingress 預設 disabled，既有
  install 不壞。
- **SC-007**: 既有 194 backend tests 不回歸；新前端 Vitest unit test
  ≥ 5 個（auth context、API client wrapper、ProtectedRoute、login form
  validation、404 fallback）全綠。
- **SC-008**: 所有 FR 在 git 歷史可見「測試 commit 早於對應實作 commit」
  （延續 TDD 紀律 / 前端 unit test 也適用）。

## Assumptions

- **Node 20 LTS 已是 CI runner 預設可用版本**（ubuntu-latest 預裝）
- **shadcn/ui CLI 流程**：用 `npx shadcn@latest add <component>` 加元件，
  生成的 .tsx 直接 commit；不走 npm install 的元件庫
- **Tailwind v3 而非 v4**：v4 剛 GA，生態（shadcn 等）尚在追上；v3 更穩
- **既有 ingress controller**：spec 假設叢集有 ingress-nginx 或等效；
  Helm chart 預設 disabled 給未準備的環境
- **nginx image 不放 secrets**：純 static serving，無需 envFrom
- **路由 path 集合**會在 spec 階段確認 — 預期：`/api/`（如有）、`/auth/`、
  `/admin/`、`/catalog/`、`/me/`、`/v1/`、`/health` → backend；其他 → frontend
- **Logout 端點**：spec 假設 `/auth/logout` 既有；若無則本階段順手補（不
  算新功能）
