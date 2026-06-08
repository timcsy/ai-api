# Implementation Plan: 模型目錄 ↔ LiteLLM 登錄表對接

**Branch**: `033-litellm-catalog-sync` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/033-litellm-catalog-sync/spec.md`

## Summary

把 LiteLLM 內建的模型登錄表（`litellm.model_cost`，實測 2776 筆，含 provider/mode/context/能力/牌價）接進管理員模型目錄：**新增時**選一個 LiteLLM key → 自動帶入 context/modality/能力 + 建議價、slug 預設＝key（可改）；查無的自訂部署（如 `azure/gpt-5.4`）指定「對照基礎模型」借中繼資料。每個同步欄位記**來源**（litellm / 借用 / 手動）+ 匯入快照（存於 `ModelCatalog` 新增的單一 JSON 欄 `litellm_sync`）。**維護時**一鍵「檢查 LiteLLM 更新」線上抓最新登錄表（`litellm.get_model_cost_map(url)`，逾時回退 bundled `litellm.model_cost`）→ 逐欄列「舊→新」+ 來源 → 選擇性採納；採納價格＝既有 `PriceList` append 一筆版本帶 `source_note="litellm@<ver>"`。**價目表仍是計費唯一真理、LiteLLM 只給建議**。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、**`litellm`（既有，library form——讀其內建 `model_cost` + `get_model_cost_map` 線上抓）**、TanStack Query、shadcn/ui。**不新增套件。**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0018`**——`model_catalog` 加一個 nullable JSON 欄 `litellm_sync`（來源標記 + 匯入快照 + 對照基礎模型 key）。價格沿用既有 `price_list`（append-only），不改 schema。
**Testing**: pytest（contract + integration，Postgres testcontainer）；Vitest + RTL（前端）
**Target Platform**: Kubernetes（admin Web UI + 後端）
**Project Type**: Web application（前後端）
**Performance Goals**: 新增帶入即時（讀記憶體中的 `model_cost`）；線上抓最新有逾時（建議 ~5s）
**Constraints**: 計費唯一真理為自有價目表；不自動覆寫手改欄；不在 proxy 熱路徑線上抓；線上抓對外連線需 egress 放行
**Scale/Scope**: 登錄表 ~2776 模型（搜尋用）；4 個新 admin 端點 + 1 個 adapter service + 1 migration + admin 前端（picker / diff 採納 UI / 來源徽章）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 後端先寫失敗 contract/integration（adapter 對照 fixture、端點契約、採納 append 價目、線上抓 timeout 回退）；前端先紅後綠。
- **II. API 契約優先**：✅ 4 個新 admin 端點先定契約（見 `contracts/`）再實作。
- **III. 整合測試覆蓋外部依賴**：✅ LiteLLM 登錄表是外部資料源——bundled `model_cost` 以真實值驗；**線上抓以 mock HTTP** 驗 timeout + **回退 bundled** 路徑（不打真網路）。migration `0018` 以 Postgres 整合測試驗、零回歸。
- **IV. 可觀測性**：✅ 線上抓失敗/回退要 log（帶原因）；採納動作留稽核（model_catalog updated + 價目 append 帶 source_note）。
- **V. 簡潔優先（YAGNI）**：✅ 用既有 `PriceList`/`source_note`；provenance 用**單一 JSON 欄**不為每欄加 column；不批量鏡像整份登錄表、不自動套用。

**結論**：全數通過。唯一 schema 增量是 1 個 nullable JSON 欄（additive，非改 PK／非重建表，不踩階段 18 的 migration 陷阱）。

## Project Structure

### Documentation (this feature)

```text
specs/033-litellm-catalog-sync/
├── plan.md              # 本檔
├── research.md          # Phase 0：litellm API 邊界、欄位對應、線上抓 vs bundled、egress
├── data-model.md        # Phase 1：litellm_sync JSON 結構 + 欄位對應 + 價格換算
├── quickstart.md        # Phase 1：驗收腳本
├── contracts/
│   └── admin-litellm-sync.md   # Phase 1：4 個 admin 端點契約
├── checklists/requirements.md  # 規格品質（已通過）
└── tasks.md             # Phase 2（/speckit.tasks 產出）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/model_catalog.py            # 加 nullable JSON 欄 litellm_sync
├── services/
│   ├── litellm_registry.py            # 【新】adapter：lookup/search/suggest_price/fetch_latest/diff + 欄位對應
│   └── pricing.py                     # 既有；採納價走既有 PriceList append（source_note=litellm@ver）
├── api/admin_catalog.py               # 加 4 端點（search / suggest / check / apply）+ create 收 litellm_sync
├── api/schemas.py                     # ModelCatalogCreate/Update 加 base_model_key + litellm_sync provenance
alembic/versions/0018_model_litellm_sync.py   # 【新】additive nullable JSON 欄

frontend/src/
├── routes/admin/{model,model-detail,catalog-manage,prices}.tsx  # picker / 來源徽章 / 檢查更新入口
├── components/
│   ├── litellm-model-picker.tsx       # 【新】搜尋 litellm key → 帶入
│   └── litellm-update-diff.tsx        # 【新】逐欄 old→new + 來源 + 勾選採納
└── __tests__/...                      # 對應前端測試
```

**Structure Decision**：Web application 既有結構。後端核心是 1 個新 adapter service（封裝所有 litellm 讀取/對應/diff，集中一處便於版本變動時維護）+ admin_catalog 端點擴充 + 1 個 additive migration；前端是 admin 模型頁的 picker 與 diff 採納 UI。計費引擎、proxy、價目表 schema 全不動。

## Complexity Tracking

> 無違規，免填。唯一複雜度（線上抓外部資料）已以「timeout + 回退 bundled + mock 測試 + egress checklist」涵蓋，屬必要而非過度設計。
