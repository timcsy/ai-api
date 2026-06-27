# Implementation Plan: OpenAI 相容 `/v1/models` ＋ Copilot 上卡

**Branch**: `050-openai-models-copilot` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/050-openai-models-copilot/spec.md`

## Summary

補上 OpenAI 相容的模型發現端點 `GET /v1/models` 與 `GET /v1/models/{id}`，回傳**呼叫金鑰 scope 內、狀態為 active 的分配對應模型**（識別碼＝該分配的正規 slug `resource_model`，與 proxy 路由所用一致）。以此為前提真機驗證 GitHub Copilot，並在既有應用商店註冊表加一張 Copilot 卡（含跨 model 開新對話的說明）。後端純讀既有資料（金鑰→分配），**不碰上游、不新增表/migration/套件**；前端純加註冊表一筆 + 一個詳情元件。續接 fail-loud 行為已存在，本功能僅微調訊息可操作性與卡上文案。

技術取向（來自 research）：`/v1/models` 走與其他 `/v1` 端點相同的 Bearer 認證（`parse_bearer_token` → `lookup_credential_by_token`），新增一個 service 方法列舉金鑰 scope 內 **active** 分配的模型；序列化成 OpenAI `{object:"list", data:[{id, object:"model", created, owned_by}]}`。**scope 來源是「金鑰被授予的分配」本身（即存取授權），不再疊套 catalog 瀏覽過濾**——分配存在即代表已被授權，重複套政策反而可能分歧。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2（後端）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——`/v1/models` 純讀既有 `credentials` / `credential_allocations` / `allocations` / `model_catalog`
**Testing**: pytest（contract / integration / unit）；Vitest + Testing Library（前端）
**Target Platform**: Linux server（distroless 容器，K8s）；前端 nginx 靜態 SPA
**Project Type**: web（backend + frontend）
**Performance Goals**: 模型發現為單次 DB 讀取（金鑰→分配 join），p95 與既有 `/catalog/models` 同級；無上游往返
**Constraints**: 回傳識別碼必須與 `resource_model`（preflight 路由鍵）逐字一致（SC-002）；列舉只含 active 分配（FR-006）；無金鑰 → 401（FR-004）
**Scale/Scope**: 一把金鑰 scope 內模型數通常個位數至數十；`UNIQUE(credential_id, resource_model)` 保證金鑰內模型不重複

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 先寫 `/v1/models` contract 測試（list / retrieve / 401 / scope 隔離 / 排除 paused·revoked / 未定價仍列 / id 可路由）跑紅，再實作。前端先寫 Copilot 卡渲染測試。
- **II. 契約優先（Contract-First）**：✅ Phase 1 先出 `contracts/v1-models.md`（OpenAI 相容 list/retrieve schema + 錯誤格式），審後實作；屬**新增端點、非破壞**（既有 `/v1/*` 不動）。
- **III. 整合測試覆蓋外部依賴**：✅ `/v1/models` 不呼叫上游（純 DB），contract/unit 即足夠；與外部客戶端（GitHub Copilot）的真實邊界以**真機驗收**（SC-004）覆蓋，沿用階段 19/32 模式。無新外部依賴接入。
- **IV. 可觀測性**：✅ 沿用既有對外端點錯誤格式（`{error:{code,message}}`）與 401 行為；不洩漏 scope 外資訊。
- **V. 簡潔優先（YAGNI）**：✅ 重用既有 service / 目錄資料；無新表、無 migration、無新套件、無新抽象。新增僅一個唯讀端點 + 一個 service 方法 + 一張前端卡。

**結論**：無違反、無 Complexity Tracking 需求、Technical Context 無 NEEDS CLARIFICATION。

## Project Structure

### Documentation (this feature)

```text
specs/050-openai-models-copilot/
├── plan.md              # 本檔
├── research.md          # Phase 0 產出
├── data-model.md        # Phase 1 產出
├── quickstart.md        # Phase 1 產出
├── contracts/
│   └── v1-models.md     # Phase 1 產出（OpenAI 相容 list/retrieve 契約）
├── checklists/
│   └── requirements.md  # /speckit-specify 已產出
└── tasks.md             # /speckit-tasks 產出（本指令不建立）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   └── models.py            # 【新】GET /v1/models、GET /v1/models/{id:path}（Bearer 認證、唯讀）
├── services/
│   └── allocations.py       # 【改】加 list_active_scope_allocations(credential)（join Allocation 過濾 active）
└── main.py                  # 【改】include_router(models_router, prefix="/v1")

tests/
├── contract/
│   └── test_v1_models.py    # 【新】list/retrieve/401/scope 隔離/排除非 active/未定價仍列/id 路由
└── integration/
    └── （沿用既有；如需以真 Postgres 驗 scope 隔離可加一支）

frontend/src/
├── lib/
│   └── applications.tsx     # 【改】註冊表加 copilot 一筆 {id,name,Logo,Detail}
├── components/
│   ├── copilot-app-detail.tsx  # 【新】設定步驟 + 建金鑰捷徑 + 跨 model 開新對話說明
│   └── app-logos.tsx        # 【改】加 CopilotLogo（inline SVG）
└── __tests__/
    └── apps-copilot.test.tsx   # 【新】Copilot 卡渲染 + 零分配指引 + 跨 model 文案
```

**Structure Decision**: 沿用既有 web 結構（`src/ai_api` 後端、`frontend/src` 前端）。後端新增 `proxy/models.py`（與 `proxy/router.py`/`responses.py` 同層的對外 `/v1` 端點），認證重用 `proxy/auth.py`、資料重用 `services/allocations.py`；前端沿用階段 28 的應用商店註冊表（`applications.tsx` 加一筆＝一張卡 + 一詳情）。

## Phase 0：研究（research.md）

待解技術點（皆有明確既有先例，無 NEEDS CLARIFICATION）：
- **R1**：`/v1/models` 的 scope 來源——金鑰 active 分配 vs catalog 瀏覽過濾。
- **R2**：模型識別碼形式（正規 slug vs bare），確保「列出 → 原樣呼叫」對得上。
- **R3**：OpenAI `GET /v1/models` 回應 schema 與 `created`/`owned_by` 欄位取值。
- **R4**：retrieve 單一模型的 not-found 語意與 bare-slug alias 是否套用。
- **R5**：GitHub Copilot 接入本平台的設定形態（驗證計畫 + 已知坑：模型清單、embeddings、跨 model 續接）。

## Phase 1：設計與契約

- **data-model.md**：無新持久化實體；定義對外 DTO「OpenAI Model object」與其來源映射（`Allocation.resource_model` → `id`、provider → `owned_by`），列出涉及的既有表（唯讀）。
- **contracts/v1-models.md**：`GET /v1/models`、`GET /v1/models/{id}` 的請求（Bearer）/回應（OpenAI list / model）/錯誤（401 unauthorized、404 not_found）契約。
- **quickstart.md**：curl / Python SDK（`client.models.list()`）/ Copilot 三條驗證路徑，含部署後真機 SC-004 驗收步驟。
- **agent context**：執行 `update-agent-context.sh claude`（本功能無新技術，預期僅記一行階段資訊）。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
