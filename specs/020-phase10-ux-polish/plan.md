# Implementation Plan: 階段 10 使用體驗打磨收尾

**Branch**: `020-phase10-ux-polish` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-phase10-ux-polish/spec.md`

## Summary

一批以前端為主的 UX 打磨：分配卡片顯示 display_name + 現價、可自助領取卡片可點進詳情、新成員三步引導、呼叫端點統一到單一來源（`gateway_base_url`）、admin 配額調整改 shadcn Dialog、token 文案涵蓋自助。唯一後端改動：`/me/allocations` 序列化補 `display_name`（從目錄查 slug→display_name map；price 已有）。不新增表、不新增 migration。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 處序列化）
**Primary Dependencies**: TanStack Query、shadcn/ui、FastAPI、SQLAlchemy 2.x async（皆既有）
**Storage**: 不新增表、不新增 migration；display_name 取自既有 `model_catalog`
**Testing**: Vitest + RTL（前端）、pytest contract（後端 /me/allocations）
**Target Platform**: SPA frontend + web-service backend
**Project Type**: web（backend + frontend）
**Performance Goals**: 卡片資料沿用既有查詢；display_name map 為單次 catalog 查詢（與既有 price_map 同一路徑）
**Constraints**: 複用既有 price-format / 目錄資料，不另寫平行邏輯；端點單一來源；既有行為零退化
**Scale/Scope**: 1 處後端序列化 + 數處前端（dashboard、catalog/claimable 卡片、admin allocations Dialog）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First (NON-NEGOTIABLE)**: ✅ 先寫失敗測試。後端：`/me/allocations` 回 `display_name`（contract）。前端 RTL：卡片顯示名稱+現價、可自助領取卡片可點進、無分配顯示引導、端點兩處一致、admin 配額 Dialog、token 文案。
- **II. Contract-First**: ✅ `/me/allocations` 回應新增 `display_name` 欄位（additive，向後相容），記於 `contracts/`。
- **III. 整合測試覆蓋外部依賴**: ✅ 後端以 in-memory SQLite contract 測試驗證 display_name 來自目錄；前端 mock fetch。
- **IV. 可觀測性**: ✅ 純展示/文案，不涉密鑰；端點來源單一化反而減少誤導。
- **V. 簡潔優先 (YAGNI)**: ✅ 複用既有 price-format、目錄資料、`gateway_base_url`；display_name 用既有 catalog 查詢，不新增端點。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/020-phase10-ux-polish/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/            # /me/allocations display_name 欄位
└── tasks.md              # /speckit.tasks
```

### Source Code (repository root)

```text
src/ai_api/api/me.py                      # 修改：_alloc_public 加 display_name；list_my_allocations 建 slug→display_name map（比照既有 price_map）
frontend/src/
├── routes/dashboard.tsx                  # 卡片 display_name+現價（US1）、可自助領取卡片可點進詳情（US2）、空狀態三步引導（US3）、API 端點改用 gateway_base_url（US4）、token 文案（US6）
├── components/api-usage-example.tsx       # 確認 base URL 來源 = gateway_base_url（US4 單一來源；多半已是，驗證/對齊）
└── routes/admin/allocations.tsx           # 調整配額改 shadcn Dialog（US5），取代 prompt()
tests/
├── contract/test_me_allocations.py        # （擴充或新增）/me/allocations 回 display_name
└── frontend：dashboard / admin-allocations RTL（擴充既有 + 新增）
```

**Structure Decision**: 沿用既有 web 佈局。後端僅 `me.py` 一處序列化；前端集中在 `dashboard.tsx` + `admin/allocations.tsx`，複用既有元件（price-format、Dialog、useAuth 的 member.gateway_base_url）。

## Complexity Tracking

> 無 Constitution 違反，本節留空。
