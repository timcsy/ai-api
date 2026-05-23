# Implementation Plan: 階段 3b.0 — Frontend Scaffold

**Branch**: `008-frontend-scaffold` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-frontend-scaffold/spec.md`

## Summary

引入 monorepo 第二個子專案 `frontend/`（React 19 + Vite 6 + TypeScript），
獨立 nginx pod 部署，Ingress 路徑路由。本階段只交付骨架 + login/logout，
**不寫任何業務頁面**。

## Technical Context

**Language/Version**: TypeScript（strict） + Python 3.11+（既有，不變）
**Primary Dependencies (frontend)**：
- React 19 + React DOM
- Vite 6（build tool）
- TypeScript 5.x
- React Router v7
- TanStack Query v5
- Tailwind v3 + `tailwindcss-animate`
- shadcn/ui（CLI 安裝；不走 npm 套件）
- ESLint + Prettier
- Vitest + React Testing Library + jsdom
**Primary Dependencies (deploy)**：nginx:1.27-alpine、node:20-alpine
**Storage**: 無（前端不直接接 DB）
**Testing**:
- Vitest unit/integration：auth context、API client、ProtectedRoute、login form
- Playwright E2E：**defer 到 3b.7**
- 後端既有 194 tests 不動
**Target Platform**: 桌面瀏覽器（Chrome/Firefox/Safari latest）；K8s deploy
**Project Type**: monorepo（既有 Python service + 新前端 SPA）
**Performance Goals**：
- `npm run build` ≤ 60s（CI）
- bundle size ≤ 500KB gzipped（含 React + Router + Query + shadcn 基礎組件）
**Constraints**：
- Node 20 LTS（CI matrix + .nvmrc）
- 與後端共用 ingress host；CORS 在跨 host 時生效
- nginx image 走既有 Trivy + SBOM gate（Phase 2.6 紀律）
- Helm Ingress 預設 disabled（向下相容）
**Scale/Scope**：~15 files (frontend src) + 3 deploy files + 1 CI workflow

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | 前端 Vitest 也採 TDD；SC-008 延續；auth context / API client / ProtectedRoute / login form / 404 fallback 五個 unit test 先寫 | ✅ |
| II. Contract-First | path-based routing 規則寫進 `contracts/routing.md`；UI 沒 API 但有「routes manifest」作為契約 | ✅ |
| III. 整合測試覆蓋外部依賴 | 前端對後端的整合 = manual dev-server test + 既有後端 contract tests 保證；E2E 留 3b.7 | ✅ |
| IV. 可觀測性 | 前端 console error 是首要觀測；CI 跑 `npm run build --reportCompressedSize`；不引入額外 telemetry SDK | ✅ |
| V. YAGNI | 5 條 NON-GOAL；無業務頁面、無 E2E、無 RWD、無 i18n、無圖表 | ✅ |

**符合 experience.md 教訓**：
- 「mutable tag」→ frontend image 也 pin SHA tag（不用 `:latest`）
- 「Helm pre-install hook 順序」→ 本階段無 hook，frontend Deployment 可獨立啟動
- 既有教訓無前端特化項目；本階段是「踩坑提取教訓」的初始累積期

**初次評估通過**。無 Complexity Tracking（新引入 frontend stack 屬於 spec
明示需求，不算違反原則）。

## Project Structure

### Documentation

```text
specs/008-frontend-scaffold/
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── routing.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
frontend/                            # 新目錄
├── .nvmrc                           # 20
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── eslint.config.js
├── components.json                  # shadcn config
├── index.html
├── public/
│   └── (空：favicon 之類稍後加)
└── src/
    ├── main.tsx                     # entry
    ├── App.tsx                      # router root
    ├── index.css                    # tailwind base
    ├── lib/
    │   ├── api-client.ts            # fetch wrapper
    │   └── utils.ts                 # shadcn helper (cn)
    ├── contexts/
    │   └── auth.tsx                 # AuthContext + useAuth
    ├── components/
    │   ├── protected-route.tsx
    │   └── ui/                      # shadcn-generated (button, input, label, card, alert)
    ├── routes/
    │   ├── login.tsx
    │   ├── home.tsx                 # placeholder protected
    │   └── not-found.tsx
    └── __tests__/
        ├── api-client.test.ts
        ├── auth-context.test.tsx
        ├── protected-route.test.tsx
        ├── login.test.tsx
        └── not-found.test.tsx

deploy/docker/
└── Dockerfile.frontend              # 新；multi-stage

deploy/nginx/
└── default.conf                     # 新；SPA fallback

deploy/helm/ai-api/
├── values.yaml                      # 加 frontend + ingress 區段
└── templates/
    ├── frontend-deployment.yaml     # 新
    ├── frontend-service.yaml        # 新
    └── ingress.yaml                 # 新（預設 disabled）

.github/workflows/
├── frontend.yml                     # 新：lint + typecheck + build + test
└── image.yml                        # 既有；加 matrix 同時 build frontend image
```

**Structure Decision**: monorepo — `frontend/` 與 `src/` 並列；CI 各自獨立
job。Helm chart 維持單一（管兩個 image + 兩個 Deployment）。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | 5 個 Vitest unit test 先於 impl → ✅ |
| Contract-First | `contracts/routing.md` 是本階段「契約」（Ingress 規則 + nginx fallback 規則） | ✅ |
| 整合測試覆蓋外部依賴 | 前端與後端整合走 manual dev-server smoke；本階段不寫 Playwright | ✅ |
| 可觀測性 | bundle size 報告於 CI；無新 audit | ✅ |
| YAGNI | NON-GOAL 5 條已防擴張 → ✅ |

通過，可進入 `/speckit.tasks`。
