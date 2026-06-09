# Implementation Plan: 對成員開放 `/v1/embeddings` 端點

**Branch**: `038-embeddings-endpoint` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/038-embeddings-endpoint/spec.md`

## Summary

新增 `proxy/embeddings.py`：`POST /v1/embeddings` 是 `proxy/router.py`（chat）的近乎複製——body 收 `{model, input}`、跑**同一條** `run_preflight`、呼 `upstream.aembedding`、取回應 `usage.prompt_tokens` → 既有 `lookup_price_for_call` + `calculate_cost`（completion=0）→ `RecordsService.record_call` 歸戶分配。掛在 `/v1`。上游錯誤走既有 `upstream_error`。前端 `api-usage-example` 對 embedding 模型顯 `/v1/embeddings` 範例——為此在成員目錄序列化（`catalog.py`）加一個唯讀衍生欄 `kind`（呼 `services/model_kind.py`，讀既有 `litellm_sync.raw.mode`）。**已實測 `litellm.EmbeddingResponse.model_dump()` 的 `usage` 帶 `prompt_tokens`/`total_tokens`/`completion_tokens=0`**——計費沿用 token、`calculate_cost` 對 completion=0 已正確。**零新表、零 migration、零新套件。**

## Technical Context

**Language/Version**: Python 3.11+（後端為主）/ TypeScript strict + React 19（前端僅範例顯示）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、`litellm`（library form：`aembedding` 既有函式）；前端 shadcn/ui（皆既有，**不新增套件**）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——embedding 呼叫沿用既有 `CallRecord` + token 計費（`PriceList`）。
**Testing**: pytest（contract：embeddings 成功/計費/擋下/上游錯誤）；前端 vitest（api-usage-example embedding 範例）。
**Target Platform**: Linux server（k3s）；瀏覽器（範例顯示）。
**Project Type**: web application（backend `src/ai_api/` + frontend `frontend/src/`）。
**Performance Goals**: embedding 為非串流單次呼叫，走既有熱路徑等價成本；無新增負擔。
**Constraints**: 沿用同一條 preflight（不另立授權）；計費沿用 token（不做計費一般化）；上游金鑰不外洩；零回歸。
**Scale/Scope**: 約 2 處後端（新 `proxy/embeddings.py` + `main.py` 掛載；`catalog.py` 加衍生 `kind`）+ 約 1 處前端（`api-usage-example` 加 embedding 範例 + `catalog-detail` 傳 kind）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 嚴格 TDD。先寫 contract（`/v1/embeddings` 成功回向量 + 記一筆 input-token 計費歸戶分配、`model_forbidden`/`model_mismatch`、401、上游錯誤回 `upstream_error`）+ 前端（embedding 模型詳情顯 `/v1/embeddings` 範例）失敗，再實作。
- **II. API 契約優先**：✅ `/v1/embeddings`（OpenAI 相容）+ 成員目錄 `kind` 衍生欄契約寫在 `contracts/`。
- **III. 整合測試覆蓋外部依賴**：✅ `upstream.aembedding` 以 mock 覆蓋成功與失敗；計費走真實 PriceList 查詢。
- **IV. 可觀測性**：✅ 成功記 `CallRecord(success, input token, cost)`；上游失敗記 `upstream_error` 帶上下文（沿用 chat）。
- **V. 簡潔優先（YAGNI）**：✅ **零 migration、零套件、零新表**；複製既有 chat router、複用 preflight + token 計費；**不做計費一般化**（embedding 仍 token，留給階段 29 增量 ②）。
- **語言與文件規範**：✅ 回覆繁體中文；程式註解英文為主。

**結論**：無違反，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/038-embeddings-endpoint/
├── plan.md              # 本檔
├── research.md          # Phase 0：router 複製、usage shape（已驗）、計費複用、kind 衍生欄、零回歸
├── data-model.md        # Phase 1：CallRecord 複用 + kind 衍生（無 schema 變更）
├── quickstart.md        # Phase 1：US1–US3 手動驗收
├── contracts/
│   └── embeddings.md    # /v1/embeddings 契約 + 目錄 kind 衍生欄 + 前端範例契約
├── checklists/requirements.md   # 已通過（0 NEEDS CLARIFICATION）
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   └── embeddings.py           # 【新】POST /v1/embeddings：clone proxy/router.py，body=input、
│                               #   run_preflight → upstream.aembedding → usage.prompt_tokens →
│                               #   calculate_cost(completion=0) → record_call
├── main.py                     # include embeddings_router, prefix="/v1"
└── api/
    └── catalog.py              # 成員目錄序列化加唯讀衍生 kind（呼 services/model_kind）

frontend/src/
├── components/
│   └── api-usage-example.tsx   # 加 embedding 範例（/v1/embeddings：curl/python/js）；
│                               #   新增 prop（如 kind / isEmbedding）切換
└── routes/
    └── catalog-detail.tsx      # 依模型 kind 傳給 ApiUsageExample（embedding → 顯 /v1/embeddings）

tests/
├── contract/
│   └── test_embeddings.py      # 【新】成功+計費、model_forbidden/model_mismatch、401、upstream_error
└── （前端）__tests__/api-usage-example*.test.tsx  # embedding 範例顯示
```

**Structure Decision**：既有 web application 佈局。後端新增唯一檔 `proxy/embeddings.py`（chat router 的 endpoint 變體），其餘改既有檔（main 掛載、catalog 加衍生欄）。不動 schema、不動計費結構、不動既有端點。

## Complexity Tracking

> 無 Constitution 違反，留空。
