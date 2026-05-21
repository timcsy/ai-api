# Implementation Plan: 階段 1 — 分流核心 (Gateway Core MVP)

**Branch**: `001-gateway-core` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-gateway-core/spec.md`

## Summary

以 LiteLLM 為代理核心，在其前後加上薄薄的「分配管理層」：
- **管理 API** 提供建立／撤回／查詢分配；分配資料持久化於關聯式資料庫
- **代理路徑**沿用 LiteLLM proxy，但攔截憑證 → 對應分配 → 驗證當前狀態 →
  以資源綁定限制可用模型 → 通過後改寫請求改用底層 Azure OpenAI key
- **呼叫紀錄** 以結構化日誌與 DB 表雙寫，查詢能力由 DB 提供
- **部署**以 Helm chart 描述；LiteLLM 鏡像由 Renovate 監看版本，回滾以
  Helm rollback 為主路徑

技術選型：Python 3.11 + FastAPI（管理 API）+ LiteLLM proxy + PostgreSQL
（生產）/ SQLite（本機）+ pytest 體系。容器化後以 Helm 部署到 K8s。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LiteLLM（proxy core）、FastAPI（admin API）、
  SQLAlchemy 2.x + Alembic（持久化與遷移）、Pydantic v2（驗證）、
  httpx（測試／代理客戶端）
**Storage**: PostgreSQL 15+（生產）；SQLite（本機開發、CI）
**Testing**: pytest、pytest-asyncio、httpx、schemathesis（OpenAPI 契約測試）、
  testcontainers-python（整合測試的真實 Postgres）
**Target Platform**: Linux container（distroless 或 slim base），K8s 部署
**Project Type**: web-service（HTTP API + 代理閘道，單一專案）
**Performance Goals**: 撤回生效 SLO ≤ 5s；代理路徑相對於上游延遲增加 ≤ 50ms
  p95（不含 Azure OpenAI 本身耗時）
**Constraints**: 服務端無本地狀態（狀態於 DB），可水平擴展；底層 Azure
  OpenAI key 僅存在於環境變數／K8s Secret
**Scale/Scope**: 階段 1 預期 ≤ 50 筆 active 分配、≤ 100 calls/min；用以驗證
  架構正確性，非性能壓測

## Constitution Check

依據 `.specify/memory/constitution.md`：

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First (NON-NEGOTIABLE) | spec FR-015、SC-008；本計畫 Phase 1 先產契約測試 | ✅ |
| II. Contract-First | spec FR-014、SC-007；本計畫 Phase 1 產 `contracts/openapi.yaml` 並先於實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | Azure OpenAI 與 Postgres 皆以 testcontainers / live sandbox 整合測試；mock 僅用於單元測試 | ✅ |
| IV. 可觀測性 | spec FR-011；本計畫指定 structured JSON logging + 每次呼叫帶 request_id 與 allocation_id；錯誤碼與供應商錯誤對應 | ✅ |
| V. YAGNI | spec 已明確列出 FR-019、FR-020 不在範圍；本計畫不引入服務發現、message bus、cache layer 等 | ✅ |

**初次評估通過**：無違反，不需 Complexity Tracking。
**Post-design 重評**：見本檔末尾 `Post-Design Re-check`。

## Project Structure

### Documentation (this feature)

```text
specs/001-gateway-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output (admin + proxy)
└── tasks.md             # Phase 2 output (by /speckit.tasks)
```

### Source Code (repository root)

```text
src/ai_api/
├── api/                 # FastAPI app: admin endpoints
│   ├── __init__.py
│   ├── allocations.py   # POST /admin/allocations, DELETE /admin/allocations/{id}
│   ├── records.py       # GET /admin/allocations/{id}/calls
│   └── deps.py          # bootstrap admin token auth
├── proxy/               # LiteLLM integration & request interception
│   ├── __init__.py
│   ├── auth.py          # credential → allocation lookup + state check
│   ├── guard.py         # model binding enforcement, redaction
│   └── config.py        # LiteLLM proxy config generation
├── models/              # SQLAlchemy models
│   ├── __init__.py
│   ├── allocation.py
│   ├── credential.py
│   └── call_record.py
├── services/
│   ├── allocations.py   # business logic: create / revoke / list
│   ├── credentials.py   # token generation + fingerprint
│   └── records.py       # call record persistence + queries
├── observability/
│   ├── logging.py       # structured JSON logger, key redaction filter
│   └── request_id.py
└── main.py              # app entrypoint

tests/
├── contract/            # OpenAPI conformance (schemathesis-driven)
├── integration/         # real Postgres (testcontainers) + Azure OpenAI sandbox
├── unit/                # pure unit tests with mocks
└── conftest.py

deploy/
├── helm/
│   └── ai-api/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── docker/
│   └── Dockerfile
└── docker-compose.yml   # local dev (api + postgres)

.github/
├── workflows/
│   ├── ci.yml           # lint + test + contract test
│   └── image.yml        # build & push container image
└── renovate.json        # LiteLLM image version tracking
```

**Structure Decision**: 採用 **Option 1 單一專案**。本服務是一個 Python
web-service（管理 API 與代理路徑在同一進程內），分為 `api` / `proxy` /
`models` / `services` / `observability` 五個模組。部署檔（Helm、Dockerfile、
compose）放在 `deploy/`，CI 設定放在 `.github/`。

## Complexity Tracking

無待說明的偏離。Constitution Check 全部通過。

## Post-Design Re-check

在 Phase 1 完成 `data-model.md` / `contracts/openapi.yaml` / `quickstart.md`
之後重新檢視五原則：

| 原則 | 重評 |
|---|---|
| Test-First | 契約檔已先於實作存在，OpenAPI 可生成失敗測試 → ✅ |
| Contract-First | OpenAPI 完整定義三類端點與錯誤 schema → ✅ |
| 整合測試覆蓋外部依賴 | quickstart 中明定本機跑 Postgres、整合 Azure OpenAI sandbox → ✅ |
| 可觀測性 | data-model 中 `CallRecord` 欄位包含 request_id、status_code、 token_usage → ✅ |
| YAGNI | data-model 僅含 4 個必要實體；無預先引入 Quota / Expiry 表 → ✅ |

通過。可進入 `/speckit.tasks` 拆解任務。
