# Implementation Plan: 會員介面分頁化 + 金鑰/分配 概念釐清

**Branch**: `032-member-ui-tabs` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/032-member-ui-tabs/spec.md`

## Summary

把會員「一頁長捲」的儀表板拆成頂部導覽分頁（我的儀表板/金鑰/分配/用量/模型目錄）。儀表板降為精簡總覽；既有自足元件（`AppCredentialsCard`、分配卡列、`UsageSummary`+圖表、`CodexInstallCard`）純搬到各自路由頁。分配頁與金鑰頁各加一句白話解釋「分配＝能用什麼；金鑰＝拿來連線的鑰匙」。金鑰卡「改名＋編輯 model」併為單一「編輯」（後端 PATCH 已支援 name+scope 同送）。admin Provider 頁面向使用者的英文「Rotate」中文化。**純前端，無 schema、無 migration、無新端點、無新套件。** 既有深連結 `/dashboard/allocations/:id` 原樣保留。

## Technical Context

**Language/Version**: TypeScript strict（前端為主）；Python 3.11+（後端**完全不動**）
**Primary Dependencies**: React 19 + Vite 6 + react-router-dom + TanStack Query + shadcn/ui + Tailwind（皆既有，不新增）
**Storage**: N/A（純呈現層，無資料模型／migration）
**Testing**: Vitest + React Testing Library（前端，既有）
**Target Platform**: 瀏覽器（桌機 + 360px 手機）
**Project Type**: Web application（frontend 重組；backend 不變）
**Performance Goals**: 互動即時；分頁切換無感（與既有 SPA 一致）
**Constraints**: 既有會員深連結 100% 仍可達；桌機+360px 不溢出；零後端回歸
**Scale/Scope**: 4 個會員路由頁（3 新 + 1 既有 catalog）+ 1 精簡總覽；2 個 UI 收尾（金鑰編輯合一、Rotate 中文化）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 先改/加失敗測試（app-shell/mobile-nav/dashboard/各新頁/legacy-redirects/金鑰卡編輯合一）再實作。見 research.md Decision 8。
- **II. API 契約優先**：✅ 不新增/變更任何 API 契約（純前端搬移）。UI 路由契約見 `contracts/ui-routes.md`。
- **III. 整合測試覆蓋外部依賴**：✅ 無新外部依賴、無 schema 變更；前端元件層測試即足。
- **IV. 可觀測性**：✅ 不動後端日誌/錯誤碼。
- **V. 簡潔優先（YAGNI）**：✅ 元件純搬移、零新抽象、零新端點、零新套件。唯一新增是 1 個精簡總覽元件（既有資料 hooks 拼裝）。

**結論**：全數通過，無 Complexity Tracking 需填。

## Project Structure

### Documentation (this feature)

```text
specs/032-member-ui-tabs/
├── plan.md              # 本檔
├── research.md          # Phase 0：8 項決策
├── data-model.md        # Phase 1：無新實體（呈現層映射）
├── quickstart.md        # Phase 1：驗收腳本
├── contracts/
│   └── ui-routes.md     # Phase 1：路由 + 導覽 UI 契約
├── checklists/
│   └── requirements.md  # 規格品質檢查（已通過）
└── tasks.md             # Phase 2（/speckit.tasks 產出，本指令不建）
```

### Source Code (repository root)

```text
frontend/src/
├── App.tsx                              # 加 /keys /allocations /usage 路由（/dashboard/allocations/:id 不動）
├── components/
│   ├── app-shell.tsx                    # MAIN_NAV 加「金鑰/分配/用量」（桌機 + 手機選單共用）
│   ├── app-credentials-card.tsx         # 改名+編輯 model → 單一「編輯」dialog（name+scope 同送 PATCH）
│   ├── member-overview.tsx              # 【新】精簡總覽（用量摘要/金鑰數/分配數/快速接入/待辦）
│   ├── allocation-list.tsx              # 【新】從 dashboard 抽出的「可自助領取 + 我的分配」卡列
│   ├── api-endpoint-card.tsx            # 【新】從 dashboard 抽出的「API 端點」卡 + token 提示
│   ├── usage-summary.tsx                # 既有，搬到用量頁
│   ├── member-usage-charts.tsx          # 既有，搬到用量頁
│   └── codex-install-card.tsx           # 既有，搬到金鑰頁 + 總覽快速接入
├── routes/
│   ├── dashboard.tsx                    # 降為精簡總覽（渲染 member-overview）
│   ├── keys.tsx                         # 【新】金鑰頁：api-endpoint-card + AppCredentialsCard + CodexInstallCard + 一句解釋
│   ├── allocations.tsx                  # 【新】分配頁：allocation-list + 一句解釋
│   ├── usage.tsx                        # 【新】用量頁：UsageSummary + TimeRangeSelect + MemberUsageCharts
│   ├── allocation-detail.tsx            # 既有，不動（深連結 /dashboard/allocations/:id）
│   └── admin/providers.tsx              # Rotate 對外文案中文化（識別字不變）
└── __tests__/
    ├── app-shell.test.tsx               # 改：斷言新導覽項
    ├── mobile-nav.test.tsx              # 改：手機選單含新項
    ├── dashboard.test.tsx               # 改：儀表板只剩總覽
    ├── legacy-redirects.test.tsx        # 改/確認：/dashboard/allocations/:id 仍可達
    ├── keys-page.test.tsx               # 【新】
    ├── allocations-page.test.tsx        # 【新】
    └── usage-page.test.tsx              # 【新】
```

**Structure Decision**：Web application 既有結構，本功能只動 `frontend/src`。沿用 `routes/` 一檔一頁、`components/` 自足元件的既有慣例；新頁是薄殼（組合既有元件），新元件是把 dashboard 既有 section 抽出。`App.tsx` 路由表與 `app-shell.tsx` 導覽是唯二「結構性」改動點。

## Complexity Tracking

> 無違規，免填。
