# Implementation Plan: 階段 3b.1 — Member View

**Branch**: `009-member-view` | **Date**: 2026-05-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-member-view/spec.md`

## Summary

延續 3b.0 stack；前端加 4 個業務頁面 + 1 個 AppShell + 7 個 shadcn 元件；
後端僅在 `/me/allocations/{id}/calls` 端點 wire 透 service 既有的 `limit +
before` query param（service 已支援，無需改 schema）。

## Technical Context

**Language/Version**: 同 3b.0（前端 TS 5.x / React 19 / Vite 6）+ Python 3.11+ 後端
**Primary Dependencies**：
- 無新 npm 依賴（除 7 個 shadcn .tsx 與其支撐 Radix primitives，已含於 3b.0
  `@radix-ui/react-slot`/`react-label` + `clsx` + `tailwind-merge` 等）
- 可能新增：`@radix-ui/react-checkbox`、`@radix-ui/react-switch`、
  `@radix-ui/react-tabs`、`@radix-ui/react-progress`、`@radix-ui/react-toast`
  （shadcn add 對應元件的 transitive deps）
**Storage**: 無；後端不動 schema
**Testing**:
- Vitest unit/component：dashboard、allocation-detail、catalog-list、
  catalog-detail、app-shell、useCatalogFilters hook、clipboard fallback
- Backend: 1 contract test 驗 cursor pagination
**Target Platform**: 同既有
**Performance Goals**：
- filter 變更 → 結果更新 ≤ 300ms（cache hit 後幾乎瞬時）
- dashboard 首屏 ≤ 1s（單一 `/me` + 單一 `/me/allocations` 並行）
**Constraints**：
- URL 為 filter state single source of truth（FR-019）
- logout 清空 queryClient cache（FR-027）
- 後端 endpoint 僅微擴；不新增任何 endpoint
**Scale/Scope**：~12 個前端新檔（components + routes + hooks + tests）+ 1
個 endpoint 修改 + 1 backend contract test

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | SC-009；frontend Vitest + backend cursor contract test 先寫 | ✅ |
| II. Contract-First | catalog 與 `/me/allocations/{id}/calls` 行為寫進 `contracts/ui-routes.md`；後端 schema 變動 spec FR-001 明列 | ✅ |
| III. 整合測試覆蓋外部依賴 | 後端 cursor pagination 整合測試；frontend 對後端整合走 manual dev-server | ✅ |
| IV. 可觀測性 | 無新 audit；React Query DevTools 可選；錯誤統一 toast | ✅ |
| V. YAGNI | 6 條 NON-GOAL；無圖表、無 admin、無 RWD、無 E2E、無費用顯示、無 picker | ✅ |

**符合 experience.md 教訓**：
- 「TS composite tsconfig」/「Vitest type clash」/「ESLint no-undef」三條前
  端坑已在 3b.0 解決，本階段直接受惠
- 「shadcn 元件 commit .tsx」模式延續；7 個新元件全部 hand-write from
  defaults，避開 CLI 互動

**初次評估通過**，無 Complexity Tracking。

## Project Structure

### Documentation

```text
specs/009-member-view/
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── ui-routes.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
frontend/src/
├── components/
│   ├── app-shell.tsx                 # 新：sticky header + nav + outlet
│   └── ui/
│       ├── badge.tsx                 # 新
│       ├── progress.tsx              # 新
│       ├── tabs.tsx                  # 新
│       ├── separator.tsx             # 新
│       ├── scroll-area.tsx           # 新
│       ├── checkbox.tsx              # 新
│       ├── switch.tsx                # 新
│       └── toast.tsx + toaster.tsx + use-toast.ts  # shadcn toast trio
├── hooks/
│   └── use-catalog-filters.ts        # 新：URL ↔ filter state 同步
├── lib/
│   └── clipboard.ts                  # 新：clipboard writeText + fallback
├── routes/
│   ├── dashboard.tsx                 # 新（取代 home.tsx placeholder）
│   ├── allocation-detail.tsx         # 新
│   ├── catalog.tsx                   # 新（list + filter sidebar）
│   ├── catalog-detail.tsx            # 新
│   └── home.tsx                      # 刪除（被 dashboard 取代）
├── App.tsx                           # 改：加 AppShell + 新 routes
└── contexts/auth.tsx                 # 改：logout 加 queryClient.clear()
└── __tests__/
    ├── dashboard.test.tsx            # 新
    ├── allocation-detail.test.tsx    # 新
    ├── catalog-filter.test.tsx       # 新
    ├── catalog-detail.test.tsx       # 新
    ├── app-shell.test.tsx            # 新
    ├── use-catalog-filters.test.ts   # 新
    └── clipboard.test.ts             # 新

src/ai_api/api/me.py                  # 改：endpoint 加 limit + before query
tests/contract/test_me_calls_pagination.py  # 新
```

**Structure Decision**：3b.0 既有結構；本階段在 `frontend/src/` 加 components、
hooks、routes 三個層次的新檔；backend 僅一個 endpoint 修改 + 一個 contract test。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | 7 個前端 + 1 個後端 test 檔先於 impl → ✅ |
| Contract-First | `contracts/ui-routes.md` 定義各路由 / data dependencies / error states → ✅ |
| 整合測試覆蓋外部依賴 | backend cursor 用 testcontainers Postgres；前端整合 manual | ✅ |
| 可觀測性 | toast 提示成功/失敗；無新 audit 需求 | ✅ |
| YAGNI | 6 條 NON-GOAL → ✅ |

通過，可進入 `/speckit.tasks`。
