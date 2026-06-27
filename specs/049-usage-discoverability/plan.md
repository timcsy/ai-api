# Implementation Plan: 「如何呼叫」可發現性重設計

**Branch**: `049-usage-discoverability` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/049-usage-discoverability/spec.md`

## Summary

把「如何呼叫」從**只埋在分配/模型詳情頁**，搬到成員**剛拿到金鑰的當下**就看得見的地方。三個 user story 做成單一 spec：US1 金鑰頁「如何使用這把金鑰」+ model 下拉（選項＝**這把金鑰 scope 內的 model**）；US2 應用頁擴成「怎麼用」總站（工具卡 + 直接 API/SDK 卡）；US3 儀表板/分配/模型詳情 cross-link 指過來。**純前端、零後端、零 migration、零新套件**——重用既有共用元件 `ApiUsageExample`（單一來源），資料來自既有 `/me/credentials`（金鑰 scope）+ `/catalog`（每個 model 的 kind / responses / 顯示名稱），前端以 slug join。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（**僅前端**；Python 後端不動）
**Primary Dependencies**: TanStack Query、shadcn/ui、既有共用元件 `ApiUsageExample`、`applications.tsx` 註冊表——**皆既有，不新增套件**
**Storage**: N/A（純呈現層，無資料模型／migration）
**Testing**: vitest（前端）
**Target Platform**: 瀏覽器（SPA）
**Project Type**: web（**前端單側**變更）
**Performance Goals**: 金鑰頁複用既有 `/me/credentials` 查詢 + 既有 `/catalog` 查詢（TanStack Query 快取），不增加新往返
**Constraints**: 範例**單一來源**（`ApiUsageExample`，不複製）；成員只看自己的金鑰與其 scope 的 model（沿用既有隔離）；金鑰只顯示一次，範例用 `$TOKEN` 佔位
**Scale/Scope**: 1 個元件改動（keys 頁加「如何使用」區 + model 下拉）+ 1 筆應用註冊表新增（直接 API/SDK 卡）+ 3 處 cross-link；**無新端點、無 schema 變更**

## Constitution Check

> constitution 原則：I Test-First（非協商 TDD）、II 契約優先、III 整合測試覆蓋外部依賴且 CI 可重現、IV 可觀測性、V YAGNI。

| 原則 | 評估 | 結論 |
|---|---|---|
| **I. Test-First** | 先寫失敗的 vitest：金鑰頁顯示「如何使用」+ 下拉切 model 換範例 + 空 scope 提示；應用頁有「直接 API/SDK」卡；三處 cross-link 存在 | ✅ 遵循 |
| **II. 契約優先** | **無 API 契約變更**——重用既有 `/me/credentials`（已回 `allocations[].{resource_model,display_name,status}`）+ `/catalog`（已回 `kind`/`responses_support`/`display_name`）。本功能的「契約」是 **UI 契約**（頁面結構 + 元件 props），定義於 `contracts/ui.md` | ✅ 遵循 |
| **III. 整合測試覆蓋外部依賴 + CI 可重現** | 前端 vitest 覆蓋；**無外部依賴、無後端行為變更**（純讀既有端點） | ✅ 遵循（無外部邊界可測） |
| **IV. 可觀測性** | 無新後端行為（純前端讀取既有端點） | ✅ N/A |
| **V. YAGNI** | 重用 `ApiUsageExample` + 應用註冊表 + 既有兩個端點；只加「下拉 + 範例」「一張卡」「三個連結」。**不**加端點、表、套件、平行範例 | ✅ 遵循 |

**Deviations**: 無。**純前端、零後端、零 migration、零新套件**。〔spec 曾保留「若 scope-model 清單需端點微調」的可能——研究後確認**不需**：`/me/credentials` 已有 scope 的 model，`/catalog` 已有 kind，前端 join 即可。〕

## Project Structure

### Documentation (this feature)

```
specs/049-usage-discoverability/
├── spec.md              # 已完成
├── plan.md              # 本檔
├── research.md          # Phase 0（本次產出）
├── data-model.md        # Phase 1（本次產出，無持久化實體）
├── quickstart.md        # Phase 1（本次產出）
├── contracts/
│   └── ui.md            # Phase 1（本次產出，UI 契約）
└── checklists/
    └── requirements.md  # 已完成（16/16）
```

### Source Code (repository root)

```
frontend/src/
├── routes/keys.tsx                 # US1：每把金鑰加「如何使用這把金鑰」區（model 下拉 → ApiUsageExample）
├── routes/apps.tsx                 # US2：應用頁顯示「直接 API/SDK」卡（與工具卡並列）
├── lib/applications.tsx            # US2：註冊表加一筆「直接 API / SDK」（Detail = model 下拉 + ApiUsageExample）
├── components/api-usage-example.tsx# 重用（必要時微調讓「無 catalog row」優雅退 chat 範例）
├── routes/dashboard.tsx 或 components/member-overview.tsx  # US3：待辦/快速接入加「開始呼叫 → 如何使用」連結
├── routes/allocation-detail.tsx    # US3：既有範例保留 + 「想接工具 → 看應用」連結
├── routes/catalog-detail.tsx       # US3：同上
└── __tests__/                      # vitest：keys 如何使用 + 下拉 + 空 scope；apps 直接 API 卡；cross-link

# 後端：不動（重用 /me/credentials、/catalog）
```

**Structure Decision**: 純前端單側。資料以**既有端點** + **前端 slug join**（`/me/credentials` 的 scope model ⋈ `/catalog` 的 kind/responses/display_name）取得；呈現一律走**單一共用元件** `ApiUsageExample`，避免「同一概念兩份必 drift」。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
