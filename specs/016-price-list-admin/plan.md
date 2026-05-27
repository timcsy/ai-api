# Implementation Plan: 價目表管理 UI (Price List Admin)

**Branch**: `016-price-list-admin` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-price-list-admin/spec.md`

## Summary

把價目表從 CLI-only 補上 admin UI：以 catalog 為主清單顯示每個模型「目前生效」價格或「未定價」、可展開歷史版本、可新增 append-only 價格版本（point-in-time）。**不新增資料表、不改計費機制**——沿用既有 `price_list` 表與 `pricing.lookup_price_for_call`；只新增 pricing service 的查詢/新增方法、admin API、前端「觀測 → 價目」分頁。price key 為 `provider + model(去 "<provider>/" 前綴)`，與計費查價一致，UI 從 catalog 帶出避免拼錯。

## Technical Context

**Language/Version**：Python 3.11+（後端）+ TypeScript strict / React 19（前端）
**Primary Dependencies**：FastAPI、SQLAlchemy 2.x async、Pydantic v2；複用既有 `pricing.py`、`PriceList`、catalog；前端既有 stack（shadcn/ui + TanStack Query）
**Storage**：PostgreSQL / SQLite；**無 schema 變更**（沿用 `price_list`，含 `UniqueConstraint(provider, model, effective_from)`）
**Testing**：pytest（後端，目前 335 baseline）；Vitest（前端，目前 72 baseline）
**Target Platform**：Linux server（K8s）；dev uvicorn + Vite
**Performance Goals**：admin 檢視/新增為 cold path（非 proxy hot path），< 200ms p95
**Constraints**：計費 point-in-time 查價行為不得改變；既有 YAML+CLI 匯入保留，與 UI 寫同一張表
**Scale/Scope**：< 50 模型、每模型少量歷史版本；後端 +3 service 方法 +3 endpoints +1 audit 值（**無 migration**）；前端 +1 觀測分頁

## Constitution Check

*GATE: 通過才進 Phase 0；Phase 1 後重檢。*

### I. Test-First (NON-NEGOTIABLE) ✅
- 「目前生效」選版邏輯：unit test（多版本取 `<=now` 最新 / 未來版本不算 / 無版本→未定價）
- 新增驗證：unit/contract（負數拒絕 / 重複 (provider,model,effective_from) 拒絕）
- point-in-time 不變：integration（補新價後，歷史呼叫成本不變；新呼叫用新價）
- endpoints：contract test 先

### II. API 契約優先 ✅
- 3 個新 endpoint 先寫 OpenAPI（list / history / create）；既有計費端點不動

### III. 整合測試覆蓋外部依賴 ✅
- 端對端：未定價模型 → 補價 → 該模型新呼叫成本 > 0（接 proxy + usage）；歷史帳不變
- 既有 335 backend + 72 frontend 零回歸（SC-006）

### IV. 可觀測性 ✅
- 新增價格版本寫 audit `price_version_added`（details: provider, model, effective_from）
- 不洩漏 secret（價目非機密；無 PII）

### V. 簡潔優先 (YAGNI) ✅
- **不新增資料表 / 不改 schema**：沿用 `price_list`
- 複用 `pricing.lookup_price_for_call` 的 point-in-time 語意，不重寫
- 不做自動同步 / 多幣別 / 編輯刪除（spec 明確排除）
- audit 值加在既有 enum（`native_enum=False` VARCHAR(64) → 無需 migration）

**Pass**：無 deviation。

## Project Structure

### Documentation (this feature)

```text
specs/016-price-list-admin/
├── plan.md              # 本檔
├── research.md          # Phase 0：選版邏輯 / key 對應 / 無 migration / UI 位置 / audit
├── data-model.md        # Phase 1：沿用 PriceList（無變更）+ 查詢/DTO 形狀
├── quickstart.md        # Phase 1：4 驗收場景
├── contracts/
│   └── admin-prices.yaml  # list / history / create
├── checklists/requirements.md  # 已完成
└── tasks.md             # /speckit.tasks 產生
```

### Source Code (repository root)

```text
src/ai_api/
├── services/
│   └── pricing.py            # MODIFY: +list_catalog_prices() +list_history() +create_version()
├── api/
│   └── admin_prices.py       # NEW: GET /admin/prices, GET /admin/prices/history, POST /admin/prices
├── models/
│   └── auth_audit.py         # MODIFY: +price_version_added（無 migration，native_enum=False）

frontend/src/
├── routes/admin/
│   └── prices.tsx            # NEW: catalog 模型 × 目前價/未定價 + 展開歷史 + 新增版本 dialog
├── routes/admin/observability.tsx  # MODIFY: 加「價目」分頁
└── App.tsx                   # MODIFY: nested route observability/prices

tests/
├── unit/test_price_current_selection.py   # NEW: 選版 + 未定價 + 驗證
├── contract/test_admin_prices.py          # NEW
└── integration/test_price_admin_flow.py   # NEW: 補價→成本>0；歷史帳不變
```

**Structure Decision**：沿用既有結構。價目本質屬計費/觀測領域，UI 放「觀測」hub 加一個「價目」分頁（比照階段 6 把「分配」加進觀測；**不增頂層 sub-nav**，守階段 5.1 精簡）。後端查詢集中在既有 `pricing.py`，不另立 service。

## Complexity Tracking

無偏離 constitution，本節留空。
