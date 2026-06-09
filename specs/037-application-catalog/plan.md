# Implementation Plan: 應用分頁（應用目錄）—— Codex 為第一個應用

**Branch**: `037-application-catalog` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/037-application-catalog/spec.md`

## Summary

成員端新增「應用」分頁（`/apps`），把分散的 Codex 接入收斂成單一所在地。v1 = 單一 Codex 應用卡：**狀態**（你有沒有 Agent 相容的分配）+ **一鍵設定**（沿用既有 `CodexInstallCard` / device-flow，桌面 App 文案 △→✓）+ **建金鑰捷徑**（重用 `POST /me/credentials`，分配 picker 預過濾「Agent 相容」、名稱預設 Codex）+ **多介面連結**（桌面 App / Cursor / JetBrains「裝好免再設定」）。`CodexInstallCard` 從 dashboard（`member-overview`）與金鑰頁移除、收斂到 `/apps`。**唯一後端改動**：`GET /me/allocations` 每筆加唯讀衍生欄 `agent_compatible`（讀該模型的既有 `responses_support` 狀態），供 picker 預過濾與卡片狀態用。**零新表、零 migration、零新套件。** VS Code 擴充「順手自動裝」只在能可靠驗證 extension id 時做，否則 v1 給 marketplace 連結（呼應「採用前先驗證能力邊界」）。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 個既有端點加衍生欄）
**Primary Dependencies**: React Router、TanStack Query、shadcn/ui（前端）；FastAPI、SQLAlchemy 2.x async（後端）。皆既有，**不新增套件。**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——`agent_compatible` 為查詢層唯讀計算欄（讀既有 `model_catalog.capabilities` 的 `responses` 標記）。
**Testing**: 前端 vitest（含 nav / install-card / apps 頁）；後端 pytest（`/me/allocations` 衍生欄）。
**Target Platform**: 瀏覽器（前端）；Linux server（後端）；安裝腳本目標 macOS/Linux/Windows（既有）。
**Project Type**: web application（backend `src/ai_api/` + frontend `frontend/src/`）。
**Performance Goals**: 應用頁讀既有 `/me/allocations`（多一個衍生欄，N 小）；無熱路徑影響。
**Constraints**: 單一所在地（CodexInstallCard 去重）；建金鑰捷徑 scope 只含 Agent 相容；不做萬能安裝器（GUI App / 非 VS Code IDE 不自動裝）；device-flow / 計費零回歸。
**Scale/Scope**: 1 處後端（`me.py` `_alloc_public` + list 端點）+ 約 4 處前端（`app-shell` MAIN_NAV、`App.tsx` route、新 `routes/apps.tsx` + Codex 應用卡、`codex-install-card` 文案 △→✓、移除 dashboard/keys 的卡）+ 測試更新（mobile-nav / app-shell / codex-install-card）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 嚴格 TDD。先寫 後端 unit（`/me/allocations` 回 `agent_compatible`：available 模型 true、unknown/unavailable false）+ 前端測試（應用頁顯示 Codex 卡、建金鑰捷徑只列 agent_compatible、無相容分配顯示指引、nav 含「應用」、桌面 App 文案 ✓）失敗，再實作。
- **II. API 契約優先**：✅ `/me/allocations` 衍生欄、`POST /me/credentials`（既有）重用契約寫在 `contracts/`。
- **III. 整合測試覆蓋外部依賴**：✅ device-flow 既有測試零回歸；建金鑰走既有 `POST /me/credentials`（已有整合測試）。
- **IV. 可觀測性**：✅ 不新增後端行為；沿用既有金鑰建立 audit。
- **V. 簡潔優先（YAGNI）**：✅ **零 migration、零套件、零新端點**（重用 `/me/credentials`）；精選靜態應用清單不做外掛框架；**不做萬能安裝器**（明文排除，FR-009）。
- **語言與文件規範**：✅ 繁體中文回覆；UI 文案沿用 ui-glossary。

**結論**：無違反，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/037-application-catalog/
├── plan.md              # 本檔
├── research.md          # Phase 0：Agent 相容旗標、收斂去重、建金鑰捷徑、VS Code 自動裝決策
├── data-model.md        # Phase 1：agent_compatible 衍生欄 + 應用（靜態）（無 schema 變更）
├── quickstart.md        # Phase 1：US1–US3 手動驗收（含三平台煙霧）
├── contracts/
│   └── apps-and-allocations.md  # /me/allocations 衍生欄 + 建金鑰捷徑(重用) + 前端 UI 契約
├── checklists/requirements.md   # 已通過（0 NEEDS CLARIFICATION）
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/
└── api/
    └── me.py                       # GET /me/allocations：_alloc_public 加唯讀 agent_compatible
                                     #   （list 端點多載 slug→capabilities，computed via responses_support）

frontend/src/
├── App.tsx                         # 加 <Route path="/apps" element={<ApplicationsPage/>} />
├── components/
│   └── app-shell.tsx               # MAIN_NAV 加 { to:"/apps", label:"應用" }
├── routes/
│   └── apps.tsx                    # 【新】ApplicationsPage：Codex 應用卡（狀態 + 一鍵設定 + 建金鑰捷徑 + 介面連結）
├── components/
│   └── codex-install-card.tsx      # 桌面 App 文案 △→✓（共用設定、免再設定）；（可選）順手裝 VS Code 擴充說明
├── components/member-overview.tsx  # 移除 CodexInstallCard（收斂到 /apps）
└── routes/keys.tsx                 # 移除 CodexInstallCard（收斂到 /apps）

frontend/src/__tests__/
├── mobile-nav.test.tsx             # MAIN_NAV 期望加「應用」
├── app-shell.test.tsx              # 若斷言 nav 目的地，補「應用」route stub
└── codex-install-card.test.tsx     # 若斷言「△ 不建議」→ 改 ✓ 文案

tests/  (後端)
└── contract/test_me_allocations*.py 或新增 → /me/allocations 回 agent_compatible 斷言
```

**Structure Decision**：既有 web application 佈局。前端為主（新 `/apps` 頁 + nav + 卡片收斂）；後端僅在既有 `/me/allocations` 加一個唯讀衍生欄。不動 schema、不動 device-flow、不動計費。

## Complexity Tracking

> 無 Constitution 違反，留空。
