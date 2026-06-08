# ai-api Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-06-08

## Active Technologies
- Python 3.11+（同 Phase 1） (002-auth-membership)
- PostgreSQL（含新表：members、sessions、email_whitelist、 (002-auth-membership)
- Python 3.11+（不變） (003-hardening)
- PostgreSQL（不變）；無新表，只修 Allocation enum (003-hardening)
- PostgreSQL（生產）/ SQLite（dev、CI） (004-usage-billing)
- GitHub Actions workflow YAML（無 source code 變更） (005-supply-chain)
- PostgreSQL（生產）/ SQLite（dev、CI）— `model_catalog` 表用 JSON columns (007-model-catalog)
- TypeScript（strict） + Python 3.11+（既有，不變） (008-frontend-scaffold)
- 無（前端不直接接 DB） (008-frontend-scaffold)
- 同 3b.0（前端 TS 5.x / React 19 / Vite 6）+ Python 3.11+ 後端 (009-member-view)
- 無；後端不動 schema (009-member-view)
- 同 3b.1 (010-admin-suite)
- Python 3.11+（後端不變）+ TypeScript strict / React 19 / Vite 6（前端不變） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`litellm`（library only，預計 `>=1.55,<2`）、`cryptography`（Fernet）、既有前端 stack（shadcn/ui + TanStack Query） (012-multi-provider-access)
- PostgreSQL（生產）/ SQLite（dev、CI）；新表 `provider_credentials`、`member_tags`；既有 `model_catalog` 加欄 (012-multi-provider-access)
- Python 3.11+ + FastAPI、SQLAlchemy 2.x async、Pydantic v2（既有，不新增套件） (017-admin-bootstrap)
- PostgreSQL（生產）/ SQLite（dev、CI）；本功能不新增表、不新增 migration (017-admin-bootstrap)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、TanStack Query、shadcn/ui（皆既有，不新增套件） (018-member-usage-overview)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration** (018-member-usage-overview)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、shadcn/ui（皆既有，不新增套件） (019-allocation-pause-resume)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**（`AllocationStatus`、`CallOutcome`、`AuditEventType` 皆 `Enum(..., native_enum=False)` 存 VARCHAR，加列舉值不需 schema 變更） (019-allocation-pause-resume)
- TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 處序列化） + TanStack Query、shadcn/ui、FastAPI、SQLAlchemy 2.x async（皆既有） (020-phase10-ux-polish)
- 不新增表、不新增 migration；display_name 取自既有 `model_catalog` (020-phase10-ux-polish)
- Python 3.11+（後端）/ TypeScript strict（前端僅用量顯示微調） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm` (021-responses-api)
- PostgreSQL（生產）/ SQLite（dev、CI）；migration `0013_responses_api` (021-responses-api)
- Python 3.11+（後端，既有不變）/ TypeScript strict + React 19 + Vite 6（前端，既有不變） (022-admin-email-notifications)
- PostgreSQL（生產）/ SQLite（dev、CI）；本功能新增表 `notification_config`、 (022-admin-email-notifications)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端），皆既有 + FastAPI、SQLAlchemy 2.x async、Pydantic v2、TanStack Query、shadcn/ui（皆既有，**不新增套件**） (023-tag-group-rollup)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——沿用既有 (023-tag-group-rollup)
- TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端少量聚合） (024-admin-visualization)
- PostgreSQL / SQLite；**不新增表、不新增 migration**——全部查詢層聚合 (024-admin-visualization)
- TypeScript strict + React 19 + Vite 6（**僅前端**；Python 後端完全不動） + 既有 Tailwind CSS、shadcn/ui（`Sheet` 將自既有 `@radix-ui/react-dialog` (025-mobile-rwd)
- N/A（純呈現層，無資料模型／migration） (025-mobile-rwd)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Pydantic v2（後端，既有）；Tailwind、shadcn/ui、 (026-member-usage-charts)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——以成員為範圍聚合既有用量 (026-member-usage-charts)
- Python 3.11+（後端為主）/ TypeScript strict + React 19（前端裝置清單） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2（皆既有）；前端既有 stack——**不新增套件** (028-per-device-credentials)
- PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0015`**（`credentials` 表改主鍵 + 加欄；保留既有資料） (028-per-device-credentials)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）/ POSIX `sh` + Windows PowerShell（安裝腳本） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`cryptography`（Fernet，既有）、TanStack Query、shadcn/ui（**皆既有，不新增套件**）；安裝腳本下載 OpenAI Codex CLI 獨立 binary（GitHub Releases，client-side） (029-codex-easy-install)
- PostgreSQL（生產）/ SQLite（dev、CI）；**新表 `device_authorizations` + migration `0016`** (029-codex-easy-install)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、TanStack Query、shadcn/ui（**皆既有，不新增套件**） (030-scoped-app-credentials)
- PostgreSQL（生產）/ SQLite（dev、CI）；**schema 重構 + migration `0017`**（改 `credentials` + 新 `credential_allocations`） (030-scoped-app-credentials)
- TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 個改名端點擴充） + TanStack Query、shadcn/ui、Tailwind（前端）；FastAPI、SQLAlchemy 2.x async、Pydantic v2（後端，**皆既有，不新增套件**） (031-credential-ui-consolidation)
- PostgreSQL / SQLite；**不新增表、不新增 migration**（`Credential.name` 已存在，僅允許更新） (031-credential-ui-consolidation)
- TypeScript strict（前端為主）；Python 3.11+（後端**完全不動**） + React 19 + Vite 6 + react-router-dom + TanStack Query + shadcn/ui + Tailwind（皆既有，不新增） (032-member-ui-tabs)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、**`litellm`（既有，library form——讀其內建 `model_cost` + `get_model_cost_map` 線上抓）**、TanStack Query、shadcn/ui。**不新增套件。** (033-litellm-catalog-sync)
- PostgreSQL（生產）/ SQLite（dev、CI）；**新 migration `0018`**——`model_catalog` 加一個 nullable JSON 欄 `litellm_sync`（來源標記 + 匯入快照 + 對照基礎模型 key）。價格沿用既有 `price_list`（append-only），不改 schema。 (033-litellm-catalog-sync)
- TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端少量擴充） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（既有）、TanStack Query、shadcn/ui。**不新增套件。** (034-catalog-admin-consolidation)
- PostgreSQL（生產）/ SQLite（dev、CI）；**無新 migration**——沿用階段 23 `model_catalog.litellm_sync`（JSON 欄）多存 `raw`；價格沿用 `price_list`。 (034-catalog-admin-consolidation)
- Python 3.11+（後端，既有不變）/ TypeScript strict + React 19 + Vite 6（前端，既有不變） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（aresponses 橋接，既有）；TanStack Query、shadcn/ui（前端，既有）。**不新增套件。** (035-responses-support-detection)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——responses 狀態以既有 `model_catalog.capabilities`（JSON list）的標記約定承載。 (035-responses-support-detection)
- Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端），皆既有不變 + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（library form：`acompletion`/`aresponses`/`aembedding`/`aspeech`/`aimage_generation`，皆既有套件內函式）；TanStack Query、shadcn/ui（前端）。**不新增套件。** (036-admin-model-test)
- PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——只讀既有 `model_catalog`（modality + `litellm_sync.raw.mode`）。 (036-admin-model-test)

- Python 3.11+ + LiteLLM（proxy core）、FastAPI（admin API）、 (001-gateway-core)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 036-admin-model-test: Added Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端），皆既有不變 + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（library form：`acompletion`/`aresponses`/`aembedding`/`aspeech`/`aimage_generation`，皆既有套件內函式）；TanStack Query、shadcn/ui（前端）。**不新增套件。**
- 035-responses-support-detection: Added Python 3.11+（後端，既有不變）/ TypeScript strict + React 19 + Vite 6（前端，既有不變） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（aresponses 橋接，既有）；TanStack Query、shadcn/ui（前端，既有）。**不新增套件。**
- 034-catalog-admin-consolidation: Added TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端少量擴充） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`（既有）、TanStack Query、shadcn/ui。**不新增套件。**


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
