# Implementation Plan: admin 依模型種類一鍵測試模型是否可用

**Branch**: `036-admin-model-test` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/036-admin-model-test/spec.md`

## Summary

模型詳情頁加一顆「測試模型」：後端依模型**種類**（對話／embedding／TTS／圖片生成／未支援）分派到對應的最小真實上游呼叫，結果即回應（沿用 test-connection / test-responses 的「結果即回應、NEVER 5xx」模式），依 slug 解出供應商憑證後呼叫。**種類判定**以 litellm `mode`（取自既有 `litellm_sync.raw.mode`）為主、`modality_input/output` 為退路——關鍵：`_modality` 把 embedding 也映成 `output=["text"]`，與 chat 撞型，故 chat↔embedding 必須靠 mode 區分。**會計費的種類（圖片、TTS）需確認**：後端對 billable 種類在未帶 `acknowledge_billable` 時回 `needs_confirmation`、不打上游；前端跳費用確認對話框後再帶旗標重打（成本閘門前後端雙保險）。測試呼叫沿用既有測試慣例＝真實上游呼叫 + 寫 audit（`model_tested`，歸戶 admin），**不**寫成員 CallRecord（與 test-responses 一致、無無歸屬影子用量）。補 `upstream.py` 的 `aembedding`/`aspeech`/`aimage_generation` 三個 wrapper（litellm 既有函式，已 `hasattr` 驗證）。**零 migration、零新套件**（`AuditEventType` 為非 native enum，加值不需 migration）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端），皆既有不變
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（library form：`acompletion`/`aresponses`/`aembedding`/`aspeech`/`aimage_generation`，皆既有套件內函式）；TanStack Query、shadcn/ui（前端）。**不新增套件。**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——只讀既有 `model_catalog`（modality + `litellm_sync.raw.mode`）。
**Testing**: pytest（後端 unit + integration）；前端 vitest。
**Target Platform**: Linux server（k3s）；前端瀏覽器。
**Project Type**: web application（backend `src/ai_api/` + frontend `frontend/src/`）。
**Performance Goals**: 測試為 admin 明確觸發、單次最小呼叫；不在成員熱路徑。對話 1-token、embedding 短字串、TTS 極短文字、圖片最小尺寸。
**Constraints**: 種類判定對所有模型可行（含手動建立，無 `litellm_sync` 者退 modality）；billable 種類必先確認；結果即回應不 5xx；測試呼叫可歸戶（audit），不產生無歸屬影子用量。
**Scale/Scope**: 約 3 處後端（`upstream.py` 三 wrapper、`model_kind` 判定 helper、`admin_catalog` 測試端點 + audit 值）+ 約 1 處前端（model-detail 測試按鈕 + billable 確認對話框）+ admin `_to_dict` 加 `test_kind`/`test_billable` 衍生欄。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 嚴格 TDD。先寫 unit（`model_kind` 各種 modality/mode 組合判定）+ integration（每種測法成功/失敗結果即回應、billable 未確認回 needs_confirmation 不打上游、未支援種類給說明、無憑證給說明、audit 寫入）失敗，再實作。
- **II. API 契約優先（Contract-First）**：✅ 新端點契約寫在 `contracts/`；沿用既有「結果即回應」慣例。
- **III. 整合測試覆蓋外部依賴**：✅ 上游各呼叫（completion/embedding/speech/image）以 mock/AsyncMock 覆蓋成功與失敗路徑。
- **IV. 可觀測性**：✅ 失敗回帶上游原因；每次測試寫 audit（`model_tested`：kind/ok/latency），admin 可追。
- **V. 簡潔優先（YAGNI）**：✅ **零 migration、零新套件**；單一 `model_kind` helper + 單一測試端點分派，不為每種類各開一個端點；複用既有憑證解析與「結果即回應」模式。
- **語言與文件規範**：✅ 回覆繁體中文；程式註解英文為主。

**結論**：無違反，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/036-admin-model-test/
├── plan.md              # 本檔
├── research.md          # Phase 0：種類判定、upstream wrapper、成本閘門、計費歸屬 決策
├── data-model.md        # Phase 1：model_kind 判定表（無 schema 變更）
├── quickstart.md        # Phase 1：四種 + 未支援 的手動驗收路徑
├── contracts/
│   └── model-test.md    # 測試端點契約 + 前端 UI 契約
├── checklists/
│   └── requirements.md  # 已通過（0 NEEDS CLARIFICATION）
└── tasks.md             # Phase 2（/speckit.tasks，非本指令產生）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   └── upstream.py             # 新增 aembedding / aspeech / aimage_generation wrapper
│                               #   （沿用 acompletion/aresponses 的憑證+extra 注入模式）
├── services/
│   └── model_kind.py           # 【新】model_kind(model) → chat|embedding|tts|image|stt|unknown
│                               #   優先 litellm_sync.raw.mode，退 modality_output/input
├── api/
│   └── admin_catalog.py        # 新端點 POST .../{slug}/test：分派 + billable 確認閘門 + audit；
│                               #   _to_dict 加 test_kind / test_billable 衍生欄
└── models/
    └── auth_audit.py           # 加 AuditEventType.model_tested（非 native enum，無 migration）

frontend/src/
└── routes/admin/model-detail.tsx   # 「測試模型」按鈕（與既有「測試 responses」並列）；
                                     #   billable（圖片/TTS）跳 AlertDialog 費用確認；讀 test_kind

tests/
├── unit/
│   └── test_model_kind.py          # 【新】種類判定矩陣
└── integration/
    └── test_admin_model_test.py    # 各種法成功/失敗、needs_confirmation、未支援、無憑證、audit
```

**Structure Decision**：既有 web application 佈局。新增 `services/model_kind.py`（種類判定單一真相）與 `upstream.py` 三個 wrapper；其餘改既有檔。不動 schema、不動計費路徑（測試走 audit 非 CallRecord）。

## Complexity Tracking

> 無 Constitution 違反，留空。
