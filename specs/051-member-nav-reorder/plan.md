# Implementation Plan: 會員導覽重排——凸顯「應用」

**Branch**: `051-member-nav-reorder` | **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/051-member-nav-reorder/spec.md`

> **Note**: 這是極小的純呈現層改動（單一陣列重排），維護者選擇略過完整 `/speckit-plan`；
> 本檔為滿足 tasks 前置的**精簡 plan**，技術脈絡與結構已足夠驅動 tasks。

## Summary

把會員主導覽的呈現順序重排為 **儀表板 → 應用 → 模型目錄 → 分配 → 用量 → 金鑰**。導覽來自單一前端清單 `MAIN_NAV`（`frontend/src/components/app-shell.tsx`），桌機橫向導覽與手機收合 `Sheet` 皆 map 它——**只改這個陣列的順序一處，桌機+手機同時生效**。標籤文字、路由（`to`）、`adminOnly` 旗標、管理員項目皆不動。同 PR 更新斷言舊順序/結構的 nav 測試。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（**僅前端**；後端、資料模型、路由不動）
**Primary Dependencies**: 既有 react-router-dom、shadcn/ui（`Sheet`）、Tailwind——**不新增套件**
**Storage**: N/A（純呈現層，無資料模型、無 migration）
**Testing**: Vitest + Testing Library（`frontend/src/__tests__/`，含既有 `mobile-nav` 等 nav 測試）
**Target Platform**: 前端 SPA（桌機 + 手機 ≥360px）
**Project Type**: web（僅動 frontend）
**Performance/Constraints**: 無；唯一約束＝順序正確、標籤/路由零變更、桌機+手機一致、深連結零回歸
**Scale/Scope**: 1 個導覽陣列（6 個會員項目 + 1 管理員項目）+ 對應 nav 測試

## Constitution Check

- **I. Test-First**：✅ 先更新/新增 nav 測試斷言新順序（紅）→ 再重排陣列（綠）。
- **II. 契約優先**：N/A（無對外 API 契約變更；導覽是內部呈現）。
- **III. 整合測試覆蓋外部依賴**：N/A（無外部依賴、無後端）。
- **IV. 可觀測性**：N/A（純呈現層）。
- **V. 簡潔優先（YAGNI）**：✅ 只重排既有單一來源陣列，無新抽象、無新套件、無新元件。

**結論**：無違反、無 Complexity Tracking、Technical Context 無 NEEDS CLARIFICATION。

## Project Structure

```text
frontend/src/
├── components/
│   └── app-shell.tsx        # 【改】MAIN_NAV 陣列重排（桌機 :95 + 手機 Sheet :149 共用）
└── __tests__/
    └── mobile-nav.test.tsx  # 【改】更新斷言為新順序（+ 其他若有斷言 nav 順序的測試）
```

**Structure Decision**: 沿用既有 web 結構，僅動 `frontend/src/components/app-shell.tsx` 的 `MAIN_NAV` 與對應前端測試。後端完全不動。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
