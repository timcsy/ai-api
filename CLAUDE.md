# ai-api Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-28

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
- 021-responses-api: Added Python 3.11+（後端）/ TypeScript strict（前端僅用量顯示微調） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`
- 020-phase10-ux-polish: Added TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 處序列化） + TanStack Query、shadcn/ui、FastAPI、SQLAlchemy 2.x async（皆既有）
- 019-allocation-pause-resume: Added Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端） + FastAPI、SQLAlchemy 2.x async、Pydantic v2、shadcn/ui（皆既有，不新增套件）


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
