# Implementation Plan: responses 支援判斷（實測 + 手動雙來源）

**Branch**: `035-responses-support-detection` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/035-responses-support-detection/spec.md`

## Summary

把「某模型能否走 `/v1/responses`（Codex/Agent 入口）」從**靜態能力旗標事前硬擋**改為**雙來源判定**：runtime 預設先試（打得通就用、打不通回真實上游錯誤），唯一的事前封鎖是 admin 手動標「不可用」；admin 可按「測試 responses」做極小真實呼叫實測，或手動覆寫；目錄顯示「Agent 相容（Responses）」徽章 + 來源（實測/手動），成員可篩。responses（軸③ gateway 端點可用性）與 LiteLLM 的 mode（軸①）/ 能力旗標（軸②）**徹底解耦**：移除 `_capabilities` 的 mode→responses 衍生，LiteLLM 採納改 **merge-preserve**（永不增刪 `responses*` 標記）。

技術手段：responses 狀態 + 來源以**既有 `capabilities` JSON 欄的內部標記約定**承載（`responses` / `responses:blocked` / `responses:tested` / `responses:manual`），集中在單一 helper `responses_support.py` 管理讀寫，成員 facet 過濾掉冒號內部標記只顯示徽章。**零 migration、零新欄、零新套件、計費不變**。本階段並一併把上一輪 i18n 修正（hyphen 詞彙 + 缺漏標籤，現滯留於未上線 commit）併入乾淨上線。

## Technical Context

**Language/Version**: Python 3.11+（後端，既有不變）/ TypeScript strict + React 19 + Vite 6（前端，既有不變）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（aresponses 橋接，既有）；TanStack Query、shadcn/ui（前端，既有）。**不新增套件。**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——responses 狀態以既有 `model_catalog.capabilities`（JSON list）的標記約定承載。
**Testing**: pytest（後端 unit + integration）；前端沿用既有元件。
**Target Platform**: Linux server（k3s）；前端瀏覽器。
**Project Type**: web application（backend `src/ai_api/` + frontend `frontend/src/`）。
**Performance Goals**: 「測試 responses」為 admin 明確觸發、單次極小呼叫（1-token）；不在成員熱路徑反覆自動測。runtime 軟化閘門移除事前 reject，改直接走既有上游呼叫，無新增延遲。
**Constraints**: 三軸解耦（responses ≠ mode ≠ 能力旗標）；手動優先（覆寫實測）；LiteLLM 同步 MUST NOT 增刪 responses 狀態。
**Scale/Scope**: 約 4 處後端（軟化閘門、`responses_support.py` helper、admin 測試/覆寫端點、litellm_registry + admin_catalog merge-preserve）+ 約 3 處前端（model-detail「測試/覆寫」UI、目錄徽章來源、成員 facet 過濾 + i18n 併入）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 嚴格 TDD。先寫 unit（`responses_support` 標記狀態機、`_capabilities` 不再含 responses、apply merge-preserve）+ integration（軟化閘門：未標記模型先試、手動 blocked 事前擋、測試端點結果即回應、手動覆寫優先）失敗，再實作。
- **II. API 契約優先（Contract-First）**：✅ 新增端點（測試 responses、手動設定）契約寫在 `contracts/`；沿用既有「測試連線」結果即回應慣例。
- **III. 整合測試覆蓋外部依賴**：✅ 上游 responses 呼叫以既有測試替身/mock 覆蓋；測試端點與軟化閘門皆有 integration。
- **IV. 可觀測性**：✅ runtime 不支援回帶上游原因的 `upstream_error`（非無資訊 400）；admin 測試/覆寫寫 audit。
- **V. 簡潔優先（YAGNI）**：✅ **零 migration、零新欄、零新套件**；複用既有 `capabilities` 欄與既有「測試連線」模式。標記約定集中於單一 helper，不散落。
- **語言與文件規範**：✅ 回覆繁體中文；程式註解英文為主、業務說明可中文且保留完整標點。

**結論**：無違反，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/035-responses-support-detection/
├── plan.md              # 本檔
├── research.md          # Phase 0：儲存承載/軟化閘門/測試端點複用/merge-preserve/i18n 併入 決策
├── data-model.md        # Phase 1：capabilities 標記子狀態機（無 schema 變更）
├── quickstart.md        # Phase 1：四條 user story 的手動驗收路徑
├── contracts/
│   └── responses-support.md   # 新端點契約 + 軟化閘門行為 + 前端 UI 契約
├── checklists/
│   └── requirements.md  # 已通過（0 NEEDS CLARIFICATION）
└── tasks.md             # Phase 2 輸出（/speckit.tasks，非本指令產生）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   └── responses.py            # 軟化閘門：移除靜態 model_supports_responses 事前擋，
│                               #   改為僅在「手動 blocked」時事前擋；其餘先試（既有上游呼叫）
├── services/
│   ├── responses_support.py    # 【新】單一 helper：capabilities 標記讀寫狀態機
│   │                           #   (available/unavailable/unknown + source tested/manual)
│   └── litellm_registry.py     # 移除 _capabilities 的 mode→responses 衍生（FR-006）
└── api/
    ├── admin_catalog.py        # 「測試 responses」+「手動設定」端點；apply 改 merge-preserve
    └── catalog.py              # 成員目錄序列化：過濾內部標記、輸出 responses 徽章 + 來源

frontend/src/
├── routes/admin/model-detail.tsx   # admin「測試 responses」按鈕 + 手動可用/不可用切換 + 來源顯示
├── routes/catalog 相關             # 成員目錄徽章 + 來源；「Agent 相容」篩選
└── lib/catalog-labels.ts           # 併入 i18n 修正（hyphen 詞彙 + 缺漏標籤，確認對齊）

tests/
├── unit/
│   ├── test_responses_support.py       # 【新】標記狀態機
│   └── test_litellm_registry.py        # 改：chat mode 不再產生 responses；merge-preserve
└── integration/
    └── test_responses_*.py             # 軟化閘門、測試端點、手動覆寫優先
```

**Structure Decision**：既有 web application 佈局。本功能新增唯一檔案 `src/ai_api/services/responses_support.py`（集中標記約定），其餘皆改既有檔。不動 schema、不動計費、不動 proxy 其餘行為。

## Complexity Tracking

> 無 Constitution 違反，留空。
