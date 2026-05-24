# Implementation Plan: 階段 3b.2 — Admin Suite

**Branch**: `010-admin-suite` | **Date**: 2026-05-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-admin-suite/spec.md`

## Summary

最大的單一 PR — 後端 6 個 endpoint 微擴 + 1 個 migration + 1 個 dep refactor；
前端 6 個新 route + 4 個 dialog/form + ~10 個 shadcn 元件 + ~25 個新 tests。

關鍵設計（c-β additive）：admin endpoint 接受 **session-with-admin OR
X-Admin-Token**，既有 274 處 admin_headers 測試零修改。

## Technical Context

**Language/Version**: 同 3b.1
**Primary Dependencies (frontend new)**：
- `react-hook-form@^7`、`@hookform/resolvers@^3`、`zod@^3`（表單驗證）
- Radix primitives：`@radix-ui/react-dialog`、`@radix-ui/react-alert-dialog`、
  `@radix-ui/react-dropdown-menu`、`@radix-ui/react-select`、`@radix-ui/react-popover`
- `date-fns@^4`（CSV 下載檔名格式化、date picker 用）
**Primary Dependencies (backend)**：無新依賴；既有 SQLAlchemy + Alembic
**Storage**:
- 後端：`members` 表 +`is_admin BOOL` 欄位（migration 0007）
- 前端：無 localStorage 使用（一次性 token 僅放 React state）
**Testing**:
- backend: ≥ 8 個新 contract tests（is_admin endpoint + permission + bootstrap）
- frontend: ≥ 25 個新 tests（5 視圖 × 5 測試 + 共用 AdminRoute / hooks）
**Target Platform**: 同既有
**Project Type**: monorepo（不變）
**Performance Goals**：
- 5 個 admin route 各自首屏 ≤ 1.5s
- bundle size ≤ 700KB gzipped
**Constraints**：
- 既有 274 處 admin_headers 測試**零修改**（SC-002）
- 唯一 admin 不可降光（FR-006 / SC-007）
- URL = filter single source of truth（延續 3b.1）
**Scale/Scope**：~30 個前端新檔 + 1 backend migration + ~6 backend endpoint 修改

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | SC-010；後端 contract test 先寫；前端每視圖至少 5 個 component test 先寫 | ✅ |
| II. Contract-First | 後端 `require_admin` dep + endpoint shape 變動寫於 `contracts/`；前端 UI 路由表寫於 `contracts/admin-routes.md` | ✅ |
| III. 整合測試覆蓋外部依賴 | bootstrap 流程整合測試（session ↔ token 雙軌驗證）；testcontainers Postgres | ✅ |
| IV. 可觀測性 | audit log 新 event：`member_promoted` / `member_demoted`；前端 toast 統一錯誤反饋 | ✅ |
| V. YAGNI | 7 條 NON-GOAL（E2E / 圖表 / WS / 批次 / 暗黑 / 自訂排版 / audit viewer） | ✅ |

**符合 experience.md 教訓**：
- 「URL = single source of truth」（3b.1 catalog）→ admin allocations / usage filter 沿用
- 「logout queryClient.clear()」→ admin/member 切換時 cache 不殘留
- 「shadcn 元件 commit .tsx」→ 10 個新元件同模式
- 「TS composite tsconfig」/「Vitest type clash」/「ESLint no-undef」三條前端坑已解決
- 「httpx URL quote」→ admin usage query 含 date range，TanStack Query 的 params 機制自動 encode

**初次評估通過**。無 Complexity Tracking（大 PR 已 spec 階段論證合理）。

## Project Structure

### Documentation

```text
specs/010-admin-suite/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-auth.md          # require_admin dep 行為 + bootstrap 流程
│   ├── admin-routes.md        # 6 個 admin route + dependencies
│   └── admin-endpoints.md     # PATCH /admin/members shape extension
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/ai_api/                              # Backend
├── api/
│   ├── deps.py                          # 改：require_admin（session OR token）
│   ├── admin_members.py                 # 改：PATCH 接受 is_admin
│   └── me.py                            # 改：/me response 加 is_admin
├── models/
│   └── member.py                        # 改：+is_admin 欄位
├── services/
│   └── members.py                       # 改：set_is_admin() + last-admin guard

alembic/versions/
└── 0007_member_is_admin.py              # 新

tests/contract/
├── test_admin_is_admin_promotion.py     # 新：bootstrap + promotion + demotion
├── test_admin_session_auth.py           # 新：session-with-admin 通過、非 admin 403
└── test_last_admin_guard.py             # 新：唯一 admin 降不下來

frontend/src/                            # Frontend
├── components/
│   ├── admin-route.tsx                  # 新：is_admin 守衛
│   ├── app-shell.tsx                    # 改：條件渲 Admin nav link
│   └── ui/
│       ├── table.tsx                    # 新
│       ├── dialog.tsx                   # 新
│       ├── alert-dialog.tsx             # 新
│       ├── dropdown-menu.tsx            # 新
│       ├── form.tsx                     # 新（含 react-hook-form 整合）
│       ├── select.tsx                   # 新
│       ├── textarea.tsx                 # 新
│       └── popover.tsx                  # 新
├── hooks/
│   ├── use-admin-allocations-filters.ts # 新：URL ↔ filter state（admin alloc）
│   └── use-admin-usage-filters.ts       # 新：URL ↔ filter state（admin usage）
├── lib/
│   └── download.ts                      # 新：blob → <a download> trigger
├── contexts/auth.tsx                    # 改：Member 型別加 is_admin
├── routes/
│   ├── admin/
│   │   ├── members.tsx                  # 新 US3
│   │   ├── allocations.tsx              # 新 US4
│   │   ├── usage.tsx                    # 新 US5
│   │   ├── quota-pool.tsx               # 新 US6
│   │   ├── catalog.tsx                  # 新 US7（thin wrapper）
│   │   └── rebalance-log.tsx            # 新 US8
├── App.tsx                              # 改：加 admin 路由群
└── __tests__/
    ├── admin-route.test.tsx
    ├── admin-members.test.tsx
    ├── admin-allocations.test.tsx
    ├── admin-usage.test.tsx
    ├── admin-quota-pool.test.tsx
    ├── admin-rebalance-log.test.tsx
    ├── use-admin-allocations-filters.test.tsx
    ├── use-admin-usage-filters.test.tsx
    └── download.test.ts
```

**Structure Decision**：admin 路由集中於 `routes/admin/` 子目錄 — 清晰標示
邊界 + 未來 lazy-load 容易（本階段不做 code-splitting，但結構預備）。

## Complexity Tracking

**單一大 PR vs 拆 5 個 PR**：spec 階段已論證 — 5 個視圖共用 shell + auth +
form pattern；分拆會多 5× spec/plan/tasks/CI overhead。視為合理單一交付單位。

無其他偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | backend 8 + frontend 25 共 33 個 test 先於 impl → ✅ |
| Contract-First | 3 個 contract md 涵蓋 auth / routes / endpoints → ✅ |
| 整合測試覆蓋外部依賴 | bootstrap session-token 雙軌走真 Postgres → ✅ |
| 可觀測性 | 2 個新 audit event；toast 統一錯誤；CSV/JSON 下載觸發瀏覽器原生 → ✅ |
| YAGNI | 7 條 NON-GOAL → ✅ |

通過，可進入 `/speckit.tasks`。
