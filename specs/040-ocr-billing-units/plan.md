# Implementation Plan: 計費一般化（非 token 單位）+ OCR 端點

**Branch**: `040-ocr-billing-units` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/040-ocr-billing-units/spec.md`

## Summary

把計費層（`PriceList` / `CallRecord` / `calculate_cost`）從 token 中心**加欄式**一般化成能裝非 token 單位（首個＝**page**），並對成員開放 `POST /v1/ocr`——OCR 模型走同一條 `run_preflight`、以 `len(OCRResponse.pages)` 計量、按「每頁價」計費、歸戶分配。新增 `upstream.aocr` wrapper、`model_kind` 加 `ocr`、前端詳情頁顯 `/v1/ocr` 範例、admin 可設/覆寫每頁價。**token 路徑完全不動（零回歸）**；migration `0019` 只加 nullable 欄；不新增套件。

OCR 之所以是「計費一般化」的證明消費者：實測 litellm `model_cost` 發現 Azure `gpt-image-*` 其實是 token 計費（不觸發一般化），而 `azure_ai/mistral-document-ai` / `doc-intelligence` 是乾淨的 `ocr_cost_per_page`（per-page）、JSON 進出（`document` dict，非 multipart）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`litellm`（library：`aocr` 既有函式）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0019`**——`price_list` 加 `price_unit`(nullable)+`price_per_unit_usd`(nullable)；`call_records` 加 `quantity`(nullable)+`unit`(nullable)。**純加欄**（token 欄不動、不改 nullability，避開 SQLite ALTER COLUMN 重建）
**Testing**: pytest（contract + integration）；前端 vitest + Testing Library
**Target Platform**: Linux server（k8s）+ 瀏覽器 SPA
**Performance Goals**: OCR 為一般 proxy 呼叫；計費為純計算，無額外延遲
**Constraints**: token 計費結果零回歸；非 token 呼叫此階段不被 token 配額擋下（已知限制）；migration 加欄式、單一 head；`document` 走 JSON（無 multipart/binary）
**Scale/Scope**: 後端：1 migration + 計費層 3 處一般化（PriceList/CallRecord/pricing）+ 1 新端點（`proxy/ocr.py`）+ `upstream.aocr` + `model_kind` 加 ocr + admin 價格端點擴充；前端：詳情頁 OCR 範例 + admin 每頁價欄 + 用量顯示「N 頁」

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 先寫失敗測試——計費一般化（per-page cost 計算、PriceList 存查每頁價）、OCR 端點（計量歸戶 / 拒絕 / 上游錯誤）、token 零回歸、目錄 kind，皆 test-first。
- **II. 契約優先**：✅ Phase 1 先定 `POST /v1/ocr` 契約 + 價格端點每頁價擴充 + 錯誤格式。
- **III. 整合測試覆蓋外部依賴**：✅ 計費一般化以**整合/契約測試**驗真實數學（頁數 × 每頁價 = cost、改價 point-in-time）；OCR 上游以 mock（`litellm.aocr`）驗計量/錯誤分支——對齊既有 embeddings 測試做法（mock upstream、真 DB 計費）。
- **IV. 可觀測性**：✅ OCR 成功/失敗皆記 `CallRecord`（含 quantity/unit/cost）；上游錯誤記 `upstream_error` + 帶上下文 log；憑證去敏（沿用 `redact_string`）。
- **V. YAGNI**：✅ 只加「page」一個新單位 + 一個通用的 `(quantity, unit)` 維度；**不**預先建 per-second/per-character/per-image 的專用欄（unit 是字串維度，未來加單位＝加資料不改 schema）。不做圖表改版、不做每單位上限、不做 binary I/O。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/040-ocr-billing-units/
├── plan.md              # 本檔
├── research.md          # Phase 0：7 個決策（PriceList/CallRecord 加欄形狀、頁數來源、端點形狀、kind、配額、litellm 建議價）
├── data-model.md        # Phase 1：計費一般化的 schema 增量 + OCR 計量流
├── quickstart.md        # Phase 1：US1–US4 + token 零回歸驗收
├── contracts/
│   └── ocr-and-pricing.md  # Phase 1：/v1/ocr + 價格端點每頁價擴充
└── tasks.md             # Phase 2（/speckit.tasks 產生）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── price_list.py        # 加 price_unit + price_per_unit_usd（nullable）
│   └── call_record.py        # 加 quantity + unit（nullable）
│   (migration 在 repo root `alembic/versions/0019_billing_units.py`，純加欄)
├── services/
│   ├── pricing.py            # Price 加 per-unit 欄；lookup 帶出；新增 calculate_unit_cost
│   ├── records.py            # record_call 加 quantity/unit 參數（nullable）
│   └── model_kind.py         # Kind 加 "ocr"；mode=="ocr" → ocr
├── proxy/
│   ├── ocr.py                # 新：POST /ocr（複製 embeddings.py 結構）
│   └── upstream.py            # 加 aocr wrapper
├── api/
│   ├── catalog.py            # kind 已輸出（Phase 38）；ocr 自動帶 kind=ocr
│   └── admin_prices.py        # PriceCreateRequest + 序列化加每頁價（選填）
└── main.py                    # mount ocr_router 於 /v1

tests/
├── contract/
│   ├── test_ocr.py                  # OCR 端點：計量歸戶 / 拒絕 / 上游錯誤
│   ├── test_pricing_units.py         # 每頁價存查 + cost 計算 + point-in-time
│   └── test_catalog_kind.py（擴充）  # ocr 模型 kind=ocr
└── integration/
    └── test_billing_generalization.py # token 零回歸 + page 計費端到端（mock aocr）

frontend/src/
├── components/api-usage-example.tsx   # 加 OCR 範例（kind==="ocr" → /v1/ocr）
├── routes/catalog-detail.tsx          # 依 kind 傳 OCR 範例
├── routes/admin/prices.tsx（或對應）  # admin 每頁價輸入
└── __tests__/...                       # OCR 範例 + 每頁價 UI 測試
```

**Structure Decision**: web application。計費一般化集中在 `models/{price_list,call_record}` + `services/{pricing,records}`（加欄 + 通用計算），OCR 端點沿用 embeddings 的 `proxy/*.py` 樣板 + `upstream` adapter（原則 7：加端點＝同一條 preflight + 對應 litellm 函式 + 記帳）。前端沿用 `api-usage-example` 的 kind 切換（Phase 38 已建）。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
