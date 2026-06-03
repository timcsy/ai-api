# Implementation Plan: 行動裝置（手機）體驗強化（RWD）

**Branch**: `025-mobile-rwd` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/025-mobile-rwd/spec.md`

## Summary

讓既有「桌機優先」的管理後台與成員端介面在手機（最小 360px）上也順手：手機導覽收合（US1）、
頁面內容不溢出不字字斷行（US2）、寬資料表卡片式堆疊（US3），**桌機／平板（≥768px）零回歸**。

技術取向：**純前端呈現層調整、零新 npm 依賴、零後端／DB 變更**。三條根因「修一次整站受惠」——
(1) Tailwind `container` padding 加手機斷點；(2) header 以既有 Radix Dialog 基礎的 shadcn `Sheet`
抽屜收合導覽；(3) 機械式套用既有斷點工具（`grid-cols-1 sm:`、`flex-wrap`、`truncate`/`break-all`）。
寬表格以**單一共用 CSS 響應式機制**（`.responsive-table` + 每格 `data-label`）在手機把列轉成卡片、
桌機維持原表格，避免兩套版面 drift。所有改動皆掛在 `sm:`/`md:` 以下的手機斷點，桌機路徑不變。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（**僅前端**；Python 後端完全不動）
**Primary Dependencies**: 既有 Tailwind CSS、shadcn/ui（`Sheet` 將自既有 `@radix-ui/react-dialog`
新增元件檔、`DropdownMenu` 已有）、lucide-react（`Menu` 漢堡圖示，已有）、TanStack Query、react-router
——**不新增任何 npm 依賴**
**Storage**: N/A（純呈現層，無資料模型／migration）
**Testing**: vitest + Testing Library（元件行為：手機導覽收合、響應式表格 `data-label` 約定、
截斷／換行 class 的存在性）＋ 360px 手動視覺驗收清單（quickstart）
**Target Platform**: 現代行動瀏覽器，最小 360px 寬；桌機 ≥768px 零回歸
**Project Type**: web（本功能僅動 `frontend/`）
**Performance Goals**: 無新效能目標；**bundle 不得因新依賴而增長**（零新依賴）
**Constraints**: 桌機／平板零回歸（FR-010）；零新 runtime 依賴；純呈現層；既有正確響應式區域不更動（FR-009/011）
**Scale/Scope**: 殼層 1 + 管理員約 14 頁 + 成員端約 6 頁 + 共用元件；約 6–9 個寬資料表需卡片化

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（不可妥協）**：適用於**有可程式化行為**的部分——手機導覽（Sheet 開合、列出全部目的地）、
  共用響應式表格（每身體格帶 `data-label`、桌機/手機兩種結構並存於 DOM）、需截斷處的 class 存在性——
  皆先寫 **失敗 vitest（Red）** 再實作。**純視覺 RWD 正確性**（360px 是否溢出、中文是否字字斷行）
  在 jsdom **無版面引擎、無法單元測試**，改以 quickstart 的 **360px 手動驗收清單**覆蓋。此非規避 TDD：
  凡有 DOM 可斷言的行為一律先測；純 CSS 視覺以手動清單收尾，並在 plan 明示分工。✅ 通過（已記錄測試分工）
- **II. 契約優先**：本功能**無 API 契約**（純前端）。對外「介面契約」為**共用元件的呈現契約**——
  響應式表格的 `data-label` 約定與兩種版面、手機導覽「全部目的地可達」——記於 `contracts/ui-contracts.md`。✅ 通過
- **III. 整合測試覆蓋外部依賴**：**無外部依賴**（不碰 Azure/DB/SMTP/網路）。N/A。✅ 通過
- **IV. 可觀測性**：純呈現層，不涉日誌／追蹤／密鑰。N/A。✅ 通過
- **V. 簡潔優先（YAGNI）**：寬表格抽共用機制——專案有 6+ 個寬表（遠超「第 4 個使用情境」門檻），
  抽象正當；採**最小** CSS 機制（一個 class + `data-label` 約定）而非重型 column-config 框架，
  保留既有所有儲存格 renderer（badge/按鈕/dropdown/可展開列）不動 → 最小回歸面。
  不新增任何依賴、不為「未來」加旗標。✅ 通過

**結論**：無憲章違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/025-mobile-rwd/
├── plan.md              # 本檔
├── research.md          # Phase 0：8 條決策（含 jsdom 測試分工、響應式表格機制、斷點策略）
├── data-model.md        # Phase 1：無資料模型（記錄 UI 結構：導覽目的地清單、表格 data-label 約定）
├── quickstart.md        # Phase 1：360px 逐頁驗收清單（對應 SC-001~007）
├── contracts/
│   └── ui-contracts.md  # Phase 1：共用元件呈現契約（響應式表格 + 手機導覽）
├── checklists/
│   └── requirements.md  # spec 品質檢核（16/16 通過）
└── tasks.md             # Phase 2（/speckit.tasks 產出，非本指令）
```

### Source Code (repository root)

```text
frontend/
├── tailwind.config.ts                         # container.padding 加手機斷點（根因①）
├── src/
│   ├── index.css                              # 新增 .responsive-table 響應式表格機制（單一來源）
│   ├── components/
│   │   ├── app-shell.tsx                      # header 手機收合（Sheet 抽屜 + 隱藏 inline nav/email）（根因②）
│   │   └── ui/
│   │       └── sheet.tsx                      # 新增：shadcn Sheet（基於既有 @radix-ui/react-dialog，非新依賴）
│   ├── routes/
│   │   ├── admin/                             # 各 admin 頁套 grid-cols-1 sm:、flex-wrap、truncate、.responsive-table
│   │   │   ├── usage.tsx / allocations.tsx / members.tsx / providers.tsx
│   │   │   ├── prices.tsx / tag-rules.tsx / access.tsx / tags.tsx
│   │   │   ├── member-detail.tsx / model-detail.tsx / notifications.tsx / home.tsx
│   │   │   └── observability.tsx
│   │   ├── dashboard.tsx / catalog.tsx / catalog-detail.tsx / allocation-detail.tsx
│   │   └── …（成員端其餘頁）
│   └── __tests__/                             # vitest：mobile-nav、responsive-table、（既有測試零回歸）
```

**Structure Decision**：單一 web 專案、**僅動 `frontend/`**。新增 2 個檔（`ui/sheet.tsx`、`index.css`
的 `.responsive-table` 區塊）、修改 `tailwind.config.ts`、`app-shell.tsx` 與各路由的手機斷點 class。
後端、`tests/`（Python）、`deploy/` 完全不動。

## Complexity Tracking

> 無憲章違反，本節不適用。
