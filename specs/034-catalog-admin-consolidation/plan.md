# Implementation Plan: 模型目錄 admin 體驗整合 + 充分利用 LiteLLM

**Branch**: `034-catalog-admin-consolidation` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/034-catalog-admin-consolidation/spec.md`

## Summary

把階段 23 接好的 LiteLLM 從「散在三個世代畫面」收斂成**模型詳情頁單一中樞**：詳情頁每個可同步欄位顯示**來源徽章**（litellm/borrowed/manual，資料來自既有 `litellm_sync.field_sources`）、「**檢查 LiteLLM 更新**」入口前移到詳情頁（重用既有 `LiteLLMUpdateDiff`，它本就同時列 metadata + 價格差異）、新增唯讀「**LiteLLM 原始資訊**」面板。退役價格 `prices.tsx` 的硬編 `TEMPLATES`，改用既有 `GET /admin/catalog/litellm/suggest/{key}`（同一來源）。後端把 LiteLLM 吃得更乾淨：`litellm_registry` 能力旗標映射 2→~10、`litellm_sync` 多存**完整 raw entry**（供唯讀面板）。**零 migration、零新套件、不改計費引擎、不升 mode 為可篩選欄。**

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端少量擴充）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（既有）、TanStack Query、shadcn/ui。**不新增套件。**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**無新 migration**——沿用階段 23 `model_catalog.litellm_sync`（JSON 欄）多存 `raw`；價格沿用 `price_list`。
**Testing**: pytest（adapter/contract）；Vitest + RTL（前端）
**Target Platform**: Kubernetes（admin Web UI + 後端）
**Project Type**: Web application（前後端）
**Performance Goals**: 詳情頁即時；帶入/建議讀記憶體 `model_cost`；檢查更新沿用階段 23 線上抓（timeout 回退）
**Constraints**: 計費唯一真理為自有價目表；手動欄不被採納覆寫；零回歸（admin + 成員端目錄篩選）
**Scale/Scope**: 主要前端（詳情頁整合 + 退役範本 + 唯讀面板）+ 後端小擴充（能力映射 + raw 快照）；**0 新端點**（重用 search/suggest/check/apply）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 後端先改/加失敗測試（能力旗標擴充、`litellm_sync.raw` 落地、provenance 不變）；前端先紅後綠（徽章、檢查更新入口、唯讀面板、價格 LiteLLM 帶入）。
- **II. API 契約優先**：✅ **不新增端點**——重用階段 23 的 search/suggest/litellm-check/litellm-apply；adapter 輸出形狀擴充（能力 + raw）以契約測試固化。
- **III. 整合測試覆蓋外部依賴**：✅ litellm 為外部資料源；bundled `model_cost` 真實值驗能力映射；線上抓 timeout/回退已於階段 23 mock 驗、不變。
- **IV. 可觀測性**：✅ 不動後端日誌/錯誤碼；採納仍留稽核（階段 23）。
- **V. 簡潔優先（YAGNI）**：✅ 收斂重疊路徑（退役硬編範本、合併編輯入口）= 減複雜度；能力只取決策相關約 10 個、其餘 raw 唯讀（不鏡像全部 153 欄到主欄位）；**不升 mode 為可篩選欄**（無 migration）。

**結論**：全數通過。本階段**降低**既有複雜度（並行路徑收斂），唯一新增是「能力映射擴充 + raw 快照 + 前端整合」，無 schema、無端點、無套件。

## Project Structure

### Documentation (this feature)

```text
specs/034-catalog-admin-consolidation/
├── plan.md              # 本檔
├── research.md          # Phase 0：能力旗標子集、raw 快照、退役範本、徽章/面板放法
├── data-model.md        # Phase 1：litellm_sync 擴 raw + 能力映射表（無新欄）
├── quickstart.md        # Phase 1：驗收腳本
├── contracts/
│   └── ui-and-adapter.md  # Phase 1：重用端點 + adapter 輸出擴充 + 詳情頁 UI 契約
├── checklists/requirements.md  # 規格品質（已通過）
└── tasks.md             # Phase 2（/speckit.tasks 產出）
```

### Source Code (repository root)

```text
src/ai_api/services/litellm_registry.py     # _capabilities 2→~10 旗標；metadata 帶 max_output_tokens（入 raw）
src/ai_api/api/admin_catalog.py             # _build_litellm_sync / litellm-apply：litellm_sync 多存 raw（完整 entry）
tests/unit/test_litellm_registry.py         # 擴充能力映射斷言
tests/contract/test_admin_create_with_litellm.py  # litellm_sync.raw 落地斷言

frontend/src/routes/admin/
├── model-detail.tsx     # 【中樞】CatalogModel 加 litellm_sync；每欄來源徽章；「檢查 LiteLLM 更新」入口（接 LiteLLMUpdateDiff）；唯讀「LiteLLM 原始資訊」面板
└── prices.tsx           # 退役硬編 TEMPLATES → LiteLLM 建議價（reuse /litellm/suggest/{provider}/{model}）
frontend/src/components/
├── litellm-update-diff.tsx     # 既有，重用（詳情頁掛載）
├── field-source-badge.tsx      # 【新】小元件：依 field_sources 顯示徽章
└── litellm-raw-panel.tsx       # 【新】唯讀面板：展開顯示 litellm_sync.raw
frontend/src/__tests__/...      # 對應前端測試
```

**Structure Decision**：Web application 既有結構，主力在 `frontend/src/routes/admin/model-detail.tsx`（變成中樞）與 `prices.tsx`（退役範本）。後端只擴充 `litellm_registry` 能力映射與 `admin_catalog` 的 `litellm_sync.raw` 落地——**無新端點、無 migration**。重用階段 23 的 `LiteLLMUpdateDiff` 與 suggest 端點是本計畫降複雜度的關鍵。

## Complexity Tracking

> 無違規，免填。本階段淨**降低**複雜度（收斂三畫面、退役並行範本）。
