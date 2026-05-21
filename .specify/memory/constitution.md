# AI API Manager Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)
強制執行 TDD：所有功能必須先撰寫測試、經使用者確認、確認測試失敗 (Red)、再撰寫實作使其通過 (Green)、最後重構 (Refactor)。
- 嚴禁先寫實作再補測試。
- 任何 PR 若新增/修改行為而沒有對應先行測試，視為違反憲章，必須退回。
- 缺陷修復也須先以可重現該缺陷的失敗測試開始。

### II. API 契約優先 (Contract-First)
API 行為由契約定義，而非由實作反推。
- 先以 OpenAPI / JSON Schema 定義端點、請求與回應、錯誤格式，並通過審查後才進入實作。
- 契約變更必須伴隨版本標記 (semver) 與相容性說明；破壞性變更需有遷移指南。
- 契約測試 (contract tests) 為合併前必過關卡。

### III. 整合測試覆蓋外部依賴
與 Azure AI 服務、資料庫、訊息佇列等外部系統的互動，必須以整合測試驗證。
- 不得僅以 mock 取代真實邊界行為驗證；mock 僅用於單元測試層。
- 跨服務契約變更、共享 schema 變更、新外部依賴接入時，整合測試為必要條件。
- 整合測試應可在 CI 中以可重現的方式執行（容器化或受控 sandbox）。

### IV. 可觀測性 (Observability)
所有 API 與背景作業必須可被觀測、追蹤、除錯。
- 採用結構化日誌 (JSON)，包含 trace ID、request ID、使用者/租戶識別（去識別化後）。
- 對外部依賴的呼叫必須記錄延遲、狀態碼與重試資訊。
- 錯誤必須帶有可定位的錯誤代碼，且絕不在日誌或回應中洩漏密鑰與 PII。

### V. 簡潔優先 (YAGNI)
從最簡單可行的設計開始，僅在需求明確時引入抽象。
- 禁止為「未來可能需要」而新增旗標、抽象層、外掛機制。
- 三段相似程式碼可以保留；證實有第四個使用情境時再抽象。
- 任何違反此原則的複雜度，必須在 PR 描述中明文說明理由。

## 語言與文件規範

- 規格文件 (spec)、計畫 (plan)、任務 (tasks)、checklist、ADR 等規範性文件，一律以**繁體中文**撰寫。
- 程式碼識別字（變數、函式、型別、檔名、API 路徑、欄位名）一律使用英文，遵循各語言慣例。
- 程式碼註解原則上以英文撰寫；如需說明業務邏輯或法規背景，可使用繁體中文，但必須完整保留標點與字符（不得以 ASCII 替代）。
- 與使用者互動的回覆（CLI 訊息、錯誤訊息對外文案）若面向中文使用者，使用繁體中文；面向程式或外部 API 的訊息使用英文。
- commit message 與 PR 標題使用英文（祈使語氣），PR 描述可雙語。

## 開發工作流程與品質關卡

- 任何功能必須依序通過：spec → plan → tasks → 失敗測試 → 實作 → 重構 → 審查 → 合併。
- PR 合併前必過關卡：
  1. 契約測試通過。
  2. 單元測試 + 整合測試通過，覆蓋率不低於既有水準。
  3. Lint / 型別檢查無錯誤。
  4. 至少一名審查者確認 TDD 流程被遵守（檢視 commit 順序：測試先於實作）。
- 任何對 constitution 的偏離，必須在 PR 中以「Constitution Deviation」標題明列原則、偏離理由、補救計畫。

## Governance

本 constitution 凌駕於所有其他開發慣例之上。
- 修訂須以 PR 方式提出，並更新版本號與 `Last Amended` 日期；版本採 semver：
  - MAJOR：移除/重新定義既有原則或變更治理結構。
  - MINOR：新增原則或實質擴充章節。
  - PATCH：澄清、措辭、錯字。
- 所有 PR 審查者必須驗證合規性；複雜度與例外必須有書面理由。
- 執行期的開發指引（風格、工具用法等）放在 `CLAUDE.md` 或對應的 agent guidance 檔案，不得與本 constitution 衝突。

**Version**: 1.0.0 | **Ratified**: 2026-05-21 | **Last Amended**: 2026-05-21

<!-- Knowie: Project Knowledge -->
## Project Knowledge

This project maintains structured knowledge in `knowledge/`:

- **Principles** (`knowledge/principles.md`): Core axioms and derived development principles — the project's non-negotiable rules.
- **Vision** (`knowledge/vision.md`): Goals, current state, architecture decisions, and roadmap.
- **Experience** (`knowledge/experience.md`): Distilled lessons from past development — patterns, pitfalls, and takeaways.

Read these files at the start of any task to understand the project's *why* and constraints.
Additional context may be found in `knowledge/research/`, `knowledge/design/`, and `knowledge/history/`.
<!-- /Knowie -->
